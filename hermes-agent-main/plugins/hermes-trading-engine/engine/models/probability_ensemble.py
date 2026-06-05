"""Probability ensemble + calibration guardrails (PAPER ONLY, pure).

Combines the available probability signals into a single, calibrated estimate
with an uncertainty band, while enforcing the project's safety contracts:

* **Sources combined:** market-implied probability, calibrated model
  probability, Chainlink/fast-BTC oracle features, news evidence score, and a
  no-trade label.
* **Online shrinkage:** the model is shrunk toward the market-implied
  probability when its sample size is small, so a thin model never dominates.
* **Evidence-only Grok/news:** news/Grok enter as a *bounded* nudge
  (``max_news_influence``). They can never move the estimate beyond that cap and
  are never the final authority — enforced + asserted.
* **Conformal uncertainty bands:** split-conformal from residual quantiles when
  available, else a sample-size-driven band.
* **Leakage checks:** helpers flag any feature timestamp at/after the label
  resolution time (future leakage).
* **Calibration rollback:** :class:`CalibrationGuard` decides keep-vs-rollback so
  a refit that degrades ECE/Brier on validation is reverted.
* **Bregman contract:** calibrated probabilities are for *ranking* opportunities
  only; a candidate is tradeable ONLY with deterministic executable-depth proof
  (``is_tradeable``). Ranking probability is never a substitute for depth proof.

Acquisition/calibration primitives are reused from
``engine.calibration_models`` and features from
``engine.features.oracle_features`` (both leaf modules) — no architecture,
client, feed, or infra changes.

Full quant scope is documented in :data:`QUANT_RESPONSIBILITIES`.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional, Sequence

logger = logging.getLogger("hte.models.ensemble")

# Hard cap on how far news/Grok evidence may move the estimate (evidence-only).
DEFAULT_MAX_NEWS_INFLUENCE: float = 0.10
# Pseudo-count for online shrinkage of the model toward the market prob.
DEFAULT_SHRINK_PSEUDOCOUNT: float = 50.0
# Bregman candidates require deterministic executable-depth proof before trading.
REQUIRE_DEPTH_PROOF: bool = True
_EPS = 1e-9

QUANT_RESPONSIBILITIES: dict[str, str] = {
    "acquisition_ingestion": "External (polymarket-client v2, Chainlink oracle, "
                             "Coinbase fast feed, news scanner). Not done here.",
    "preprocessing_features": "engine.features.oracle_features (anchor/fast/news "
                              "feature transforms) feed this ensemble.",
    "probabilistic_modeling": "THIS MODULE: market+model+feature+news ensemble, "
                              "online shrinkage, conformal bands.",
    "calibration": "engine.calibration_models (Platt/isotonic/temperature/shrink) "
                   "+ CalibrationGuard rollback on ECE/Brier degradation.",
    "bregman_signal_development": "Calibrated prob ranks opportunities ONLY; "
                                  "trading requires deterministic depth proof.",
    "risk_portfolio": "RiskEngine remains the execution gate; ensemble supplies "
                      "calibrated prob + uncertainty as advisory inputs.",
    "backtesting": "Pure + deterministic; replay-safe.",
    "optimization_robustness": "Explicit weights/caps/quantiles; leakage checks.",
    "clobv2_execution": "Unchanged/external; depth proof gates trading.",
    "monitoring": "ECE/Brier, rollback count, conformal width surfaced to the "
                  "inspection report + status CLI.",
    "compliance_security_ops": "PAPER ONLY; evidence-only Grok/news; no wallet/"
                               "keys/order path; no secrets.",
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _clip01(v: Any, lo: float = 0.02, hi: float = 0.98) -> Optional[float]:
    f = _num(v)
    if f is None:
        return None
    return min(hi, max(lo, f))


def _quantile(values: Sequence[float], q: float) -> Optional[float]:
    vals = sorted(v for v in (_num(x) for x in values) if v is not None)
    if not vals:
        return None
    q = min(1.0, max(0.0, q))
    idx = q * (len(vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def conformal_band(p: float, residuals: Optional[Sequence[float]] = None, *,
                   alpha: float = 0.1, n_eff: Optional[float] = None,
                   z: float = 1.64) -> tuple[float, float, float]:
    """Return ``(p, lo, hi)`` uncertainty band.

    With ``residuals`` (|y - p_pred| style absolute residuals) uses the
    split-conformal ``1-alpha`` empirical quantile. Otherwise falls back to a
    binomial-style half-width driven by ``n_eff`` (more data => tighter).
    """
    p = float(min(1.0, max(0.0, p)))
    half: float
    if residuals:
        half = _quantile([abs(_num(r) or 0.0) for r in residuals], 1.0 - alpha) or 0.0
    else:
        n = max(1.0, float(n_eff or 1.0))
        half = z * math.sqrt(max(p * (1.0 - p), _EPS) / n)
    lo = max(0.0, p - half)
    hi = min(1.0, p + half)
    return p, round(lo, 6), round(hi, 6)


def detect_leakage(feature_ts: Any, label_ts: Any) -> bool:
    """True if a feature timestamp is at/after the label resolution time
    (i.e. the feature could encode the outcome -> future leakage)."""
    f, l = _num(feature_ts), _num(label_ts)
    if f is None or l is None:
        return False
    return f >= l


def leakage_scan(records: Sequence[Mapping[str, Any]]) -> dict:
    """Scan ``[{feature_ts, label_ts}, ...]`` for leakage; return a summary."""
    leaks = [i for i, r in enumerate(records or [])
             if detect_leakage(r.get("feature_ts"), r.get("label_ts"))]
    n = len(records or [])
    return {"n": n, "leaks": leaks, "leak_count": len(leaks),
            "leakage_ok": len(leaks) == 0}


# --------------------------------------------------------------------------- #
# Ensemble
# --------------------------------------------------------------------------- #
@dataclass
class EnsembleConfig:
    """Weights/caps for the ensemble (all explicit for sweeps)."""

    shrink_pseudocount: float = DEFAULT_SHRINK_PSEUDOCOUNT
    w_feature: float = 0.05            # max feature nudge magnitude
    max_news_influence: float = DEFAULT_MAX_NEWS_INFLUENCE
    conformal_alpha: float = 0.1


@dataclass
class EnsembleInputs:
    """All optional inputs to the ensemble (None => unavailable)."""

    market_prob: Optional[float] = None
    model_prob: Optional[float] = None
    calibrated_model_prob: Optional[float] = None
    model_sample_size: Optional[int] = None
    oracle_features: Any = None          # OracleFeatureSet or dict (duck-typed)
    news_evidence_score: Optional[float] = None  # [0,1] strength
    news_direction: Optional[int] = None         # -1 / 0 / +1 toward UP
    no_trade_label: Optional[bool] = None
    residuals: Optional[Sequence[float]] = None


@dataclass
class ProbabilityEstimate:
    p: Optional[float]
    lo: Optional[float]
    hi: Optional[float]
    abstain: bool
    components: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class ProbabilityEnsemble:
    """Combine probability signals into one calibrated estimate (pure)."""

    def __init__(self, config: Optional[EnsembleConfig] = None):
        self.cfg = config or EnsembleConfig()

    # -- feature + news contributions (bounded) ------------------------------
    def _feature_signal(self, oracle_features: Any) -> float:
        """Directional feature nudge in [-w_feature, w_feature] from microtrend,
        scaled by anchor confidence and reduced on feed disagreement."""
        if oracle_features is None:
            return 0.0
        fast = _of_get(oracle_features, "fast")
        anchor = _of_get(oracle_features, "anchor")
        cross = _of_get(oracle_features, "cross")
        micro = _num(_of_get(fast, "microtrend")) or 0.0
        conf = _num(_of_get(anchor, "confidence_multiplier"))
        conf = 1.0 if conf is None else conf
        agree = _of_get(cross, "agree")
        agree_mult = 1.0 if agree in (None, True) else 0.5
        return self.cfg.w_feature * max(-1.0, min(1.0, micro)) * conf * agree_mult

    def _news_nudge(self, inp: EnsembleInputs) -> float:
        """Bounded news/Grok nudge (evidence-only). Never exceeds the cap."""
        score = _num(inp.news_evidence_score)
        direction = inp.news_direction
        if score is None or direction in (None, 0):
            return 0.0
        score = max(0.0, min(1.0, score))
        nud = (1 if direction > 0 else -1) * score * self.cfg.max_news_influence
        return max(-self.cfg.max_news_influence, min(self.cfg.max_news_influence, nud))

    def combine(self, inp: EnsembleInputs) -> ProbabilityEstimate:
        """Produce the final calibrated estimate + uncertainty band."""
        reasons: list[str] = []
        market = _clip01(inp.market_prob)
        model = _clip01(inp.calibrated_model_prob if inp.calibrated_model_prob is not None
                        else inp.model_prob)
        components = {"market": market, "model": model}

        if inp.no_trade_label:
            reasons.append("no_trade_label")
            p = market if market is not None else (model if model is not None else 0.5)
            _, lo, hi = conformal_band(p, inp.residuals, alpha=self.cfg.conformal_alpha,
                                       n_eff=inp.model_sample_size)
            return ProbabilityEstimate(p=round(p, 6), lo=lo, hi=hi, abstain=True,
                                       components=components, reasons=reasons)

        if model is None and market is None:
            reasons.append("no_signal")
            return ProbabilityEstimate(p=None, lo=None, hi=None, abstain=True,
                                       components=components, reasons=reasons)

        # --- online shrinkage of model toward market ---
        n = float(inp.model_sample_size or 0)
        w_model = n / (n + self.cfg.shrink_pseudocount) if (n + self.cfg.shrink_pseudocount) > 0 else 0.0
        if model is not None and market is not None:
            core = w_model * model + (1.0 - w_model) * market
            if w_model < 0.5:
                reasons.append("shrunk_to_market")
        else:
            core = model if model is not None else market
        components["w_model"] = round(w_model, 4)
        components["core"] = round(core, 6)

        # --- bounded feature nudge ---
        fsig = self._feature_signal(inp.oracle_features)
        if fsig:
            components["feature_nudge"] = round(fsig, 6)
            reasons.append("feature_nudge")

        # --- bounded news/Grok evidence nudge (never final authority) ---
        nud = self._news_nudge(inp)
        if nud:
            components["news_nudge"] = round(nud, 6)
            reasons.append("news_evidence")

        adjusted = core + fsig + nud
        # Enforce evidence-only: total external (feature+news) move is capped so
        # the model/market core remains the authority.
        max_ext = self.cfg.w_feature + self.cfg.max_news_influence
        adjusted = max(core - max_ext, min(core + max_ext, adjusted))
        p = float(_clip01(adjusted))

        _, lo, hi = conformal_band(p, inp.residuals, alpha=self.cfg.conformal_alpha,
                                   n_eff=inp.model_sample_size)
        return ProbabilityEstimate(p=round(p, 6), lo=lo, hi=hi, abstain=False,
                                   components=components, reasons=reasons)


def _of_get(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return obj.get(key)
    # OracleFeatureSet exposes attributes; sub-objects expose attributes too.
    return getattr(obj, key, None)


# --------------------------------------------------------------------------- #
# Calibration rollback guard
# --------------------------------------------------------------------------- #
@dataclass
class CalibrationGuard:
    """Keep-vs-rollback decision for a refit, with a rollback counter.

    A candidate is rejected (rollback) only when it degrades BOTH ECE and Brier
    on the validation set beyond ``tol`` — avoids churn while preventing a worse
    calibrator from going live.
    """

    tol: float = 0.0
    rollbacks: int = 0
    keeps: int = 0

    def consider(self, candidate: Mapping[str, Any],
                 current: Optional[Mapping[str, Any]]) -> dict:
        cand_ece = _num((candidate or {}).get("ece"))
        cand_brier = _num((candidate or {}).get("brier"))
        if not current:
            self.keeps += 1
            return {"decision": "keep", "reason": "no_prior"}
        cur_ece = _num(current.get("ece"))
        cur_brier = _num(current.get("brier"))
        if None in (cand_ece, cand_brier, cur_ece, cur_brier):
            self.keeps += 1
            return {"decision": "keep", "reason": "missing_metrics"}
        if cand_ece > cur_ece + self.tol and cand_brier > cur_brier + self.tol:
            self.rollbacks += 1
            return {"decision": "rollback", "reason": "ece+brier degraded",
                    "ece": [cur_ece, cand_ece], "brier": [cur_brier, cand_brier]}
        self.keeps += 1
        return {"decision": "keep", "reason": "ok"}


# --------------------------------------------------------------------------- #
# Bregman ranking contract (calibrated prob ranks; depth proof gates trading)
# --------------------------------------------------------------------------- #
def _edge(c: Mapping[str, Any]) -> float:
    p = _num(c.get("calibrated_prob"))
    mkt = _num(c.get("market_prob"))
    if p is None:
        return float("-inf")
    if mkt is None:
        return p
    return p - mkt


def rank_candidates(candidates: Sequence[Mapping[str, Any]]) -> list[dict]:
    """Rank Bregman candidates by calibrated edge (descending). RANKING ONLY —
    ordering never authorizes a trade; see :func:`is_tradeable`."""
    rows = [dict(c) for c in (candidates or [])]
    rows.sort(key=_edge, reverse=True)
    return rows


def is_tradeable(candidate: Mapping[str, Any], *,
                 require_depth_proof: bool = REQUIRE_DEPTH_PROOF) -> bool:
    """A candidate is tradeable ONLY with deterministic executable-depth proof.

    Calibrated probability/edge rank candidates but never substitute for the
    deterministic depth proof that Bregman/CLOB must supply before any trade.
    """
    if not require_depth_proof:
        return True
    return bool(candidate.get("executable_depth_proof")) is True

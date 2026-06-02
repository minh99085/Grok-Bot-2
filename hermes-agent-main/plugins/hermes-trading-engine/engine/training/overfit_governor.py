"""Anti-overfitting controls for the aggressive paper-learning system.

Quant scope (all deterministic, stdlib-only, PAPER ONLY — nothing here trades):

* **Data Ingestion / Preprocessing** — :func:`time_category_split` produces a
  no-leakage train/validation/test split *stratified by market category* so
  every category contributes to all three splits and time order is preserved
  inside each category (train precedes validation precedes test).
* **Statistical Modeling / Strategy Optimization** —
  :func:`walk_forward_evaluate` measures in-sample vs out-of-sample performance
  over rolling windows; :func:`parameter_stability_score` quantifies how stable a
  parameter is across windows; :func:`overfit_penalty` scores IS→OOS degradation.
* **Risk/Portfolio Optimization** — :func:`overfit_penalized_params` shrinks
  aggressive thresholds, shrink factors, risk sizes, and exploration settings
  toward conservative defaults in proportion to the overfit penalty.
* **Backtesting / Monitoring** — :class:`OverfitDetector` flags an IS/OOS metric
  bundle (Sharpe, Brier, log-loss, ECE, realized edge, drawdown) as overfit.
* **Bregman arbitrage robustness** — :func:`bregman_false_positive_robustness`
  flags certified "risk-free" opportunities that settled to a loss.
* **Compliance/Security** — :class:`WalkForwardParameterGovernor` is the
  promotion gate: a parameter set (especially an *aggressive* one) can only be
  promoted to production-like parameters when walk-forward validation passes.

This module never relaxes a risk gate. It only ever makes the learner MORE
conservative (or blocks a promotion).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

logger = logging.getLogger("hte.training.overfit_governor")

_EPS = 1e-9


# --------------------------------------------------------------------------- #
# train / validation / test split by time AND market category
# --------------------------------------------------------------------------- #
@dataclass
class SplitResult:
    """A chronological, category-stratified train/validation/test split."""

    train: list = field(default_factory=list)
    validation: list = field(default_factory=list)
    test: list = field(default_factory=list)

    def coverage(self) -> dict:
        """``category -> {train, validation, test}`` sample counts."""
        cov: dict = {}
        for name, rows in (("train", self.train), ("validation", self.validation),
                           ("test", self.test)):
            for o in rows:
                cat = str(o.get("category", "uncategorized"))
                cov.setdefault(cat, {"train": 0, "validation": 0, "test": 0})
                cov[cat][name] += 1
        return cov

    def to_dict(self) -> dict:
        return {"n_train": len(self.train), "n_validation": len(self.validation),
                "n_test": len(self.test), "coverage": self.coverage()}


def time_category_split(observations: Sequence[dict], *, ts_key: str = "ts",
                        category_key: str = "category", train_frac: float = 0.6,
                        val_frac: float = 0.2) -> SplitResult:
    """Split ``observations`` into train/validation/test with NO look-ahead.

    The split is stratified by ``category_key`` and chronological by ``ts_key``
    *inside each category*: for every category the earliest ``train_frac`` rows
    go to train, the next ``val_frac`` to validation, the remainder to test. This
    guarantees (a) every category with >=3 samples is represented in all three
    splits and (b) train always precedes validation precedes test in time within
    a category (no leakage). Tiny categories (<3 samples) are placed
    deterministically into the earliest non-empty split they can fill.
    """
    train_frac = max(0.0, min(1.0, float(train_frac)))
    val_frac = max(0.0, min(1.0 - train_frac, float(val_frac)))
    by_cat: dict = {}
    for o in observations:
        by_cat.setdefault(str(o.get(category_key, "uncategorized")), []).append(o)

    res = SplitResult()
    for _cat, rows in sorted(by_cat.items()):
        rows = sorted(rows, key=lambda r: r.get(ts_key, 0))
        n = len(rows)
        if n == 0:
            continue
        if n < 3:
            # Not enough to populate three splits: assign each available row to
            # train, then validation, then test (chronologically).
            buckets = (res.train, res.validation, res.test)
            for i, r in enumerate(rows):
                buckets[min(i, 2)].append(r)
            continue
        n_train = max(1, int(round(n * train_frac)))
        n_val = max(1, int(round(n * val_frac)))
        # ensure at least one row remains for test
        if n_train + n_val >= n:
            n_val = max(1, min(n_val, n - n_train - 1))
            if n_train + n_val >= n:
                n_train = max(1, n - 2)
                n_val = 1
        res.train += rows[:n_train]
        res.validation += rows[n_train:n_train + n_val]
        res.test += rows[n_train + n_val:]

    res.train.sort(key=lambda r: r.get(ts_key, 0))
    res.validation.sort(key=lambda r: r.get(ts_key, 0))
    res.test.sort(key=lambda r: r.get(ts_key, 0))
    return res


# --------------------------------------------------------------------------- #
# parameter stability + overfit penalty (scalars)
# --------------------------------------------------------------------------- #
def parameter_stability_score(values: Sequence[float]) -> float:
    """Stability of a parameter/metric across walk-forward windows, in ``(0, 1]``.

    Constant series -> 1.0. Higher dispersion (coefficient of variation) -> lower
    score via ``1 / (1 + cv)``. A constant-zero series is treated as perfectly
    stable.
    """
    vals = [float(v) for v in values]
    if len(vals) < 2:
        return 1.0
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = math.sqrt(var)
    scale = abs(mean) if abs(mean) > _EPS else (max(abs(v) for v in vals) or 1.0)
    cv = std / (scale + _EPS)
    return round(1.0 / (1.0 + cv), 6)


def overfit_penalty(in_sample: float, out_of_sample: float, *,
                    higher_better: bool = True) -> float:
    """Normalized IS→OOS degradation penalty in ``[0, 1]``.

    ``higher_better`` metrics (Sharpe, realized edge): penalty grows as OOS falls
    below IS. ``higher_better=False`` metrics (Brier, log-loss, ECE): penalty
    grows as OOS rises above IS. No degradation (or OOS better than IS) -> 0.
    """
    is_v = float(in_sample)
    oos_v = float(out_of_sample)
    denom = abs(is_v) + _EPS
    gap = (is_v - oos_v) / denom if higher_better else (oos_v - is_v) / denom
    return round(max(0.0, min(1.0, gap)), 6)


# --------------------------------------------------------------------------- #
# walk-forward evaluation
# --------------------------------------------------------------------------- #
@dataclass
class WalkForwardResult:
    windows: list = field(default_factory=list)   # [{index, is_metric, oos_metric}]
    mean_is: float = 0.0
    mean_oos: float = 0.0
    oos_is_ratio: float = 1.0
    stability: float = 1.0
    overfit_penalty: float = 0.0
    n_windows: int = 0
    higher_better: bool = True

    def to_dict(self) -> dict:
        return {"windows": self.windows, "mean_is": round(self.mean_is, 6),
                "mean_oos": round(self.mean_oos, 6),
                "oos_is_ratio": round(self.oos_is_ratio, 6),
                "stability": round(self.stability, 6),
                "overfit_penalty": round(self.overfit_penalty, 6),
                "n_windows": self.n_windows, "higher_better": self.higher_better}


def walk_forward_evaluate(observations: Sequence[dict], *,
                          metric_fn: Callable[[list], float], train: int, test: int,
                          step: Optional[int] = None, higher_better: bool = True
                          ) -> WalkForwardResult:
    """Rolling walk-forward IS/OOS evaluation of ``metric_fn`` over ``observations``.

    For each rolling window, ``metric_fn`` is computed on the train slice (the
    in-sample estimate) and the immediately-following test slice (the
    out-of-sample estimate). Aggregates the per-window IS/OOS means, the OOS/IS
    ratio, the OOS stability across windows, and the overfit penalty.
    """
    from engine.replay.robustness import walk_forward_windows

    rows = list(observations)
    wins = walk_forward_windows(len(rows), train=int(train), test=int(test), step=step)
    out: list = []
    for w in wins:
        tr = rows[w.train_start:w.train_end]
        te = rows[w.test_start:w.test_end]
        if not tr or not te:
            continue
        out.append({"index": w.index, "is_metric": float(metric_fn(tr)),
                    "oos_metric": float(metric_fn(te))})
    if not out:
        return WalkForwardResult(higher_better=higher_better)

    mean_is = sum(r["is_metric"] for r in out) / len(out)
    mean_oos = sum(r["oos_metric"] for r in out) / len(out)
    stability = parameter_stability_score([r["oos_metric"] for r in out])
    pen = overfit_penalty(mean_is, mean_oos, higher_better=higher_better)
    if higher_better:
        ratio = mean_oos / mean_is if abs(mean_is) > _EPS else (1.0 if mean_oos >= 0 else 0.0)
    else:
        ratio = mean_is / mean_oos if abs(mean_oos) > _EPS else 1.0
    return WalkForwardResult(windows=out, mean_is=mean_is, mean_oos=mean_oos,
                             oos_is_ratio=ratio, stability=stability,
                             overfit_penalty=pen, n_windows=len(out),
                             higher_better=higher_better)


# --------------------------------------------------------------------------- #
# overfit detector (IS vs OOS metric bundle)
# --------------------------------------------------------------------------- #
@dataclass
class OverfitVerdict:
    overfit: bool
    score: float
    reasons: list = field(default_factory=list)
    penalties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"overfit": self.overfit, "score": round(self.score, 6),
                "reasons": list(self.reasons),
                "penalties": {k: round(v, 6) for k, v in self.penalties.items()}}


class OverfitDetector:
    """Flags an in-sample/out-of-sample metric bundle as overfit.

    Metric dicts may carry any of ``sharpe``, ``realized_edge`` (higher better),
    ``brier``, ``log_loss``, ``ece`` (lower better), and ``max_drawdown`` (more
    negative = worse). Each present metric contributes an overfit penalty; the
    verdict is overfit when any per-metric penalty exceeds its threshold.
    """

    _HIGHER = ("sharpe", "realized_edge")
    _LOWER = ("brier", "log_loss", "ece")

    def __init__(self, *, max_penalty: float = 0.5, max_brier_gap: float = 0.08,
                 max_ece_gap: float = 0.06, max_drawdown_ratio: float = 2.0):
        self.max_penalty = float(max_penalty)
        self.max_brier_gap = float(max_brier_gap)
        self.max_ece_gap = float(max_ece_gap)
        self.max_drawdown_ratio = float(max_drawdown_ratio)

    def detect(self, in_sample: dict, out_of_sample: dict) -> OverfitVerdict:
        reasons: list = []
        penalties: dict = {}
        for k in self._HIGHER:
            if k in in_sample and k in out_of_sample:
                p = overfit_penalty(in_sample[k], out_of_sample[k], higher_better=True)
                penalties[k] = p
                if p > self.max_penalty:
                    reasons.append(f"{k}_oos_degraded(penalty={p:.2f})")
        for k in self._LOWER:
            if k in in_sample and k in out_of_sample:
                p = overfit_penalty(in_sample[k], out_of_sample[k], higher_better=False)
                penalties[k] = p
                gap = float(out_of_sample[k]) - float(in_sample[k])
                thresh = self.max_ece_gap if k == "ece" else self.max_brier_gap
                if p > self.max_penalty or gap > thresh:
                    reasons.append(f"{k}_oos_worse(gap={gap:.3f})")
        # drawdown: OOS much deeper than IS
        if "max_drawdown" in in_sample and "max_drawdown" in out_of_sample:
            is_dd = abs(float(in_sample["max_drawdown"]))
            oos_dd = abs(float(out_of_sample["max_drawdown"]))
            if is_dd > _EPS and oos_dd / is_dd > self.max_drawdown_ratio:
                penalties["max_drawdown"] = round(min(1.0, oos_dd / is_dd / 4.0), 6)
                reasons.append(f"drawdown_oos_blowup(ratio={oos_dd / is_dd:.2f})")
        score = max(penalties.values()) if penalties else 0.0
        return OverfitVerdict(overfit=bool(reasons), score=score, reasons=reasons,
                              penalties=penalties)


# --------------------------------------------------------------------------- #
# overfit-penalized parameters (thresholds / shrink / risk sizes / exploration)
# --------------------------------------------------------------------------- #
def overfit_adjusted_value(aggressive_value: float, conservative_value: float,
                           penalty: float) -> float:
    """Linear blend ``(1-penalty)*aggressive + penalty*conservative``.

    ``penalty=0`` keeps the aggressive value; ``penalty=1`` reverts to the
    conservative value. Used for every overfit-penalized parameter so a fragile
    parameter set is automatically pulled back toward safe defaults.
    """
    p = max(0.0, min(1.0, float(penalty)))
    return (1.0 - p) * float(aggressive_value) + p * float(conservative_value)


def overfit_penalized_params(params: dict, penalty: float, *,
                             conservative: dict) -> dict:
    """Shrink each parameter present in ``conservative`` toward its conservative
    target in proportion to ``penalty``. Parameters absent from ``conservative``
    are passed through unchanged."""
    out = dict(params)
    p = max(0.0, min(1.0, float(penalty)))
    if p <= 0.0:
        return out
    for k, cons in conservative.items():
        if k in out:
            out[k] = overfit_adjusted_value(out[k], cons, p)
    return out


# --------------------------------------------------------------------------- #
# Bregman false-positive arbitrage robustness
# --------------------------------------------------------------------------- #
def bregman_false_positive_robustness(certifications: Sequence[dict], *,
                                      max_fp_rate: float = 0.1,
                                      min_samples: int = 1) -> dict:
    """Robustness check on certified "risk-free" Bregman opportunities.

    ``certifications`` is a list of ``{certified_profit, realized_pnl,
    all_leg_fill_prob}`` records. A *false positive* is a bundle that was
    certified profitable (``certified_profit > 0``) yet settled to a loss
    (``realized_pnl <= 0``) — exactly the failure mode that breaks a hedge when
    partial fills or settlement ambiguity hit. Returns the false-positive rate
    and whether it stays within ``max_fp_rate``.
    """
    certs = [c for c in certifications if float(c.get("certified_profit", 0.0)) > 0.0]
    n = len(certs)
    fps = [c for c in certs if float(c.get("realized_pnl", 0.0)) <= 0.0]
    fp_rate = (len(fps) / n) if n else 0.0
    mean_realized = (sum(float(c.get("realized_pnl", 0.0)) for c in certs) / n) if n else 0.0
    robust = n >= min_samples and fp_rate <= float(max_fp_rate)
    return {"n": n, "certified": n, "false_positives": len(fps),
            "fp_rate": round(fp_rate, 6), "mean_realized": round(mean_realized, 6),
            "robust": bool(robust),
            "mean_fill_prob": round(
                sum(float(c.get("all_leg_fill_prob", 0.0)) for c in certs) / n, 6)
            if n else 0.0}


# --------------------------------------------------------------------------- #
# walk-forward parameter governor (promotion gate)
# --------------------------------------------------------------------------- #
class WalkForwardParameterGovernor:
    """Gate that promotes parameters to production-like state only when
    walk-forward validation passes.

    A promotion is allowed only when (a) the walk-forward result passes
    (OOS not materially degraded vs IS, stable across windows, low overfit
    penalty) and (b) the IS/OOS metric bundle is not flagged overfit. Aggressive
    parameter sets are held to the SAME walk-forward bar — they may learn faster
    online, but cannot promote production-like parameters unless walk-forward
    validation passes.
    """

    def __init__(self, *, oos_degrade_tolerance: float = 0.2,
                 min_param_stability: float = 0.5, max_overfit_penalty: float = 0.5,
                 detector: Optional[OverfitDetector] = None):
        self.oos_degrade_tolerance = float(oos_degrade_tolerance)
        self.min_param_stability = float(min_param_stability)
        self.max_overfit_penalty = float(max_overfit_penalty)
        self.detector = detector or OverfitDetector(max_penalty=max_overfit_penalty)

    def evaluate(self, observations: Sequence[dict], *,
                 metric_fn: Callable[[list], float], train: int, test: int,
                 step: Optional[int] = None, higher_better: bool = True
                 ) -> WalkForwardResult:
        return walk_forward_evaluate(observations, metric_fn=metric_fn, train=train,
                                     test=test, step=step, higher_better=higher_better)

    def passes(self, wf: WalkForwardResult) -> bool:
        if wf.n_windows <= 0:
            return False
        return (wf.oos_is_ratio >= (1.0 - self.oos_degrade_tolerance)
                and wf.stability >= self.min_param_stability
                and wf.overfit_penalty <= self.max_overfit_penalty)

    def can_promote(self, *, walk_forward: WalkForwardResult,
                    in_sample: Optional[dict] = None,
                    out_of_sample: Optional[dict] = None, aggressive: bool = False
                    ) -> dict:
        reasons: list = []
        wf_ok = self.passes(walk_forward)
        if not wf_ok:
            if walk_forward.n_windows <= 0:
                reasons.append("walk_forward_no_windows")
            if walk_forward.oos_is_ratio < (1.0 - self.oos_degrade_tolerance):
                reasons.append(f"oos_degraded(ratio={walk_forward.oos_is_ratio:.2f})")
            if walk_forward.stability < self.min_param_stability:
                reasons.append(f"unstable(stability={walk_forward.stability:.2f})")
            if walk_forward.overfit_penalty > self.max_overfit_penalty:
                reasons.append(f"overfit_penalty={walk_forward.overfit_penalty:.2f}")

        verdict = None
        if in_sample is not None and out_of_sample is not None:
            verdict = self.detector.detect(in_sample, out_of_sample)
            if verdict.overfit:
                reasons += [f"detector:{r}" for r in verdict.reasons]

        promote = wf_ok and (verdict is None or not verdict.overfit)
        # Aggressive promotion is held to the SAME walk-forward bar; an overfit /
        # WF-failing aggressive set can never reach production-like params.
        if aggressive and not promote:
            reasons.append("aggressive_locked_until_walk_forward_passes")
        return {"promote": bool(promote), "walk_forward_passed": bool(wf_ok),
                "aggressive": bool(aggressive), "reasons": reasons,
                "walk_forward": walk_forward.to_dict(),
                "overfit": verdict.to_dict() if verdict is not None else None}


# conservative production targets the governor pulls aggressive params toward when
# overfitting is detected (matches TrainingConfig non-aggressive defaults).
CONSERVATIVE_PARAMS = {
    "min_net_edge": 0.03,
    "base_shrink_factor": 0.25,
    "fixed_notional_usd": 5.0,
    "exploration_rate": 0.0,
    "exploration_notional_usd": 0.0,
    "max_event_exposure_usd": 20.0,
    "max_bregman_bundle_exposure_usd": 30.0,
}

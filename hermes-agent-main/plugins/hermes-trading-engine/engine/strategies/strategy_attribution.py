"""Per-strategy PnL attribution, ablations + production-readiness (pure).

Exploration trades (Tier-4 tiny paper bets) must NEVER count as live-readiness
validation evidence. This module keeps a clean split:

* ``validation_pnl`` — PnL from certified/edge trades (Tiers 1-3).
* ``exploration_pnl`` — PnL from exploration-only trades (Tier 4).
* ``by_strategy`` / ``by_tier`` — attribution breakdowns.

It also provides **ablation attribution** (how much each component — Bregman /
Chainlink / fast BTC / news / Grok / calibration — contributes vs a leave-it-out
run) and a **three-bucket readiness report** that keeps exploration, validation,
and production-readiness strictly separate.

Pure, deterministic, no I/O. PAPER ONLY.

Quant responsibilities
----------------------
* Quant analyst — enumerates the ablation components to test.
* Quant researcher — defines validation vs exploration + the readiness gate
  (significance + positive ablations + no overfit).
* Quant developer — owns this attribution/ablation accounting (typed, tested).
* Trader/monitoring — reads validation-only + production-ready signals; never
  conflates exploration PnL with validated edge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

logger = logging.getLogger("hte.strategies.attribution")


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


@dataclass
class AttributionRecord:
    strategy: str
    pnl: float
    tier: Optional[int] = None
    is_exploration: bool = False


@dataclass
class PnLAttribution:
    """Accumulates trade PnL split by exploration/validation + strategy/tier."""

    validation_pnl: float = 0.0
    exploration_pnl: float = 0.0
    by_strategy: dict = field(default_factory=dict)
    by_tier: dict = field(default_factory=dict)
    n_validation: int = 0
    n_exploration: int = 0

    def record(self, strategy: str, pnl, *, tier: Optional[int] = None,
               is_exploration: bool = False) -> None:
        """Record one resolved paper trade's PnL (validation unless flagged)."""
        p = _num(pnl)
        if p is None:
            logger.debug("ignoring non-numeric pnl for %s: %r", strategy, pnl)
            return
        self.by_strategy[strategy] = round(self.by_strategy.get(strategy, 0.0) + p, 10)
        if tier is not None:
            self.by_tier[int(tier)] = round(self.by_tier.get(int(tier), 0.0) + p, 10)
        if is_exploration:
            self.exploration_pnl = round(self.exploration_pnl + p, 10)
            self.n_exploration += 1
        else:
            self.validation_pnl = round(self.validation_pnl + p, 10)
            self.n_validation += 1

    def total_pnl(self) -> float:
        return round(self.validation_pnl + self.exploration_pnl, 10)

    def summary(self) -> dict:
        return {
            "validation_pnl": self.validation_pnl,
            "exploration_pnl": self.exploration_pnl,
            "total_pnl": self.total_pnl(),
            "n_validation": self.n_validation,
            "n_exploration": self.n_exploration,
            "by_strategy": dict(self.by_strategy),
            "by_tier": dict(self.by_tier),
            # Validation-only is the readiness number; exploration excluded.
            "exploration_excluded_from_validation": True,
        }


def split_exploration_validation(records: Iterable[Mapping]) -> dict:
    """Split a list of ``{strategy, pnl, tier?, is_exploration?}`` records into a
    PnLAttribution summary. Convenience wrapper around :class:`PnLAttribution`."""
    attr = PnLAttribution()
    for r in records or []:
        attr.record(r.get("strategy", "unknown"), r.get("pnl"),
                    tier=r.get("tier"), is_exploration=bool(r.get("is_exploration")))
    return attr.summary()


# --------------------------------------------------------------------------- #
# Ablation attribution
# --------------------------------------------------------------------------- #
ABLATION_COMPONENTS = (
    "bregman", "chainlink", "fast_btc", "news", "grok", "calibration",
)


def ablation_report(baseline_metric: float, ablated: Mapping[str, float], *,
                    metric_name: str = "metric",
                    min_contribution: float = 0.0) -> dict:
    """Quantify each component's contribution via leave-one-out ablation (pure).

    ``baseline_metric`` is the full-system score; ``ablated[component]`` is the
    score with that component REMOVED. Contribution = baseline - ablated (a
    positive value means the component helps). A component is flagged
    ``necessary`` when its contribution clears ``min_contribution``. Components
    with a negative contribution are flagged ``harmful`` (candidate to drop).
    """
    base = float(baseline_metric)
    rows: dict[str, dict] = {}
    for comp, score in (ablated or {}).items():
        try:
            contrib = base - float(score)
        except (TypeError, ValueError):
            continue
        rows[comp] = {
            "ablated_metric": round(float(score), 8),
            "contribution": round(contrib, 8),
            "necessary": contrib > float(min_contribution),
            "harmful": contrib < 0.0,
        }
    ranked = sorted(rows.items(), key=lambda kv: kv[1]["contribution"], reverse=True)
    return {
        "metric_name": metric_name,
        "baseline_metric": round(base, 8),
        "components": rows,
        "ranking": [c for c, _ in ranked],
        "necessary": [c for c, r in rows.items() if r["necessary"]],
        "harmful": [c for c, r in rows.items() if r["harmful"]],
    }


# --------------------------------------------------------------------------- #
# Three-bucket readiness report (exploration vs validation vs production)
# --------------------------------------------------------------------------- #
def production_readiness(*, validation: Mapping, exploration: Optional[Mapping] = None,
                        significance: Optional[Mapping] = None,
                        ablations: Optional[Mapping] = None,
                        overfit: Optional[bool] = None,
                        min_validation_trades: int = 50) -> dict:
    """Combine evidence into THREE strictly-separated buckets (pure).

    * ``exploration`` — reported but NEVER part of the readiness verdict.
    * ``validation`` — validation-only PnL/trade evidence.
    * ``production_ready`` — True only when validation has enough trades AND the
      significance gate passed AND no required ablation is harmful AND overfit is
      not flagged. Returns a structured report with the gating reasons.
    """
    val = dict(validation or {})
    n_val = int(val.get("n_validation", val.get("trades", 0)) or 0)
    reasons: list[str] = []

    if n_val < int(min_validation_trades):
        reasons.append(f"insufficient_validation_trades({n_val}<{min_validation_trades})")
    sig_pass = bool((significance or {}).get("passed", False))
    if significance is not None and not sig_pass:
        reasons.append("significance_gate_failed")
    harmful = list((ablations or {}).get("harmful", []))
    if harmful:
        reasons.append(f"harmful_components:{','.join(harmful)}")
    if overfit:
        reasons.append("overfit_flagged")

    production_ready = (n_val >= int(min_validation_trades)
                        and (significance is None or sig_pass)
                        and not harmful and not overfit)
    return {
        "exploration": dict(exploration or {}),
        "validation": val,
        "significance": dict(significance or {}),
        "ablations": dict(ablations or {}),
        "overfit": bool(overfit) if overfit is not None else None,
        "production_ready": bool(production_ready),
        "blocking_reasons": reasons,
        # Hard contract: exploration is excluded from the readiness verdict.
        "exploration_excluded_from_readiness": True,
    }

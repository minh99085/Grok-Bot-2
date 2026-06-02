"""Paper experiment manager — controlled strategy-variant experiments.

Instead of learning from one blended policy, the trainer runs controlled
PAPER-ONLY experiments across distinct strategy variants:

* ``bregman``          — certified Bregman arbitrage (flagship; first budget).
* ``statistical_edge`` — calibrated statistical-mispricing edge (priority 2).
* ``directional_edge`` — directional / research-driven edge (priority 3).
* ``chainlink_edge``   — directional edge on a Chainlink-linked market.
* ``exploration``      — bounded active-learning exploratory paper trades.

Quant scope:

* **Signal Generation / Bregman strategy** — :func:`classify_variant` tags each
  decision with the variant that produced it; Bregman keeps priority-1 budget.
* **Risk/Portfolio Optimization** — :meth:`ExperimentManager.allocate` splits a
  PAPER-ONLY trade-slot budget across variants. It can only ever DISTRIBUTE
  existing slots (its sum never exceeds the slot budget), so hard risk caps —
  enforced by the RiskEngine/portfolio across the COMBINED book — still bind.
* **Backtesting / Monitoring** — :meth:`variant_metrics` reports per-variant
  trade/feedback counts, Sharpe, Sortino, Calmar, drawdown, Brier, log-loss,
  ECE, realized edge, and fill quality; :meth:`champion_challenger` ranks them.
* **Compliance/Security** — nothing here sizes orders, approves trades, or
  relaxes a cap; it is pure accounting + slot distribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Strategy variants, in budget-priority order (Bregman first).
BREGMAN_VARIANT = "bregman"
STRATEGY_VARIANTS = (
    "bregman", "statistical_edge", "directional_edge", "chainlink_edge", "exploration")
_NON_BREGMAN = tuple(v for v in STRATEGY_VARIANTS if v != BREGMAN_VARIANT)


def classify_variant(*, strategy: Optional[str], exploration: bool = False,
                     chainlink_linked: bool = False) -> str:
    """Map a resolved signal + flags to a strategy variant.

    Priority: Bregman (flagship) > exploration > Chainlink-linked > statistical >
    directional. Bregman always wins (it is the certified, hedged strategy)."""
    s = (strategy or "").strip().lower()
    if s in ("bregman", "bregman_arbitrage"):
        return "bregman"
    if exploration:
        return "exploration"
    if chainlink_linked:
        return "chainlink_edge"
    if s in ("statistical_mispricing", "statistical", "statistical_edge"):
        return "statistical_edge"
    return "directional_edge"


@dataclass
class VariantMetrics:
    """Per-variant paper metrics (deterministic; reuses replay metric math)."""

    variant: str
    starting_bankroll: float = 500.0
    trades: int = 0
    feedback: int = 0
    orders: int = 0
    fills: int = 0
    notional: float = 0.0
    _equity: list = field(default_factory=list)
    _preds: list = field(default_factory=list)
    _outs: list = field(default_factory=list)
    _trades_edge: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self._equity:
            self._equity = [float(self.starting_bankroll)]

    def record_trade(self, *, notional: float = 0.0) -> None:
        self.trades += 1
        self.notional = round(self.notional + float(notional or 0.0), 6)

    def record_fill(self, *, filled: bool) -> None:
        self.orders += 1
        if filled:
            self.fills += 1

    def record_feedback(self, *, predicted_prob: float, win: bool, realized_pnl: float,
                        net_edge: float = 0.0, cost: float = 0.0) -> None:
        self.feedback += 1
        self._equity.append(round(self._equity[-1] + float(realized_pnl), 6))
        self._preds.append(float(predicted_prob))
        self._outs.append(1.0 if win else 0.0)
        self._trades_edge.append({"realized_pnl": float(realized_pnl),
                                  "cost": float(cost), "net_edge": float(net_edge)})

    def to_dict(self) -> dict:
        from engine.replay import metrics as _m
        dd_abs, _dd_pct = _m.max_drawdown(self._equity)
        return {
            "variant": self.variant,
            "trade_count": self.trades,
            "feedback_count": self.feedback,
            "sharpe": _m.sharpe(self._equity),
            "sortino": _m.sortino(self._equity),
            "calmar": _m.calmar(self._equity),
            "max_drawdown": round(-abs(dd_abs), 6),
            "brier": _m.brier_score(self._preds, self._outs),
            "log_loss": _m.log_loss(self._preds, self._outs),
            "ece": _m.ece(self._preds, self._outs),
            "realized_edge": _m.realized_edge(self._trades_edge),
            "fill_quality": round(self.fills / self.orders, 6) if self.orders else 0.0,
            "notional": round(self.notional, 6),
        }


@dataclass
class ExperimentManager:
    """Allocates a paper-only trade-slot budget across strategy variants and
    accumulates per-variant metrics for champion/challenger reporting."""

    experiment_id: str
    variants: tuple = STRATEGY_VARIANTS
    starting_bankroll: float = 500.0
    weights: Optional[dict] = None
    bregman_first: bool = True
    aggressive: bool = False

    def __post_init__(self) -> None:
        self.variants = tuple(self.variants)
        self._m: dict = {v: VariantMetrics(v, starting_bankroll=self.starting_bankroll)
                         for v in self.variants}
        # equal weights by default (a variant absent from weights gets 1.0)
        self.weights = {v: float((self.weights or {}).get(v, 1.0)) for v in self.variants}
        self._alloc: Optional[dict] = None   # current-tick slot allocation
        self._alloc_total: int = 0           # sum of current-tick allocation
        self._opened: dict = {}              # current-tick opens per variant

    # -- paper-only budget allocation ---------------------------------------
    def allocate(self, total_slots: int, *, bregman_available: bool = False) -> dict:
        """Distribute ``total_slots`` paper trade slots across variants.

        Bregman receives its weighted share FIRST (at least one slot) when a
        certified opportunity exists; the remainder is split across the other
        variants by weight using largest-remainder rounding. The returned counts
        always SUM TO <= ``total_slots`` — the manager can never manufacture extra
        trades beyond the slot budget, so the combined book stays within the hard
        caps the RiskEngine enforces."""
        total = max(0, int(total_slots))
        result = {v: 0 for v in self.variants}
        if total <= 0:
            return result

        remaining = total
        if self.bregman_first and bregman_available and BREGMAN_VARIANT in result:
            share = self.weights[BREGMAN_VARIANT] / (sum(self.weights.values()) or 1.0)
            breg = min(total, max(1, int(round(total * share))))
            result[BREGMAN_VARIANT] = breg
            remaining -= breg

        others = [v for v in self.variants if v != BREGMAN_VARIANT]
        ow = {v: self.weights[v] for v in others}
        tw = sum(ow.values()) or 1.0
        raw = {v: remaining * ow[v] / tw for v in others}
        floor = {v: int(raw[v]) for v in others}
        rem = remaining - sum(floor.values())
        for v in sorted(others, key=lambda x: raw[x] - floor[x], reverse=True)[:max(0, rem)]:
            floor[v] += 1
        for v in others:
            result[v] = floor[v]
        return result

    def begin_tick(self, allocation: dict) -> None:
        """Set the per-tick variant slot allocation (resets per-tick open counts)."""
        self._alloc = dict(allocation or {})
        self._alloc_total = sum(int(v) for v in self._alloc.values())
        self._opened = {}

    def can_open(self, variant: str) -> bool:
        """Whether ``variant`` may open THIS tick. Always True when no allocation
        was set (experiments disabled). With an allocation: a variant opens within
        its own share first (diversity / Bregman-first priority); leftover slots
        are reclaimed (slack) up to the TOTAL tick budget so the per-variant split
        never reduces overall paper throughput below the slot budget. The hard
        risk caps (max_open_trades / exposure) always bind regardless."""
        if self._alloc is None:
            return True
        opened_v = self._opened.get(variant, 0)
        if opened_v < int(self._alloc.get(variant, 0)):
            return True
        total_opened = sum(self._opened.values())
        return total_opened < int(getattr(self, "_alloc_total", 0))

    # -- recording ----------------------------------------------------------
    def record_decision(self, variant: str, *, traded: bool) -> None:  # noqa: ARG002
        # decision-level counters live on the learner; kept for symmetry/hooks.
        return None

    def record_trade(self, variant: str, *, notional: float = 0.0) -> None:
        if variant in self._m:
            self._m[variant].record_trade(notional=notional)
            self._opened[variant] = self._opened.get(variant, 0) + 1

    def record_fill(self, variant: str, *, filled: bool) -> None:
        if variant in self._m:
            self._m[variant].record_fill(filled=filled)

    def record_feedback(self, variant: str, *, predicted_prob: float, win: bool,
                        realized_pnl: float, net_edge: float = 0.0,
                        cost: float = 0.0) -> None:
        if variant in self._m:
            self._m[variant].record_feedback(
                predicted_prob=predicted_prob, win=win, realized_pnl=realized_pnl,
                net_edge=net_edge, cost=cost)

    # -- reporting ----------------------------------------------------------
    def variant_metrics(self) -> dict:
        return {v: self._m[v].to_dict() for v in self.variants}

    def combined_trades(self) -> int:
        return sum(m.trades for m in self._m.values())

    def combined_notional(self) -> float:
        return round(sum(m.notional for m in self._m.values()), 6)

    @staticmethod
    def _score(m: dict) -> tuple:
        # rank by realized edge, then Sharpe (both higher-is-better)
        return (float(m.get("realized_edge", 0.0)), float(m.get("sharpe", 0.0)))

    def champion_challenger(self) -> dict:
        vm = self.variant_metrics()
        active = [v for v in self.variants if vm[v]["feedback_count"] > 0]
        ranking = sorted(active, key=lambda v: self._score(vm[v]), reverse=True)
        champion = ranking[0] if ranking else None
        return {
            "champion": champion,
            "challengers": ranking[1:],
            "ranking": ranking,
            "scores": {v: {"realized_edge": vm[v]["realized_edge"],
                           "sharpe": vm[v]["sharpe"],
                           "trade_count": vm[v]["trade_count"]} for v in active},
        }

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "variants": self.variant_metrics(),
            "champion_challenger": self.champion_challenger(),
            "combined_trades": self.combined_trades(),
            "combined_notional": self.combined_notional(),
            "allocation": dict(self._alloc) if self._alloc is not None else {},
        }

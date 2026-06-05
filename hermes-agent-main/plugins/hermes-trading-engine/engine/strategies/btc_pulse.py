"""BTC Pulse after-cost shadow gate (PAPER ONLY, pure, deterministic).

BTC Pulse must NOT consume risk budget while it is losing. This module is the
hard gate: the pulse may place a paper trade ONLY when every condition holds —

1. the **regime is classified** (a directional regime, not unknown/chop),
2. the **expected after-cost value is positive** (above a learned threshold),
3. the **fast-BTC / Chainlink disagreement is explainable** (within bps budget),
4. **market staleness is below threshold**,
5. **fill realism passes**, and
6. **calibration is not degrading**.

Otherwise it emits a **shadow decision** (logged, no capital) with a typed
no-trade label. A strategy-level **drawdown throttle** scales size down to zero
across a drawdown band. Bregman remains Tier 1 — BTC Pulse can never outrank an
EXECUTABLE certified Bregman arbitrage (enforced in the router).

Includes regime-specific **expectancy tables** (learned after-cost EV per regime)
and a per-regime **threshold learner** (raises the bar after losses).

Quant responsibilities
----------------------
* **Data ingestion** — read-only fast-BTC + Chainlink anchor + staleness.
* **Feature engineering** — regime classification from short-horizon returns.
* **Modeling** — regime expectancy tables + threshold learning.
* **Bregman-priority signal generation** — pulse is Tier 2 ONLY; never above
  executable certified Bregman.
* **Risk / portfolio** — after-cost gate + drawdown throttle protect the budget.
* **Backtesting / robustness** — shadow decisions yield no-trade labels for
  learning without risking capital.
* **CLOB v2 execution** — fill realism + staleness gate before any paper order.
* **Monitoring** — gate mode + reasons + expectancy surfaced every tick.
* **Compliance / security / ops** — PAPER-only; no wallet/order path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

logger = logging.getLogger("hte.strategies.btc_pulse_gate")

# Directional regimes the pulse is allowed to trade in.
REGIME_TRENDING_UP = "trending_up"
REGIME_TRENDING_DOWN = "trending_down"
REGIME_CHOP = "chop"
REGIME_UNKNOWN = "unknown"
TRADABLE_REGIMES = frozenset({REGIME_TRENDING_UP, REGIME_TRENDING_DOWN})

# Typed no-trade labels (why the pulse fell back to a shadow decision).
NT_UNKNOWN_REGIME = "unknown_regime"
NT_CHOP_REGIME = "chop_regime"
NT_NEGATIVE_AFTER_COST_EV = "negative_after_cost_ev"
NT_BELOW_LEARNED_THRESHOLD = "below_learned_threshold"
NT_DISAGREEMENT_UNEXPLAINED = "oracle_disagreement_unexplained"
NT_STALE_MARKET = "stale_market"
NT_WEAK_FILL_REALISM = "weak_fill_realism"
NT_CALIBRATION_DEGRADING = "calibration_degrading"
NT_DRAWDOWN_THROTTLE = "drawdown_throttle"

NO_TRADE_LABELS = frozenset({
    NT_UNKNOWN_REGIME, NT_CHOP_REGIME, NT_NEGATIVE_AFTER_COST_EV,
    NT_BELOW_LEARNED_THRESHOLD, NT_DISAGREEMENT_UNEXPLAINED, NT_STALE_MARKET,
    NT_WEAK_FILL_REALISM, NT_CALIBRATION_DEGRADING, NT_DRAWDOWN_THROTTLE,
})


def classify_regime(returns: Sequence[float], *, min_samples: int = 8,
                    trend_z: float = 1.0) -> str:
    """Classify the short-horizon regime from a return series (pure).

    Returns ``unknown`` when there are too few samples, ``trending_up`` /
    ``trending_down`` when the mean-return t-stat exceeds ``trend_z``, else
    ``chop``. Deterministic; no lookahead beyond the supplied window.
    """
    xs = [float(r) for r in (returns or [])]
    if len(xs) < int(min_samples):
        return REGIME_UNKNOWN
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1) if n > 1 else 0.0
    sd = var ** 0.5
    if sd <= 0:
        return REGIME_TRENDING_UP if mean > 0 else (
            REGIME_TRENDING_DOWN if mean < 0 else REGIME_CHOP)
    t_stat = mean / (sd / (n ** 0.5))
    if t_stat >= trend_z:
        return REGIME_TRENDING_UP
    if t_stat <= -trend_z:
        return REGIME_TRENDING_DOWN
    return REGIME_CHOP


@dataclass
class RegimeExpectancy:
    """Learned after-cost expectancy per regime (EWMA over resolved trades)."""

    alpha: float = 0.1
    table: dict = field(default_factory=dict)   # regime -> {"ev": float, "n": int}

    def update(self, regime: str, after_cost_pnl: float) -> None:
        try:
            pnl = float(after_cost_pnl)
        except (TypeError, ValueError):
            return
        cur = self.table.get(regime, {"ev": 0.0, "n": 0})
        n = cur["n"] + 1
        a = self.alpha if cur["n"] > 0 else 1.0
        ev = (1 - a) * cur["ev"] + a * pnl
        self.table[regime] = {"ev": round(ev, 8), "n": n}

    def expected_after_cost(self, regime: str) -> Optional[float]:
        cur = self.table.get(regime)
        return cur["ev"] if cur else None

    def to_dict(self) -> dict:
        return {k: dict(v) for k, v in self.table.items()}


@dataclass
class PulseThresholdLearner:
    """Per-regime minimum after-cost EV threshold; rises after losses (pure)."""

    base: float = 0.0
    loss_step: float = 0.002
    win_relax: float = 0.0005
    max_extra: float = 0.05
    extra: dict = field(default_factory=dict)   # regime -> extra

    def threshold(self, regime: str) -> float:
        return round(self.base + self.extra.get(regime, 0.0), 8)

    def update(self, regime: str, after_cost_pnl: float) -> None:
        try:
            pnl = float(after_cost_pnl)
        except (TypeError, ValueError):
            return
        cur = self.extra.get(regime, 0.0)
        if pnl < 0:
            cur = min(self.max_extra, cur + self.loss_step)
        elif pnl > 0:
            cur = max(0.0, cur - self.win_relax)
        self.extra[regime] = round(cur, 8)


def drawdown_throttle(drawdown: float, *, soft: float = 0.10, hard: float = 0.20) -> float:
    """Strategy-level size multiplier in [0,1] across a drawdown band (pure)."""
    dd = max(0.0, float(drawdown or 0.0))
    s = max(0.0, float(soft))
    h = max(s + 1e-9, float(hard))
    if dd <= s:
        return 1.0
    if dd >= h:
        return 0.0
    return round(1.0 - (dd - s) / (h - s), 8)


@dataclass
class PulseGateInputs:
    regime: str
    expected_after_cost_value: Optional[float]
    min_after_cost_ev: float = 0.0
    disagreement_bps: Optional[float] = None
    max_disagreement_bps: float = 150.0
    market_stale_s: Optional[float] = None
    max_stale_s: float = 120.0
    fill_realism_ok: bool = True
    calibration_degrading: bool = False
    drawdown: float = 0.0
    dd_soft: float = 0.10
    dd_hard: float = 0.20


@dataclass
class PulseGateDecision:
    mode: str               # "trade" | "shadow"
    allow_trade: bool
    throttle: float
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"mode": self.mode, "allow_trade": self.allow_trade,
                "throttle": self.throttle, "reasons": list(self.reasons)}


def evaluate_pulse_gate(inp: PulseGateInputs) -> PulseGateDecision:
    """Hard after-cost gate: return ``trade`` only when ALL conditions hold, else
    ``shadow`` with typed no-trade labels (pure + deterministic)."""
    reasons: list[str] = []

    regime = str(inp.regime or REGIME_UNKNOWN).lower()
    if regime == REGIME_CHOP:
        reasons.append(NT_CHOP_REGIME)
    elif regime not in TRADABLE_REGIMES:
        reasons.append(NT_UNKNOWN_REGIME)

    ev = inp.expected_after_cost_value
    if ev is None or float(ev) <= 0.0:
        reasons.append(NT_NEGATIVE_AFTER_COST_EV)
    elif float(ev) <= float(inp.min_after_cost_ev):
        reasons.append(NT_BELOW_LEARNED_THRESHOLD)

    if (inp.disagreement_bps is not None
            and inp.max_disagreement_bps > 0
            and float(inp.disagreement_bps) > float(inp.max_disagreement_bps)):
        reasons.append(NT_DISAGREEMENT_UNEXPLAINED)

    if (inp.market_stale_s is not None
            and float(inp.market_stale_s) > float(inp.max_stale_s)):
        reasons.append(NT_STALE_MARKET)

    if not inp.fill_realism_ok:
        reasons.append(NT_WEAK_FILL_REALISM)

    if inp.calibration_degrading:
        reasons.append(NT_CALIBRATION_DEGRADING)

    throttle = drawdown_throttle(inp.drawdown, soft=inp.dd_soft, hard=inp.dd_hard)
    if throttle <= 0.0:
        reasons.append(NT_DRAWDOWN_THROTTLE)

    allow = (not reasons) and throttle > 0.0
    decision = PulseGateDecision(
        mode=("trade" if allow else "shadow"), allow_trade=allow,
        throttle=throttle, reasons=reasons)
    if allow:
        logger.debug("pulse gate: TRADE regime=%s ev=%s throttle=%.2f", regime, ev, throttle)
    else:
        logger.info("pulse gate: SHADOW regime=%s reasons=%s", regime, reasons)
    return decision

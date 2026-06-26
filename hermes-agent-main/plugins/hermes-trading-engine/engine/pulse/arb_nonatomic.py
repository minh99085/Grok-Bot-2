"""Non-atomic (sequential) leg-fill simulation for within-window dutch-book arb.

Delegates to ``execution_realistic.simulate_buy_both_sequential`` for pre-commit leg-2 max
and unwind reporting. PAPER ONLY.
"""

from __future__ import annotations

from typing import Optional

from engine.pulse.execution_realistic import simulate_buy_both_sequential


def simulate_buy_both_nonatomic(
    up_book,
    down_book,
    *,
    target_usd: float,
    fees: float = 0.0,
    epsilon: float = 0.05,
    leg2_slippage_bps: float = 50.0,
    max_book_age_s: float = 30.0,
    now: Optional[float] = None,
) -> dict:
    """Sequential BUY-both: fill UP first, re-walk DOWN asks after impact + slippage buffer."""
    sim = simulate_buy_both_sequential(
        up_book, down_book, target_usd=target_usd, fees=fees, epsilon=epsilon,
        leg2_slippage_bps=leg2_slippage_bps, leg_order="up_first",
        max_book_age_s=max_book_age_s, now=now)
    survives = bool(sim.get("survives") or sim.get("non_atomic_pass"))
    return {
        "survives": survives,
        "reason": sim.get("reason", "fail"),
        "shares": sim.get("shares", 0.0),
        "leg1_vwap": sim.get("leg1_vwap"),
        "leg2_vwap": sim.get("leg2_vwap"),
        "leg2_stressed": True,
        "leg2_slippage_bps": leg2_slippage_bps,
        "ask_sum": sim.get("ask_sum"),
        "guaranteed_profit_usd": sim.get("guaranteed_profit_usd"),
        "pre_commit_leg2_max": sim.get("pre_commit_leg2_max"),
        "unwind_required": sim.get("unwind_required", False),
        "leg2_breach_pre_commit": sim.get("leg2_breach_pre_commit", False),
    }
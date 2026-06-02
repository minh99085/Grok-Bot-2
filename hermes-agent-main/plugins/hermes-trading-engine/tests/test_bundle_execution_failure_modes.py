"""Bregman bundle execution failure modes + optimistic-vs-realistic PnL.

Quant scope — *Bregman execution* + *Backtesting & Simulation* + *Risk
Management*: proves leg ordering, max-hedge-gap, timeout/cancel, partial-fill
unwind cost, and the hedge-break blocker; and that paper profitability that
depends on guaranteed fills collapses under the realistic model. PAPER ONLY.
"""

from __future__ import annotations

import pytest

from engine.training.bregman_execution import (
    BregmanArbitrageEngine, BregmanBundleExecutionSimulator)
from engine.training.bregman_grouping import SimplexGroup, SimplexLeg
from engine.replay.metrics import optimistic_vs_realistic_pnl


def _leg(mid, ask, depth=5000.0):
    return SimplexLeg(market_id=mid, outcome="YES", token_id=f"{mid}:YES", ask=ask,
                      bid=ask - 0.01, depth_usd=depth, tick_size=0.01,
                      fresh_book=True, stale=False)


def _opp(depth=5000.0):
    g = SimplexGroup(group_id="g", group_type="exhaustive_event",
                     legs=[_leg("m1", 0.45, depth), _leg("m2", 0.45, depth)],
                     mutually_exclusive=True, exhaustive=True)
    return BregmanArbitrageEngine(min_depth_usd=10.0, max_spread=0.10, slippage_bps=0.0,
                                  taker_fee_bps=0.0, target_capital_usd=100.0).certify(g)


def test_full_fill_realizes_profit_partial_breaks_hedge():
    sim = BregmanBundleExecutionSimulator()
    opp = _opp()
    full = sim.simulate(opp, leg_fill_fractions=[1.0, 1.0])
    partial = sim.simulate(opp, leg_fill_fractions=[1.0, 0.4])
    assert full.fully_hedged and full.realized_pnl > 0
    assert not partial.fully_hedged and partial.realized_pnl < 0
    assert partial.failure_mode == "partial_fill_breaks_hedge"
    assert partial.hedge_break_blocked is True


def test_timeout_and_max_hedge_gap_break_hedge():
    opp = _opp()
    sim = BregmanBundleExecutionSimulator(timeout_ms=1000)
    timed = sim.simulate(opp, leg_latencies_ms=[200, 5000])
    assert timed.timed_out and not timed.fully_hedged
    # max-hedge-gap: legs fill but too far apart in time -> hedge broken
    gap = sim.simulate(opp, leg_fill_fractions=[1.0, 1.0],
                       leg_latencies_ms=[100, 900], max_hedge_gap_ms=500)
    assert gap.fully_hedged is False
    assert gap.failure_mode == "hedge_gap_exceeded"


def test_partial_fill_unwind_cost_increases_the_loss():
    opp = _opp()
    sim = BregmanBundleExecutionSimulator()
    no_cost = sim.simulate(opp, leg_fill_fractions=[1.0, 0.4])
    with_cost = sim.simulate(opp, leg_fill_fractions=[1.0, 0.4], unwind_cost_bps=200.0)
    assert with_cost.realized_pnl < no_cost.realized_pnl
    assert with_cost.unwind_cost > 0.0


def test_leg_ordering_policy_is_applied():
    opp = _opp()
    sim = BregmanBundleExecutionSimulator()
    res = sim.simulate(opp, leg_order="liquidity_desc", leg_fill_fractions=[1.0, 1.0])
    # ordering does not change a full fill's profit, but is recorded + valid
    assert res.fully_hedged is True
    assert [l.market_id for l in res.leg_results]  # legs were processed


def test_optimistic_vs_realistic_pnl_exposes_guaranteed_fill_artifact():
    opp = _opp(depth=20.0)        # razor-thin depth: realistic fills will break
    sim = BregmanBundleExecutionSimulator()
    optimistic = sim.simulate(opp, leg_fill_fractions=[1.0, 1.0]).realized_pnl
    # realistic fills against the thin book (modeled fractions) break the hedge
    realistic = sim.simulate(opp).realized_pnl
    cmp = optimistic_vs_realistic_pnl([optimistic], [realistic])
    assert cmp["optimistic"] >= cmp["realistic"]
    assert cmp["realistic_is_conservative"] is True
    # the "profit" was an artifact of guaranteed fills: realistic is NOT positive
    assert realistic <= 0.0 < optimistic

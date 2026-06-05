"""Tests for after-cost execution-simulation realism (engine.simulation.fill_model).

Covers order-book depth, partial fills, latency, stale-book rejection, fees, and
Bregman multi-leg (all-or-nothing) execution feasibility.
"""

from __future__ import annotations

from engine.simulation.fill_model import (
    BookLevel,
    LatencyModel,
    LegSpec,
    OrderBook,
    ReplayFeeModel,
    simulate_bregman_execution,
    simulate_fill,
)


def _book(ts=1000, asks=((0.50, 100), (0.51, 100)), bids=((0.49, 100),)):
    return OrderBook(ts_ms=ts,
                     asks=[BookLevel(p, s) for p, s in asks],
                     bids=[BookLevel(p, s) for p, s in bids])


def test_full_fill_with_fees():
    b = _book()
    oc = simulate_fill(side="buy", size=50, book=b, decision_ts_ms=1000,
                       fee_model=ReplayFeeModel(taker_fee_bps=60),
                       latency=LatencyModel(latency_ms=100, max_book_age_ms=5000))
    assert oc.rejected is False
    assert oc.partial is False
    assert oc.filled == 50
    assert oc.avg_price == 0.50
    assert oc.fees > 0


def test_partial_fill_on_thin_book():
    b = _book(asks=((0.50, 10),))
    oc = simulate_fill(side="buy", size=100, book=b, decision_ts_ms=1000)
    assert oc.partial is True
    assert oc.filled == 10


def test_depth_walk_slippage():
    b = _book(asks=((0.50, 10), (0.60, 1000)))
    oc = simulate_fill(side="buy", size=110, book=b, decision_ts_ms=1000)
    assert oc.filled == 110
    assert oc.avg_price > 0.50      # walked into the worse level
    assert oc.slippage_frac > 0


def test_stale_book_rejected():
    b = _book(ts=0)
    oc = simulate_fill(side="buy", size=10, book=b, decision_ts_ms=10_000,
                       latency=LatencyModel(latency_ms=250, max_book_age_ms=2000))
    assert oc.rejected is True
    assert "stale_book" in oc.reason
    assert oc.filled == 0


def test_latency_counts_toward_age():
    # book age = (decision + latency) - book.ts = 1900 -> under 2000 budget (ok)
    b = _book(ts=0)
    ok = simulate_fill(side="buy", size=10, book=b, decision_ts_ms=1650,
                       latency=LatencyModel(latency_ms=250, max_book_age_ms=2000))
    assert ok.rejected is False
    # push decision later so age = 2150 -> rejected
    bad = simulate_fill(side="buy", size=10, book=b, decision_ts_ms=1900,
                        latency=LatencyModel(latency_ms=250, max_book_age_ms=2000))
    assert bad.rejected is True


def test_no_liquidity_rejected():
    b = OrderBook(ts_ms=1000, asks=[], bids=[])
    oc = simulate_fill(side="buy", size=10, book=b, decision_ts_ms=1000)
    assert oc.rejected is True
    assert oc.reason == "no_liquidity"


# --- Bregman multi-leg feasibility ------------------------------------------
def _legs(depth_a=100, depth_b=100, ts_a=1000, ts_b=1000):
    a = LegSpec(id="a", book=OrderBook(ts_ms=ts_a, asks=[BookLevel(0.40, depth_a)]))
    b = LegSpec(id="b", book=OrderBook(ts_ms=ts_b, asks=[BookLevel(0.40, depth_b)]))
    return [a, b]


def test_multileg_feasible_when_all_legs_fill():
    r = simulate_bregman_execution(_legs(), decision_ts_ms=1000, sets=50,
                                   worst_case_payoff_per_set=1.0,
                                   fee_model=ReplayFeeModel(taker_fee_bps=0))
    assert r.feasible is True
    # cost = 50*0.40 + 50*0.40 = 40 ; payoff = 50 ; edge = 10
    assert abs(r.after_cost_edge - 10.0) < 1e-6


def test_multileg_infeasible_if_one_leg_thin():
    r = simulate_bregman_execution(_legs(depth_b=5), decision_ts_ms=1000, sets=50)
    assert r.feasible is False
    assert "leg_b" in r.reason
    assert r.after_cost_edge == 0.0


def test_multileg_infeasible_if_one_leg_stale():
    # leg_a fresh (ts 9900), leg_b stale (ts 0) at decision 10_000 + 250ms latency
    r = simulate_bregman_execution(_legs(ts_a=9900, ts_b=0), decision_ts_ms=10_000,
                                   sets=10,
                                   latency=LatencyModel(latency_ms=250, max_book_age_ms=2000))
    assert r.feasible is False
    assert "leg_b" in r.reason and "stale" in r.reason


def test_multileg_serializes():
    r = simulate_bregman_execution(_legs(), decision_ts_ms=1000, sets=1)
    d = r.to_dict()
    assert d["feasible"] is True and isinstance(d["legs"], list)

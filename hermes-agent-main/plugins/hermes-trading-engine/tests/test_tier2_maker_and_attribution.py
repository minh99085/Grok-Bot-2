"""Tier-2 #5 maker/passive-fill SHADOW simulator + #6 execution attribution.
Pure, shadow-only, paper-only — never trades."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.training.maker_fill_sim import MakerFillSimulator, RESTING, FILLED, EXPIRED
from engine.training.execution_attribution import execution_attribution


# ---------------- #5 maker fill simulator ----------------

def test_passive_order_fills_when_market_crosses():
    sim = MakerFillSimulator(max_resting_ticks=20, markout_ticks=2, turnover_per_tick=1.0)
    # rest a buy at 0.49 with a tiny queue ($5 ahead), $5 size; full turnover -> clears fast
    sim.place(market_id="m1", rest_price=0.49, mid=0.50, depth_usd=5.0, size_usd=5.0, tick=0)
    assert sim.has("m1")
    # tick 1: ask drops to 0.49 (crosses our bid) -> queue consumed -> FILLED
    sim.update({"m1": {"best_ask": 0.49, "best_bid": 0.48, "mid": 0.49, "depth_usd": 5.0}},
               tick=1)
    assert sim.filled == 1
    m = sim.metrics()
    assert m["orders_filled"] == 1 and m["fill_rate"] == 1.0
    assert m["avg_spread_captured"] > 0          # captured mid(0.50) - rest(0.49)


def test_passive_order_expires_when_never_crossed():
    sim = MakerFillSimulator(max_resting_ticks=3)
    sim.place(market_id="m2", rest_price=0.40, mid=0.45, depth_usd=100.0, size_usd=5.0, tick=0)
    for t in range(1, 5):
        # ask stays well above our bid -> never crosses
        sim.update({"m2": {"best_ask": 0.50, "best_bid": 0.44, "mid": 0.45,
                           "depth_usd": 100.0}}, tick=t)
    m = sim.metrics()
    assert m["orders_expired"] == 1 and m["orders_filled"] == 0 and m["fill_rate"] == 0.0


def test_adverse_selection_markout_tracked():
    sim = MakerFillSimulator(max_resting_ticks=20, markout_ticks=2, turnover_per_tick=1.0)
    sim.place(market_id="m3", rest_price=0.50, mid=0.51, depth_usd=5.0, size_usd=5.0, tick=0)
    sim.update({"m3": {"best_ask": 0.50, "best_bid": 0.49, "mid": 0.50, "depth_usd": 5.0}},
               tick=1)                                   # fill at 0.50
    # price falls after we bought -> adverse markout (we were picked off)
    sim.update({"m3": {"best_ask": 0.46, "best_bid": 0.44, "mid": 0.45, "depth_usd": 5.0}},
               tick=2)
    sim.update({"m3": {"best_ask": 0.46, "best_bid": 0.44, "mid": 0.45, "depth_usd": 5.0}},
               tick=3)
    m = sim.metrics()
    assert m["markout_samples"] == 1 and m["avg_adverse_markout"] < 0   # mid 0.45 < rest 0.50


def test_dedup_and_shadow_only():
    sim = MakerFillSimulator()
    assert sim.place(market_id="m4", rest_price=0.5, mid=0.5, depth_usd=10, size_usd=5, tick=0)
    assert sim.place(market_id="m4", rest_price=0.5, mid=0.5, depth_usd=10, size_usd=5, tick=0) is False
    assert sim.metrics()["live_trading_enabled"] is False


# ---------------- #6 execution attribution ----------------

def _pos(*, fill, mid, qty=10.0, strategy="directional", exploration=False, source="",
         fill_quality=1.0):
    return SimpleNamespace(closed=True, entry_price=fill, executable_price_entry=fill,
                           p_market_entry=mid, qty=qty, strategy=strategy,
                           exploration=exploration, research_source=source,
                           fill_quality=fill_quality, realized_pnl=0.0)


def test_implementation_shortfall_positive_when_paying_up():
    pos = [_pos(fill=0.52, mid=0.50, qty=10.0)]      # paid 0.02 over the decision mid
    rep = execution_attribution(pos)
    assert rep["overall"]["avg_impl_shortfall"] == pytest.approx(0.02, abs=1e-9)
    assert rep["overall"]["avg_impl_shortfall_bps"] == pytest.approx(400.0, abs=1.0)
    assert rep["overall"]["total_exec_cost_usd"] == pytest.approx(0.2, abs=1e-6)


def test_attribution_buckets_and_markouts():
    pos = [_pos(fill=0.51, mid=0.50, strategy="directional", source="grok_online"),
           _pos(fill=0.61, mid=0.60, exploration=True)]
    rep = execution_attribution(pos, learner_markouts={"5m": -0.001})
    assert "directional" in rep["by_strategy"] and "exploration" in rep["by_strategy"]
    assert "grok_online" in rep["by_signal_source"]
    assert rep["readiness_only"]["trades"] == 1       # excludes exploration
    assert rep["markout_by_horizon"]["5m"] == -0.001


def test_attribution_empty():
    rep = execution_attribution([])
    assert rep["closed_trades"] == 0 and rep["overall"]["trades"] == 0

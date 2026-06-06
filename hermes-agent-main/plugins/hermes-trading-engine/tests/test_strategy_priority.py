"""Pass-4: Bregman-first strategy priority + slot/capital reservation.

Certified, realistic, after-cost-positive Bregman complete-set arbitrage gets
first claim on open slots + capital each tick; directional is secondary and
admission-gated; exploration is tertiary and cannot consume reserved capacity.
PAPER ONLY.
"""

from __future__ import annotations

from types import SimpleNamespace

from engine.markets import universe_manager as um
from engine.training import PolymarketPaperTrainer, TrainingConfig

from tests._pmtrain_helpers import clean_live_env, market

_NOW = 1_000_000.0


def _trainer(tmp_path, monkeypatch, **cfg):
    clean_live_env(monkeypatch, tmp_path)
    cfg.setdefault("max_open_trades", 8)
    return PolymarketPaperTrainer(
        TrainingConfig(mode="paper_train", **cfg), data_dir=tmp_path)


def _bregman_event(asks, *, group="elect"):
    recs = []
    for i, ask in enumerate(asks):
        raw = market(i, bid=round(ask - 0.02, 4), ask=ask, liq=20_000, depth=2000,
                     category="crypto", group=group, now=_NOW)
        raw["negRiskComplete"] = True
        recs.append(um.MarketRecord.from_raw(raw, now=_NOW))
    return recs


def _dir(market_id="d0", group_key="market:d0", event_id=None):
    return SimpleNamespace(market_id=market_id, group_key=group_key, event_id=event_id)


def _breg_pos(market_id, group_key):
    return SimpleNamespace(strategy="bregman", market_id=market_id, group_key=group_key)


# --- sort: prefer higher after-cost ROI / lower risk ------------------------

def test_bregman_quality_sort_prefers_higher_roi(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    hi = SimpleNamespace(required_capital=10.0, profit_lower_bound=2.0,
                         fill_feasibility=1.0, legs=[])      # ROI 0.20
    lo = SimpleNamespace(required_capital=10.0, profit_lower_bound=0.5,
                         fill_feasibility=1.0, legs=[])      # ROI 0.05
    ordered = sorted([lo, hi], key=t._bregman_quality_key, reverse=True)
    assert ordered[0] is hi


def test_bregman_quality_sort_prefers_lower_capital_on_roi_tie(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    cheap = SimpleNamespace(required_capital=10.0, profit_lower_bound=1.0,
                            fill_feasibility=1.0, legs=[])   # ROI 0.10, cap 10
    pricey = SimpleNamespace(required_capital=20.0, profit_lower_bound=2.0,
                             fill_feasibility=1.0, legs=[])  # ROI 0.10, cap 20
    ordered = sorted([pricey, cheap], key=t._bregman_quality_key, reverse=True)
    assert ordered[0] is cheap


# --- reservation gate -------------------------------------------------------

def test_directional_blocked_by_reserved_bregman_slot(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, max_open_trades=4, bregman_reserve_open_slots=3)
    t._bregman_certified_realistic_count = 2          # certified-realistic exists -> reserve held
    t.open_positions = lambda: [_breg_pos("b0", "event:e")]   # 1 slot used
    t._begin_directional_phase(4, 1)
    assert t._dir_reserved_slots == 3                 # held (not released)
    ok, reason = t._directional_admit(_dir())
    assert not ok and reason == "bregman_reservation"
    assert t.priority_metrics["directional_trades_blocked_by_bregman_reservation"] == 1


def test_directional_uses_released_slot_when_no_bregman(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, max_open_trades=4, bregman_reserve_open_slots=3)
    t._bregman_certified_realistic_count = 0          # no certified-realistic Bregman
    t.open_positions = lambda: []
    t._begin_directional_phase(4, 0)
    assert t._dir_reserved_slots == 0                 # released to directional
    assert t.priority_metrics["unused_bregman_slots_released_to_directional"] == 3
    ok, reason = t._directional_admit(_dir())
    assert ok and reason == ""


def test_directional_global_capacity_stops_loop(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, max_open_trades=2, bregman_reserve_open_slots=0)
    t._bregman_certified_realistic_count = 0
    t.open_positions = lambda: [_breg_pos("b0", "event:e"), _breg_pos("b1", "event:e")]
    t._begin_directional_phase(0, 2)
    ok, reason = t._directional_admit(_dir())
    assert not ok and reason == "global_capacity"


# --- directional/Bregman collision ------------------------------------------

def test_directional_blocked_on_bregman_market(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, max_open_trades=8)
    t._bregman_certified_realistic_count = 0
    t.open_positions = lambda: [_breg_pos("m5", "event:elect")]
    t._begin_directional_phase(8, 1)
    ok, reason = t._directional_admit(_dir(market_id="m5", group_key="market:m5"))
    assert not ok and reason == "bregman_market_collision"
    assert t.priority_metrics["directional_trades_blocked_by_bregman_market_collision"] == 1


def test_directional_blocked_on_bregman_event(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, max_open_trades=8)
    t._bregman_certified_realistic_count = 0
    t.open_positions = lambda: [_breg_pos("m5", "event:elect")]
    t._begin_directional_phase(8, 1)
    ok, reason = t._directional_admit(_dir(market_id="dX", group_key="event:elect"))
    assert not ok and reason == "bregman_event_collision"
    assert t.priority_metrics["directional_trades_blocked_by_bregman_event_collision"] == 1


def test_directional_allowed_when_no_collision_and_slots(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, max_open_trades=8)
    t._bregman_certified_realistic_count = 0
    t.open_positions = lambda: [_breg_pos("m5", "event:elect")]
    t._begin_directional_phase(8, 1)
    ok, reason = t._directional_admit(_dir(market_id="other", group_key="event:other"))
    assert ok and reason == ""


# --- exploration cannot consume reserved Bregman capacity -------------------

def test_exploration_blocked_from_reserved_capacity(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._bregman_reserve_active = True
    t.priority_metrics = {"exploration_blocked_from_reserved_bregman_capacity": 0}
    rec = um.MarketRecord.from_raw(market(0, now=_NOW), now=_NOW)
    est = SimpleNamespace(market_id="m0", fresh_book=True, spread=0.02, ambiguity_score=0.05,
                          evidence_score=1.0, liquidity_usd=20_000.0, p_market_mid=0.40,
                          p_market_bid=0.38, bregman_group_id="", confidence=0.9,
                          research_source="research", calibrated_probability=None)
    edge = SimpleNamespace(outcome="YES", executable_price=0.40, p_final=0.6, net_edge=0.08)
    res = t._open(rec, est, edge, SimpleNamespace(diagnostics_id="d"), exploratory=True)
    assert res["opened"] is False
    assert res["reason"] == "exploration_blocked_bregman_reserved"
    assert t.priority_metrics["exploration_blocked_from_reserved_bregman_capacity"] == 1


def test_exploration_allowed_when_no_reserve(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._bregman_reserve_active = False                 # no Bregman reserve this tick
    rec = um.MarketRecord.from_raw(market(0, now=_NOW), now=_NOW)
    est = SimpleNamespace(market_id="m0", fresh_book=True, spread=0.02, ambiguity_score=0.05,
                          evidence_score=1.0, liquidity_usd=20_000.0, p_market_mid=0.40,
                          p_market_bid=0.38, bregman_group_id="", confidence=0.9,
                          research_source="research", calibrated_probability=None)
    edge = SimpleNamespace(outcome="YES", executable_price=0.40, p_final=0.6, net_edge=0.08)
    res = t._open(rec, est, edge, SimpleNamespace(diagnostics_id="d"), exploratory=True)
    # not blocked by the Bregman-reservation gate (may still open or hit other gates)
    assert res.get("reason") != "exploration_blocked_bregman_reserved"


# --- integration: Bregman opens before directional + metrics ----------------

def test_bregman_opens_before_directional_and_metrics(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    opened = t._run_bregman(_bregman_event([0.28, 0.30, 0.30]), _NOW)
    assert opened == 1
    t._begin_directional_phase(8, opened)
    rep = t.strategy_priority_report()
    assert rep["bregman_priority_enabled"] is True
    assert rep["bregman_evaluated_before_directional"] is True
    assert rep["directional_consumed_capacity_before_bregman"] is False
    assert rep["bregman_opened_before_directional_count"] == 1
    assert rep["bregman_certified_before_directional_count"] >= 1
    assert rep["directional_secondary_after_bregman"] is True
    assert rep["exploration_tertiary_after_exploit"] is True
    assert rep["paper_realism_enforced"] is True
    # reserve held because a certified-realistic opp existed this tick
    assert rep["bregman_reserved_slots"] == 3


def test_strategy_priority_metrics_emitted(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._bregman_certified_realistic_count = 0
    t._begin_directional_phase(8, 0)
    rep = t.strategy_priority_report()
    for key in ("bregman_priority_enabled", "bregman_evaluated_before_directional",
                "bregman_reserved_slots", "bregman_reserved_capital_usd",
                "bregman_certified_before_directional_count",
                "bregman_opened_before_directional_count",
                "directional_slots_before_bregman", "directional_slots_after_bregman",
                "directional_trades_blocked_by_bregman_reservation",
                "directional_trades_blocked_by_bregman_market_collision",
                "directional_trades_blocked_by_bregman_event_collision",
                "unused_bregman_slots_released_to_directional",
                "unused_bregman_capital_released_to_directional",
                "exploration_blocked_from_reserved_bregman_capacity"):
        assert key in rep

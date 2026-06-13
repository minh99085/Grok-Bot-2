"""Accelerated discovery / learning mode (PAPER ONLY).

Proves the mode scales OBSERVATION + LEARNING throughput (scan breadth, candidates,
shadow/no-trade labels, near-miss + diagnostics capture, hydration coverage) while
leaving EVERY execution gate, paper-realism flag, and live-trading control IDENTICAL to
the default. A higher trade count can never be faked: realistic/certified/exploration/
shadow/no-trade/near-miss buckets stay separated.
"""

import time

from engine.training import PolymarketPaperTrainer, TrainingConfig
from engine.markets import universe_manager as um
from tests._pmtrain_helpers import clean_live_env, market

_NOW = 1_796_000_000.0

# Execution gates / realism / live controls that accelerated discovery MUST NOT touch.
FROZEN_GATES = (
    "min_depth_at_price", "max_spread", "bregman_max_book_age_sec",
    "bregman_min_after_cost_profit_usd", "bregman_min_after_cost_roi", "bregman_min_roi",
    "max_ambiguity_score", "max_event_exposure_usd", "max_category_exposure_usd",
    "max_bregman_bundle_exposure_usd", "reject_on_stale_book", "require_executable_ask",
    "reject_missing_ask", "reject_offline_stub_fills", "allow_pm_reference_price_fills",
    "bregman_allow_reference_fills",
)
# Discovery / learning knobs the mode is ALLOWED to scale up.
DISCOVERY_KNOBS = (
    "bregman_discovery_limit", "bregman_shadow_labels_per_tick", "bregman_top_near_misses",
    "bregman_near_miss_store_cap", "bregman_clob_hydration_max_groups", "shortlist_limit",
)


def _base(**kw):
    return TrainingConfig(mode="paper_train", paper_trade_pressure_enabled=False, **kw)


def test_accel_does_not_change_any_execution_gate():
    base = _base()
    accel = _base(accelerated_discovery_enabled=True)
    for g in FROZEN_GATES:
        assert getattr(base, g) == getattr(accel, g), f"accel changed gate {g}!"


def test_accel_scales_discovery_knobs_up():
    base = _base()
    accel = _base(accelerated_discovery_enabled=True)
    for k in DISCOVERY_KNOBS:
        assert getattr(accel, k) >= getattr(base, k), f"{k} not scaled up"
    # at least these are strictly higher
    assert accel.bregman_discovery_limit > base.bregman_discovery_limit
    assert accel.bregman_shadow_labels_per_tick > base.bregman_shadow_labels_per_tick
    assert accel.bregman_clob_hydration_max_groups > base.bregman_clob_hydration_max_groups
    # faster ticks => more throughput per hour
    assert accel.scan_interval_seconds < base.scan_interval_seconds


def test_accel_default_off_and_env_on(monkeypatch):
    assert _base().accelerated_discovery_enabled is False
    monkeypatch.setenv("HERMES_ACCELERATED_DISCOVERY", "1")
    assert TrainingConfig.from_env().accelerated_discovery_enabled is True
    monkeypatch.delenv("HERMES_ACCELERATED_DISCOVERY", raising=False)
    assert TrainingConfig.from_env().accelerated_discovery_enabled is False


# --------------------------------------------------------------------------- #
# runtime telemetry through the trainer
# --------------------------------------------------------------------------- #
def _trainer(tmp_path, monkeypatch, **cfg):
    clean_live_env(monkeypatch, tmp_path)
    return PolymarketPaperTrainer(
        TrainingConfig(mode="paper_train", max_open_trades=8, **cfg), data_dir=tmp_path)


def _recs(n=6):
    return [um.MarketRecord.from_raw(market(i, group=None, now=_NOW), now=_NOW)
            for i in range(n)]


def test_accel_telemetry_fields_present_and_active(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, accelerated_discovery_enabled=True)
    t.scan_bregman(_recs(), _NOW)
    m = t.bregman_exec_metrics
    assert m["accelerated_discovery_enabled"] is True
    assert m["markets_scanned_per_tick"] == 6
    assert m["candidates_evaluated_per_tick"] >= 1
    assert m["shadow_labels_per_tick"] >= 150           # accel-scaled
    assert "no_trade_labels_per_tick" in m
    assert m["bregman_diagnostics_records_written"] >= 1
    assert isinstance(m["top_near_miss_edges_after_cost"], list)
    assert isinstance(m["top_bregman_rejection_reasons"], list)
    # accel knob proof carries the scaled discovery limits
    knobs = m["accelerated_discovery_knobs"]
    assert knobs["bregman_discovery_limit"] >= 3000
    assert knobs["bregman_shadow_labels_per_tick"] >= 150
    assert knobs["scan_interval_seconds"] <= 20.0


def test_report_buckets_are_separated(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, accelerated_discovery_enabled=True)
    t.scan_bregman(_recs(), _NOW)
    b = t.bregman_exec_metrics["report_buckets"]
    for key in ("realistic_executable_trades", "bregman_certified_bundles",
                "directional_exploit_trades", "shadow_exploration", "no_trade_labels",
                "near_miss_rejects", "paper_relaxed_exploration_trades"):
        assert key in b
    # with no real opportunities, NOTHING counts as a realistic/certified trade
    assert b["realistic_executable_trades"] == 0
    assert b["bregman_certified_bundles"] == 0


def test_accel_increases_diagnostics_vs_default_same_gates(tmp_path, monkeypatch):
    # identical inputs; accel produces >= the diagnostics throughput of default, and the
    # certified/realistic counts are unchanged (gates identical => same trade outcome).
    base = _trainer(tmp_path / "b", monkeypatch, accelerated_discovery_enabled=False,
                    paper_trade_pressure_enabled=False)
    accel = _trainer(tmp_path / "a", monkeypatch, accelerated_discovery_enabled=True,
                     paper_trade_pressure_enabled=False)
    base.scan_bregman(_recs(), _NOW)
    accel.scan_bregman(_recs(), _NOW)
    assert (accel.bregman_exec_metrics["shadow_labels_per_tick"]
            >= base.bregman_exec_metrics["shadow_labels_per_tick"])
    # certified opportunities identical (gates not loosened => same certification)
    assert (accel.bregman_exec_metrics["certified_opportunities"]
            == base.bregman_exec_metrics["certified_opportunities"] == 0)


def test_live_trading_remains_disabled_under_accel(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, accelerated_discovery_enabled=True)
    # the engine has no live path; mode stays paper_train and accel does not flip it
    assert t.mode == "paper_train"
    assert t.cfg.accelerated_discovery_enabled is True

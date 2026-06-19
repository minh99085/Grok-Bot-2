"""Tier-3 governance/ops: alpha attribution, model registry/reproducibility, SLO monitor.
All pure, read-only, paper-only."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.training.alpha_attribution import attribute_pnl
from engine.training.model_registry import build_snapshot, ModelRegistry
from engine.training.slo_monitor import evaluate_slos, OK, WARN, BREACH


def _pos(pnl, *, exploration=False, strategy="directional", source="", chainlink=False,
         cost=5.0):
    return SimpleNamespace(closed=True, realized_pnl=pnl, exploration=exploration,
                           strategy=strategy, research_source=source,
                           chainlink_linked=chainlink, cost=cost)


# ---------------- alpha attribution ----------------

def test_attribution_buckets_and_totals():
    pos = [_pos(2.0, strategy="directional", source="grok_online"),
           _pos(-1.0, exploration=True),
           _pos(3.0, strategy="bregman"),
           _pos(-0.5, chainlink=True)]
    rep = attribute_pnl(pos)
    assert rep["closed_trades"] == 4
    assert rep["overall"]["total_pnl"] == 3.5
    assert set(rep["by_strategy"]) == {"directional", "exploration", "bregman"}
    assert set(rep["by_signal_source"]) == {"grok_research", "model_market", "chainlink"}
    # readiness excludes the exploration probe
    assert rep["readiness_only"]["trades"] == 3
    assert rep["best_strategy"] == "bregman"


def test_attribution_empty():
    rep = attribute_pnl([])
    assert rep["closed_trades"] == 0 and rep["overall"]["trades"] == 0


# ---------------- model registry / reproducibility ----------------

def _cfg():
    return SimpleNamespace(mode="paper_train", min_net_edge=0.005, max_spread=0.12,
                           portfolio_risk_enabled=True, size_aware_depth_enabled=True)


class _Learner:
    def __init__(self):
        self.prob_buckets = {"5": {"n": 10, "wins": 5, "sum_pred": 5.0}}
        self.categories = {"crypto": {"n": 10, "reliability": 0.5}}
        self.closed = 10
        self.warm_start_samples = 1245

    def calibration_error(self):
        return 0.04


def test_snapshot_is_content_addressed_and_reproducible():
    learner = _Learner()
    s1 = build_snapshot(cfg=_cfg(), learner=learner, commit="abc123", seed=42,
                        warm_start_samples=1245)
    s2 = build_snapshot(cfg=_cfg(), learner=_Learner(), commit="abc123", seed=42,
                        warm_start_samples=1245)
    assert s1["version_id"] == s2["version_id"]          # same stack -> same version
    assert s1["reproducible"] is True and s1["warm_start_samples"] == 1245
    assert s1["live_trading_enabled"] is False


def test_snapshot_version_changes_with_config():
    learner = _Learner()
    base = build_snapshot(cfg=_cfg(), learner=learner, commit="c", seed=42)
    cfg2 = _cfg(); cfg2.min_net_edge = 0.05
    changed = build_snapshot(cfg=cfg2, learner=learner, commit="c", seed=42)
    assert base["version_id"] != changed["version_id"]
    assert base["config_hash"] != changed["config_hash"]


def test_registry_champion_compare():
    reg = ModelRegistry()
    champ = build_snapshot(cfg=_cfg(), learner=_Learner(), commit="c", seed=42)
    reg.register_champion(champ)
    cfg2 = _cfg(); cfg2.max_spread = 0.20
    challenger = build_snapshot(cfg=cfg2, learner=_Learner(), commit="c", seed=42)
    diff = reg.compare(challenger)
    assert diff["changed"] is True and diff["config_changed"] is True


# ---------------- SLO monitor ----------------

def test_slo_all_ok():
    rep = evaluate_slos(calibration_error=0.04, training_file_age_s=120.0,
                        chainlink_stale=False, btc_stale=False, fill_quality=1.0)
    assert rep["status"] == OK and not rep["breaches"] and not rep["warnings"]


def test_slo_breach_on_stale_training_loop():
    rep = evaluate_slos(training_file_age_s=400.0, training_file_max_age_s=300.0)
    assert rep["status"] == BREACH and "training_loop_fresh" in rep["breaches"]


def test_slo_warn_then_breach_on_calibration_drift():
    warn = evaluate_slos(calibration_error=0.10, baseline_calibration_error=0.04,
                         training_file_age_s=10.0)
    assert "calibration_drift" in warn["warnings"] or "calibration_drift" in warn["breaches"]


def test_slo_breach_on_kill_switch_and_bregman_fp():
    rep = evaluate_slos(training_file_age_s=10.0, kill_switch_downgraded=True,
                        bregman_false_positive_rate=0.01)
    assert rep["status"] == BREACH
    assert "not_kill_switch_downgraded" in rep["breaches"]
    assert "bregman_zero_false_positives" in rep["breaches"]

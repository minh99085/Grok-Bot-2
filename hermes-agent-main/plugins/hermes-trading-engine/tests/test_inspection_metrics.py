"""Tests for inspection feature extraction, scorecard, and baseline comparison."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import inspection_metrics as m  # noqa: E402


def _status():
    return {
        "mode": "paper",
        "runtime_seconds": 3600,
        "pnl": {"open_positions": 2, "trades_closed": 40, "equity": 510.0,
                "total_pnl": 10.0, "win_rate": 0.55},
        "scan_metrics": {"scanned": 1000, "kept": 80},
        "safety": {"ok": True, "live_detected": False},
        "monitoring": {"bregman_opportunities": 12, "certified_bregman_profit": 3.2,
                       "brier": 0.21},
        "training_campaign": {"evidence": {"paper_trades": 40, "bregman_candidates": 12,
                                           "bregman_certified": 5,
                                           "after_cost_expectancy": 0.8}},
        "btc_pulse": {"btc_pulse_enabled": True, "btc_pulse_frozen": False,
                      "btc_pulse_oracle_required": True, "btc_pulse_paper_trades": 9,
                      "btc_pulse_after_cost_pnl": 1.5},
        "news": {"news_scanner_enabled": True, "news_provider_mode": "offline_cache",
                 "news_items_fetched": 100, "news_items_used": 30},
        "btc_fast_price": {"enabled": True, "valid": True, "age_seconds": 2.0,
                           "disagreement_vs_chainlink_bps": 5.0},
        "campaign_safety": {"realistic_fill_enabled": True, "clean_label_guard_enabled": True},
    }


def _api():
    return {"chainlink_status": {"available": True,
                                 "btc_usd": {"enabled": True, "valid": True,
                                             "stale": False, "age_seconds": 30, "price": 65000}}}


def test_extract_features_maps_core_fields():
    feats = m.extract_features(_status(), _api(), {"present": True, "passing": True})
    assert feats["paper_training_running"] is True
    assert feats["runtime_minutes"] == 60.0
    assert feats["scanned_markets"] == 1000
    assert feats["equity"] == 510.0
    assert feats["chainlink_enabled"] is True
    assert feats["chainlink_valid"] is True
    assert feats["btc_fast_price_enabled"] is True
    assert feats["btc_pulse_oracle_gate_active"] is True
    assert feats["news_scanner_enabled"] is True
    assert feats["tests_passing"] is True


def test_extract_features_empty_status_is_all_unknown():
    feats = m.extract_features({}, {}, {})
    assert feats["equity"] is None
    assert feats["chainlink_enabled"] in (None, False)
    assert feats["scanned_markets"] is None


def test_scorecard_is_deterministic():
    feats = m.extract_features(_status(), _api(), {"present": True, "passing": True})
    safety = {"status": "OK", "critical": False, "warn": False}
    tests = {"present": True, "passing": True}
    obs = {"artifacts_found": True, "logs_collected": True, "api_ok": True}
    s1 = m.compute_scorecard(feats, safety, tests, True, {"available": False}, obs)
    s2 = m.compute_scorecard(feats, safety, tests, True, {"available": False}, obs)
    assert s1 == s2
    assert 0 <= s1["score"] <= 100
    assert s1["components"]["safety"]["score"] == 25
    assert s1["components"]["tests"]["score"] == 15


def test_scorecard_zero_safety_when_critical():
    feats = m.extract_features(_status(), _api(), {"present": True, "passing": True})
    s = m.compute_scorecard(feats, {"status": "CRITICAL", "critical": True},
                            {"present": True, "passing": True}, True,
                            {"available": False}, {})
    assert s["components"]["safety"]["score"] == 0


def test_compare_baseline_detects_regression():
    base_feats = m.extract_features(_status(), _api(), {})
    cur = dict(base_feats)
    cur["after_cost_pnl"] = base_feats["after_cost_pnl"] - 1.0  # material drop
    cur["equity"] = base_feats["equity"] - 100.0
    comp = m.compare_baseline(cur, {"features": base_feats})
    assert comp["available"] is True
    assert comp["regression"] is True
    assert "after_cost_pnl" in comp["degraded"]


def test_compare_baseline_detects_improvement():
    base_feats = m.extract_features(_status(), _api(), {})
    cur = dict(base_feats)
    cur["after_cost_pnl"] = base_feats["after_cost_pnl"] + 2.0
    cur["equity"] = base_feats["equity"] + 50.0
    comp = m.compare_baseline(cur, {"features": base_feats})
    assert comp["regression"] is False
    assert "after_cost_pnl" in comp["improved"]


def test_compare_baseline_none_is_current_state_only():
    feats = m.extract_features(_status(), _api(), {})
    comp = m.compare_baseline(feats, None)
    assert comp["available"] is False
    assert comp["regression"] is False


def test_tests_passing_regression_flag():
    base = {"features": {"tests_passing": True}}
    comp = m.compare_baseline({"tests_passing": False}, base)
    assert comp["regression"] is True
    assert comp["metrics"]["tests_passing"]["direction"] == "DEGRADED"


def test_detect_missing_features_flags_gaps():
    feats = m.extract_features({}, {}, {"present": False})
    missing = m.detect_missing_features(feats, {}, {"present": False})
    flagged = {x["feature"] for x in missing}
    assert "chainlink" in flagged
    assert "btc_fast_price" in flagged
    assert "tests" in flagged


def test_detect_missing_features_healthy_has_fewer():
    feats = m.extract_features(_status(), _api(), {"present": True, "passing": True})
    missing = m.detect_missing_features(feats, _api(), {"present": True, "passing": True})
    flagged = {x["feature"] for x in missing}
    assert "chainlink" not in flagged
    assert "btc_fast_price" not in flagged

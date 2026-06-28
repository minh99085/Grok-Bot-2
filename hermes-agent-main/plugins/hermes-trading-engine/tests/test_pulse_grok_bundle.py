"""Grok decision bundle v1.3 helpers — per-market stats, gate funnel, 5-TF TV trend."""

from __future__ import annotations

from engine.pulse.grok_bundle import (compact_tv_learning, gate_funnel_top, grok_task_for_window,
                                      order_bundle_for_grok, serialize_bundle_for_grok,
                                      tv_trend_snapshot)


def test_gate_funnel_top_sorted():
    funnel = gate_funnel_top({
        "context_gate": 100,
        "down_bias_gate": 200,
        "grok_decider": 5,
        "execution_gate": 50,
    }, top_n=3)
    assert funnel["total_rejected"] == 355
    assert funnel["top_blockers"][0] == {"stage": "down_bias_gate", "count": 200}
    assert funnel["top_blockers"][1]["stage"] == "context_gate"


def test_tv_trend_snapshot_all_five_charts():
    mtf = {
        "mtf_timeframes": ["4", "5", "10", "13", "15"],
        "mtf_count": 5,
        "tf_4m_dir": "DOWN",
        "tf_5m_dir": "UP",
        "tf_10m_dir": "UP",
        "tf_13m_dir": "UP",
        "tf_15m_dir": "UP",
        "tf_4m_age_s": 45.0,
        "tf_5m_age_s": 120.0,
        "tf_10m_age_s": 200.0,
        "tf_13m_age_s": 250.0,
        "tf_15m_age_s": 300.0,
        "confirm_5tf": "partial_up_5tf",
        "confirm_mtf": "partial_up_mtf",
        "direction_5tf": "UP",
        "direction_mtf": "UP",
        "trend_fresh_count": 5,
        "trend_by_tf": {"4": "DOWN", "5": "UP", "10": "UP", "13": "UP", "15": "UP"},
    }
    by_tf = {
        "BTCUSD@4": {"direction": "DOWN", "strength": 0.61},
        "BTCUSD@5": {"direction": "UP", "strength": 0.75},
        "BTCUSD@10": {"direction": "UP", "strength": 0.79},
        "BTCUSD@13": {"direction": "UP", "strength": 0.80},
        "BTCUSD@15": {"direction": "UP", "strength": 0.82},
    }
    snap = tv_trend_snapshot(mtf=mtf, latest_by_timeframe=by_tf, feature_symbol="BTCUSD")
    assert snap["confirm_5tf"] == "partial_up_5tf"
    assert snap["confirm_mtf"] == "partial_up_mtf"
    assert snap["direction_5tf"] == "UP"
    assert snap["charts"]["10m"]["direction"] == "UP"
    assert snap["charts"]["10m"]["strength"] == 0.79
    assert snap["charts"]["10m"]["fresh"] is True
    assert snap["charts"]["4m"]["age_s"] == 45.0


def test_tv_trend_stale_fallback():
    mtf = {"mtf_timeframes": ["4", "5", "10", "13", "15"], "mtf_count": 5,
           "tf_5m_dir": None, "tf_10m_dir": "UP", "tf_10m_age_s": 90.0,
           "confirm_5tf": "single_tf", "confirm_mtf": "single_tf",
           "direction_5tf": "UP", "direction_mtf": "UP", "trend_fresh_count": 1}
    by_tf = {"BTCUSD@5": {"direction": "DOWN", "strength": 0.55}}
    snap = tv_trend_snapshot(mtf=mtf, latest_by_timeframe=by_tf)
    assert snap["charts"]["5m"]["direction"] == "DOWN"
    assert snap["charts"]["5m"]["fresh"] is False
    assert snap["charts"]["5m"]["stale_stored_dir"] == "DOWN"


def test_tv_trend_includes_signal_level():
    mtf = {"mtf_timeframes": ["2", "3", "4"], "mtf_count": 3,
           "tf_2m_dir": "UP", "tf_2m_age_s": 10.0, "confirm_mtf": "confirmed_up_mtf",
           "trend_fresh_count": 1}
    by_tf = {"BTCUSD@2": {"direction": "UP", "strength": 0.8, "signal_level": "UP_STRONG"}}
    snap = tv_trend_snapshot(mtf=mtf, latest_by_timeframe=by_tf)
    assert snap["charts"]["2m"]["signal_level"] == "UP_STRONG"


def test_grok_task_15m_entry_band():
    task = grok_task_for_window(series_label="15m", window_seconds=900, ttc_s=500.0)
    assert task["in_entry_band"] is True
    assert task["horizon"] == "15m_chainlink_window"


def test_bundle_priority_ordering():
    b = order_bundle_for_grok({
        "lessons": [1], "tradingview_trend": {"x": 1}, "cex_lead_mispricing": {"d": 0.1},
    })
    keys = list(b.keys())
    assert keys.index("tradingview_trend") < keys.index("lessons")
    assert keys.index("cex_lead_mispricing") < keys.index("lessons")


def test_compact_tv_learning():
    out = compact_tv_learning({
        "settled_with_signal": 40,
        "best_signal_levels": [{"signal_level": "UP_STRONG", "win_rate": 0.7}],
        "by_signal_level": {"UP_STRONG": {"n": 10}, "FLAT": {"n": 5}},
    })
    assert out["best_signal_levels"][0]["signal_level"] == "UP_STRONG"
    assert "UP_STRONG" in out["by_signal_level"]


def test_serialize_bundle_truncates_tail():
    big = {"tradingview_trend": {"a": 1}, "lessons": ["x" * 5000]}
    ordered = order_bundle_for_grok(big)
    raw = serialize_bundle_for_grok(ordered, max_chars=200)
    assert "tradingview_trend" in raw
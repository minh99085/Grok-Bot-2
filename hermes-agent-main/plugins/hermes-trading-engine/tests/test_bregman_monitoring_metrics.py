"""Bregman arbitrage monitoring metrics + false-positive kill-switch.

Quant scope — *Bregman arbitrage monitoring* + *Live Monitoring*: proves the
monitoring layer surfaces Bregman opportunities, certified profit, and the
false-positive rate, and that a high Bregman false-positive rate trips the
kill-switch. PAPER ONLY.
"""

from __future__ import annotations

import pytest

from engine.training.monitoring import (KillSwitchThresholds, bregman_monitoring,
                                        evaluate_kill_switch)


def _summary(**kw):
    base = {"enabled": True, "execution_enabled": True, "opportunity_count": 5,
            "sets_opened": 3, "rejected": 1,
            "last_scan_metrics": {"opportunity_count": 2, "certified_profit": 1.4,
                                  "false_positive_rate": 0.0, "certified_count": 2}}
    base.update(kw)
    return base


def test_bregman_monitoring_extracts_core_fields():
    m = bregman_monitoring(_summary())
    assert m["opportunities"] == 5
    assert m["certified_profit"] == pytest.approx(1.4)
    assert m["false_positive_rate"] == pytest.approx(0.0)
    assert m["sets_opened"] == 3


def test_bregman_monitoring_handles_empty_summary():
    m = bregman_monitoring({})
    assert m["opportunities"] == 0
    assert m["certified_profit"] == 0.0
    assert m["false_positive_rate"] == 0.0


def test_high_bregman_false_positive_rate_trips_kill_switch():
    summary = _summary(last_scan_metrics={"opportunity_count": 4, "certified_profit": 0.1,
                                          "false_positive_rate": 0.5})
    m = bregman_monitoring(summary)
    assert m["false_positive_rate"] == pytest.approx(0.5)
    dash = {"calibration_error": 0.05, "brier_trend": 0.0, "drawdown": -1.0,
            "loss_streak": 0, "label_suppression_rate": 0.0, "ambiguous_rate": 0.0,
            "stale_data_rejection_rate": 0.0, "partial_fill_rate": 0.0,
            "bregman_false_positive_rate": m["false_positive_rate"], "avg_spread": 0.02,
            "learner_rollbacks": 0, "samples": 50}
    ks = evaluate_kill_switch(dash, KillSwitchThresholds(), aggressive=True)
    assert "bregman_false_positives" in ks["triggered"]
    assert ks["should_downgrade"] is True


def test_clean_bregman_does_not_trip_kill_switch():
    m = bregman_monitoring(_summary())
    dash = {"calibration_error": 0.05, "brier_trend": 0.0, "drawdown": -1.0,
            "loss_streak": 0, "label_suppression_rate": 0.0, "ambiguous_rate": 0.0,
            "stale_data_rejection_rate": 0.0, "partial_fill_rate": 0.0,
            "bregman_false_positive_rate": m["false_positive_rate"], "avg_spread": 0.02,
            "learner_rollbacks": 0}
    ks = evaluate_kill_switch(dash, KillSwitchThresholds(), aggressive=True)
    assert "bregman_false_positives" not in ks["triggered"]

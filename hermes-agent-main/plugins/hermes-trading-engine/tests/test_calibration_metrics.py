"""Tests for calibration + bucket metrics computed from the canonical ledger."""

from __future__ import annotations

from engine.ledger import CanonicalLedger


def _led_with_preds(pairs):
    led = CanonicalLedger(starting_balance=100.0)
    for i, (p, y) in enumerate(pairs):
        led.record(ts=float(i), market=f"m{i}", strategy="bregman", traded=True,
                   predicted_prob=p, outcome=y, after_cost_pnl=(1.0 if y else -1.0),
                   calibration_bucket=min(9, int(p * 10)))
    return led


def test_brier_perfect_predictions_is_low():
    led = _led_with_preds([(0.99, 1), (0.01, 0), (0.98, 1), (0.02, 0)])
    cal = led.calibration()
    assert cal["brier"] is not None and cal["brier"] < 0.05
    assert cal["n"] == 4


def test_brier_bad_predictions_is_high():
    led = _led_with_preds([(0.99, 0), (0.01, 1), (0.98, 0)])
    assert led.calibration()["brier"] > 0.5


def test_ece_present_and_bounded():
    led = _led_with_preds([(0.7, 1), (0.7, 0), (0.3, 0), (0.3, 1), (0.9, 1)])
    ece = led.calibration()["ece"]
    assert ece is not None and 0.0 <= ece <= 1.0


def test_calibration_none_without_pairs():
    led = CanonicalLedger(starting_balance=100.0)
    led.record(ts=1.0, market="m", strategy="bregman", traded=True, after_cost_pnl=1.0)
    cal = led.calibration()
    assert cal["brier"] is None and cal["ece"] is None and cal["n"] == 0


def test_confidence_bucket_pnl_groups_by_bucket():
    led = _led_with_preds([(0.92, 1), (0.95, 1), (0.15, 0)])
    b = led.confidence_bucket_pnl()
    assert b[9]["n"] == 2 and b[9]["after_cost_pnl"] == 2.0
    assert b[9]["hit_rate"] == 1.0
    assert b[1]["n"] == 1


def test_no_trade_bucket_performance():
    led = CanonicalLedger(starting_balance=100.0)
    led.record(ts=1.0, market="m1", strategy="model", traded=False, kind="decision",
               gross_ev=-0.02, fee_adjusted_ev=-0.03)            # correctly skipped
    led.record(ts=2.0, market="m2", strategy="model", traded=False, kind="decision",
               gross_ev=0.05, fee_adjusted_ev=0.04)              # arguably missed
    nt = led.no_trade_bucket()
    assert nt["n"] == 2
    assert nt["correctly_skipped"] == 0.5


def test_risk_metrics_from_ledger_returns():
    led = _led_with_preds([(0.6, 1), (0.6, 1), (0.4, 0), (0.6, 1), (0.4, 0)])
    rm = led.risk_metrics()
    assert rm["n_returns"] == 5
    assert "sharpe" in rm and "cvar" in rm

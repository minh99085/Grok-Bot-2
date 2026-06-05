"""Tests for the canonical paper ledger: schema, equity, attribution, risk."""

from __future__ import annotations

from engine.ledger import CanonicalLedger, LedgerEntry


_REQUIRED_FIELDS = (
    "ts", "market", "strategy", "signal_version", "bregman_certificate_id",
    "gross_ev", "fee_adjusted_ev", "fill_realism_status", "order_book_depth",
    "filled_qty", "rejected_qty", "fees", "slippage", "realized_pnl",
    "unrealized_pnl", "after_cost_pnl", "is_exploration", "calibration_bucket",
    "risk_throttle_state",
)


def test_entry_has_all_required_fields():
    e = LedgerEntry(ts=1.0, market="m", strategy="bregman")
    d = e.to_dict()
    for f in _REQUIRED_FIELDS:
        assert f in d, f


def _ledger():
    led = CanonicalLedger(starting_balance=500.0)
    led.record(ts=1.0, market="m1", strategy="bregman", traded=True,
               bregman_certificate_id="cert-1", gross_ev=0.2, fee_adjusted_ev=0.18,
               fill_realism_status="filled", filled_qty=10, fees=0.1, slippage=0.0,
               realized_pnl=2.0, after_cost_pnl=1.9, predicted_prob=0.7, outcome=1,
               calibration_bucket=7)
    led.record(ts=2.0, market="m2", strategy="btc_pulse", traded=True,
               fill_realism_status="filled", filled_qty=5, realized_pnl=-0.5,
               after_cost_pnl=-0.6, predicted_prob=0.55, outcome=0, calibration_bucket=5,
               is_exploration=True)
    led.record(ts=3.0, market="m3", strategy="bregman", traded=True, open=True,
               notional=10.0, unrealized_pnl=0.3, after_cost_pnl=0.3)
    led.record(ts=4.0, market="m4", strategy="model", traded=False, kind="decision",
               gross_ev=-0.01, fee_adjusted_ev=-0.02)
    return led


def test_equity_is_starting_plus_realized_plus_open_unrealized():
    led = _ledger()
    # 500 + (2.0 - 0.5) + 0.3 = 501.8
    assert led.equity() == 501.8
    assert led.realized_total() == 1.5
    assert led.unrealized_total() == 0.3


def test_attribution_splits_exploration_validation():
    a = _ledger().attribution()
    assert a["bregman"]["trades"] == 2
    assert a["btc_pulse"]["exploration_pnl"] == -0.6
    assert a["bregman"]["validation_pnl"] == round(1.9 + 0.3, 8)


def test_strategy_exposure_from_open_positions():
    exp = _ledger().strategy_exposure()
    assert exp.get("bregman") == 10.0          # only the open position
    assert "btc_pulse" not in exp or exp["btc_pulse"] == 0.0


def test_no_trade_bucket_counts_decisions():
    nt = _ledger().no_trade_bucket()
    assert nt["n"] == 1
    assert nt["correctly_skipped"] == 1.0      # fee-adj EV <= 0 -> rightly skipped


def test_confidence_bucket_pnl():
    b = _ledger().confidence_bucket_pnl()
    assert 7 in b and b[7]["after_cost_pnl"] == 1.9
    assert b[7]["hit_rate"] == 1.0


def test_risk_metrics_present():
    rm = _ledger().risk_metrics()
    for k in ("sharpe", "sortino", "calmar", "max_drawdown", "cvar", "n_returns"):
        assert k in rm


def test_summary_bundles_everything():
    s = _ledger().summary()
    for k in ("equity", "attribution", "calibration", "confidence_bucket_pnl",
              "no_trade_bucket", "risk_metrics", "strategy_exposure"):
        assert k in s


def test_from_entries_roundtrip():
    led = _ledger()
    dicts = [e.to_dict() for e in led.entries]
    led2 = CanonicalLedger.from_entries(dicts, starting_balance=500.0)
    assert led2.equity() == led.equity()

"""Capped/delayed Kelly sizing diagnostics (Phase 9) — paper-only, default off, no martingale."""

from __future__ import annotations

from engine.pulse.sizing import kelly_fraction, degradation_penalty, sizing_diagnostics


def test_kelly_fraction_basic():
    # p_win 0.6 at price 0.5 (even odds b=1) -> f = 0.6 - 0.4/1 = 0.2
    assert abs(kelly_fraction(0.6, 0.5) - 0.2) < 1e-9
    assert kelly_fraction(0.5, 0.5) == 0.0          # no edge
    assert kelly_fraction(0.3, 0.5) == 0.0          # negative -> clamped to 0
    assert kelly_fraction(None, 0.5) is None and kelly_fraction(0.6, 0.0) is None


def test_degradation_penalty_only_reduces():
    assert degradation_penalty(0.0, 50.0) == 1.0
    assert degradation_penalty(25.0, 50.0) == 0.5
    assert degradation_penalty(60.0, 50.0) == 0.0   # past cap -> 0 (never > 1, never martingale)


def test_sizing_default_off_does_not_change_actual_size():
    d = sizing_diagnostics(p_win=0.7, price=0.5, ev_after_costs=0.1, bankroll_usd=1000.0,
                           hard_cap_usd=10.0, daily_loss_cap_usd=50.0, daily_loss_so_far=0.0,
                           base_size_usd=5.0, sizing_enabled=False)
    assert d["observe_only"] is True and d["actual_size_usd"] == 5.0     # unchanged
    assert d["suggested_size_usd"] > 0 and d["no_martingale"] is True
    assert d["half_kelly"] is not None and d["hard_cap_usd"] == 10.0


def test_sizing_hard_cap_and_daily_loss_cap():
    # huge edge -> suggestion capped at hard_cap
    d = sizing_diagnostics(p_win=0.95, price=0.5, ev_after_costs=0.4, bankroll_usd=100000.0,
                           hard_cap_usd=10.0, daily_loss_cap_usd=50.0, daily_loss_so_far=0.0,
                           base_size_usd=5.0, sizing_enabled=True)
    assert d["suggested_size_usd"] <= 10.0 and d["actual_size_usd"] <= 10.0
    # daily loss cap hit -> suggestion 0, actual falls back to base size (no forced trade)
    d2 = sizing_diagnostics(p_win=0.9, price=0.5, ev_after_costs=0.4, bankroll_usd=1000.0,
                            hard_cap_usd=10.0, daily_loss_cap_usd=50.0, daily_loss_so_far=60.0,
                            base_size_usd=5.0, sizing_enabled=True)
    assert d2["daily_cap_hit"] is True and d2["suggested_size_usd"] == 0.0


def test_sizing_requires_positive_ev():
    d = sizing_diagnostics(p_win=0.7, price=0.5, ev_after_costs=-0.05, bankroll_usd=1000.0,
                           hard_cap_usd=10.0, daily_loss_cap_usd=50.0, daily_loss_so_far=0.0,
                           base_size_usd=5.0, sizing_enabled=True)
    assert d["suggested_size_usd"] == 0.0           # negative EV -> no suggested size

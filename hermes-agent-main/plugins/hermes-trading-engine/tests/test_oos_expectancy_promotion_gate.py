"""6C: out-of-sample expectancy promotion gate.

A walk-forward HELD-OUT window of readiness trades must be credibly profitable after
costs before a run promotes past paper_learning. In-sample profit alone is not enough
(overfit guard). The gate applies only once the held-out window has enough samples, and
it NEVER enables live trading.
"""

from __future__ import annotations

from engine.training.live_readiness import (
    ReadinessCriteria, ReadinessState, evaluate_live_readiness)


def _bregman(**kw):
    b = dict(opportunities=10, false_positive_rate=0.0, worst_case_pnl=0.5,
             full_hedge_validated=True, all_leg_fill_feasible=True,
             partial_fill_hedge_break=False)
    b.update(kw)
    return b


def _ev(**kw):
    e = dict(samples=1200, after_cost_expectancy=0.02, realistic_fill_expectancy=0.015,
             oos_sharpe=2.0, oos_sortino=2.2, oos_calmar=1.0, max_drawdown_pct=0.08,
             calibration_error=0.04, ece=0.05, label_suppression_rate=0.05,
             unresolved_rate=0.05, ambiguous_rate=0.05, stale_data_rejection_rate=0.02,
             chainlink_stale=False, stale_book=False, risk_violations=0,
             downgraded=False, bregman=_bregman())
    e.update(kw)
    return e


def _gate(v, name):
    return next(g for g in v.gates if g.name == name)


def test_gate_not_applicable_below_min_oos_samples():
    # too few held-out samples -> gate does not apply, does not block
    v = evaluate_live_readiness(
        _ev(oos_expectancy_samples=5, oos_after_cost_expectancy=-0.5,
            oos_after_cost_expectancy_lb=-0.9), ReadinessCriteria())
    assert _gate(v, "positive_out_of_sample_expectancy").applies is False
    assert "positive_out_of_sample_expectancy" not in " ".join(v.blockers)
    assert v.state == ReadinessState.CANARY_READY


def test_negative_held_out_window_blocks_promotion():
    # enough OOS samples but the held-out window lost money -> BLOCKED
    v = evaluate_live_readiness(
        _ev(oos_expectancy_samples=50, oos_after_cost_expectancy=-0.10,
            oos_after_cost_expectancy_lb=-0.25), ReadinessCriteria())
    g = _gate(v, "positive_out_of_sample_expectancy")
    assert g.applies is True and g.passed is False
    assert v.state == ReadinessState.BLOCKED
    assert v.live_trading_enabled is False


def test_positive_mean_but_negative_lower_bound_blocks_when_required():
    # mean > 0 but the lower confidence bound is negative -> not credible -> blocked
    v = evaluate_live_readiness(
        _ev(oos_expectancy_samples=50, oos_after_cost_expectancy=0.03,
            oos_after_cost_expectancy_lb=-0.01), ReadinessCriteria())
    assert _gate(v, "positive_out_of_sample_expectancy").passed is False
    assert v.state == ReadinessState.BLOCKED


def test_credible_positive_held_out_window_allows_promotion():
    v = evaluate_live_readiness(
        _ev(oos_expectancy_samples=50, oos_after_cost_expectancy=0.04,
            oos_after_cost_expectancy_lb=0.012), ReadinessCriteria())
    g = _gate(v, "positive_out_of_sample_expectancy")
    assert g.applies is True and g.passed is True
    assert v.state == ReadinessState.CANARY_READY
    assert v.live_trading_enabled is False


def test_lower_bound_requirement_can_be_disabled():
    c = ReadinessCriteria(oos_require_positive_lower_bound=False)
    v = evaluate_live_readiness(
        _ev(oos_expectancy_samples=50, oos_after_cost_expectancy=0.03,
            oos_after_cost_expectancy_lb=-0.01), c)
    assert _gate(v, "positive_out_of_sample_expectancy").passed is True

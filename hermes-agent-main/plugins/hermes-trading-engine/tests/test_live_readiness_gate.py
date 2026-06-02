"""Live-readiness gate — readiness states + hard blockers.

Quant scope — *Strategy Optimization & Robustness Testing* + *Live Trading &
Monitoring* + *Compliance/Security*: proves the readiness verdict only reaches a
live-ready state (micro_canary_ready / canary_ready) when the strategy proves
durable after-cost profitability, execution realism, calibration quality,
settlement-label quality, risk-gate cleanliness, and Bregman validity. This NEVER
enables live trading — it only produces verdicts + blockers.
"""

from __future__ import annotations

import pytest

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


# --------------------------------------------------------------------------- #
# readiness states
# --------------------------------------------------------------------------- #
def test_readiness_states_defined_and_ordered():
    assert ReadinessState.ORDER == [
        "blocked", "paper_learning", "paper_qualified", "micro_canary_ready",
        "canary_ready"]
    assert ReadinessState.LIVE_READY == {"micro_canary_ready", "canary_ready"}


def test_strong_durable_evidence_reaches_canary_ready():
    v = evaluate_live_readiness(_ev(samples=1200), ReadinessCriteria())
    assert v.state == ReadinessState.CANARY_READY
    assert v.blockers == []
    assert v.allows_live_escalation is True
    assert v.live_trading_enabled is False  # verdict NEVER enables live


def test_mid_sample_strong_evidence_is_micro_canary():
    v = evaluate_live_readiness(_ev(samples=600), ReadinessCriteria())
    assert v.state == ReadinessState.MICRO_CANARY_READY
    assert v.allows_live_escalation is True


def test_qualified_sample_is_paper_qualified_not_live_ready():
    v = evaluate_live_readiness(_ev(samples=300), ReadinessCriteria())
    assert v.state == ReadinessState.PAPER_QUALIFIED
    assert v.allows_live_escalation is False


def test_small_sample_is_paper_learning():
    v = evaluate_live_readiness(_ev(samples=50), ReadinessCriteria())
    assert v.state == ReadinessState.PAPER_LEARNING
    assert v.allows_live_escalation is False


def test_gate_results_and_score_present():
    v = evaluate_live_readiness(_ev(), ReadinessCriteria())
    assert v.gates and all(hasattr(g, "passed") for g in v.gates)
    assert 0 <= v.score <= 100
    d = v.to_dict()
    assert d["state"] == ReadinessState.CANARY_READY
    assert "gates" in d and "capital_preservation" not in d  # gate ≠ capital plan


# --------------------------------------------------------------------------- #
# hard blockers prevent any live-ready state
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("override", [
    {"after_cost_expectancy": -0.01},
    {"realistic_fill_expectancy": -0.01},
    {"calibration_error": 0.5},
    {"max_drawdown_pct": 0.9},
    {"unresolved_rate": 0.6},
    {"label_suppression_rate": 0.9},
    {"stale_data_rejection_rate": 0.9},
    {"chainlink_stale": True},
    {"stale_book": True},
    {"risk_violations": 3},
    {"downgraded": True},
    {"bregman": {"opportunities": 5, "false_positive_rate": 0.3, "worst_case_pnl": 0.5,
                 "full_hedge_validated": True, "all_leg_fill_feasible": True,
                 "partial_fill_hedge_break": False}},
    {"bregman": {"opportunities": 5, "false_positive_rate": 0.0, "worst_case_pnl": -0.2,
                 "full_hedge_validated": True, "all_leg_fill_feasible": True,
                 "partial_fill_hedge_break": False}},
    {"bregman": {"opportunities": 5, "false_positive_rate": 0.0, "worst_case_pnl": 0.5,
                 "full_hedge_validated": True, "all_leg_fill_feasible": True,
                 "partial_fill_hedge_break": True}},
])
def test_any_hard_blocker_blocks_live_ready(override):
    v = evaluate_live_readiness(_ev(**override), ReadinessCriteria())
    assert v.state not in ReadinessState.LIVE_READY
    assert v.state == ReadinessState.BLOCKED
    assert v.blockers

"""Micro-live readiness verdict — ready ONLY when every institutional gate passes.

Quant scope — *Compliance/Security/Operational Excellence* + *Live Trading &
Monitoring*: proves the campaign declares micro-live readiness (and mints a canary
certificate) ONLY when after-cost profitability, out-of-sample robustness,
realistic-fill profitability, clean settlement labels, calibrated probabilities,
Bregman certification, and risk-gate cleanliness ALL pass. Any single failure
blocks readiness, names the exact failed criterion, and mints no certificate.
PAPER ONLY — the verdict never enables live trading.
"""

from __future__ import annotations

import pytest

from engine.training.validation_campaign import (default_campaign_evidence,
                                                  run_campaign)


def test_all_gates_pass_yields_live_ready_and_certificate():
    report = run_campaign(default_campaign_evidence())
    assert report.overall_ready is True
    assert report.readiness_state in ("micro_canary_ready", "canary_ready")
    assert report.readiness_verdict["live_trading_enabled"] is False
    assert report.certificate is not None


# each tuple: (criterion, profile_to_break, mutation)
_BREAKERS = [
    ("after_cost_profitability", "conservative_baseline", {"after_cost_expectancy": -0.01}),
    ("out_of_sample_robustness", "aggressive_learning", {"oos_sharpe": 0.1, "oos_sortino": 0.1,
                                                         "oos_calmar": 0.0}),
    ("realistic_fill_profitability", "realistic_fill_validation",
     {"realistic_fill_expectancy": -0.01}),
    ("clean_settlement_labels", "aggressive_plus_profit_governor", {"ambiguous_rate": 0.9}),
    ("calibrated_probabilities", "conservative_baseline", {"ece": 0.9, "calibration_error": 0.9}),
    ("bregman_certification", "bregman_certified_only",
     {"bregman": {"opportunities": 5, "false_positive_rate": 0.5,
                  "partial_fill_hedge_break": True, "worst_case_pnl": -1.0,
                  "full_hedge_validated": False, "all_leg_fill_feasible": False}}),
    ("risk_gate_cleanliness", "aggressive_learning", {"risk_violations": 3}),
]


@pytest.mark.parametrize("criterion,profile,mutation", _BREAKERS)
def test_each_failed_gate_blocks_readiness(criterion, profile, mutation):
    ev = default_campaign_evidence()
    ev[profile].update(mutation)
    report = run_campaign(ev)
    assert report.overall_ready is False, f"{criterion} should block readiness"
    assert report.certificate is None
    assert any(criterion in b for b in report.blockers), \
        f"expected '{criterion}' in blockers {report.blockers}"
    assert report.criteria[criterion]["passed"] is False


def test_blocked_campaign_reports_non_live_ready_state():
    ev = default_campaign_evidence()
    ev["aggressive_learning"]["risk_violations"] = 5
    report = run_campaign(ev)
    assert report.readiness_state not in ("micro_canary_ready", "canary_ready")
    assert report.readiness_verdict["allows_live_escalation"] is False

"""Ablation profitability report — research & Chainlink are advisory, not load-bearing.

Quant scope — *Strategy Optimization & Robustness Testing* + *Signal Generation*:
proves the campaign measures the marginal contribution of research and Chainlink
fair-value support, and flags whether the strategy stays profitable WITHOUT each
advisory input (research/Chainlink must never be load-bearing for after-cost edge).
"""

from __future__ import annotations

from engine.training.validation_campaign import (build_ablation_report,
                                                  default_campaign_evidence)


def test_ablation_report_shape():
    rep = build_ablation_report(default_campaign_evidence())
    for key in ("research_contribution", "chainlink_contribution",
                "robust_without_research", "robust_without_chainlink", "profiles"):
        assert key in rep


def test_research_contribution_is_measured():
    ev = default_campaign_evidence()
    ev["aggressive_learning"]["after_cost_expectancy"] = 0.030
    ev["no_research_ablation"]["after_cost_expectancy"] = 0.022
    rep = build_ablation_report(ev)
    assert abs(rep["research_contribution"] - 0.008) < 1e-6
    # still profitable without research -> research is advisory only
    assert rep["robust_without_research"] is True


def test_strategy_that_needs_research_is_flagged_not_robust():
    ev = default_campaign_evidence()
    ev["no_research_ablation"]["after_cost_expectancy"] = -0.01  # only profitable with research
    ev["no_research_ablation"]["realistic_fill_expectancy"] = -0.01
    rep = build_ablation_report(ev)
    assert rep["robust_without_research"] is False


def test_chainlink_contribution_is_measured_and_robustness_flagged():
    ev = default_campaign_evidence()
    ev["aggressive_learning"]["after_cost_expectancy"] = 0.030
    ev["no_chainlink_ablation"]["after_cost_expectancy"] = 0.028
    rep = build_ablation_report(ev)
    assert abs(rep["chainlink_contribution"] - 0.002) < 1e-6
    assert rep["robust_without_chainlink"] is True

    ev["no_chainlink_ablation"]["after_cost_expectancy"] = -0.02
    ev["no_chainlink_ablation"]["realistic_fill_expectancy"] = -0.02
    rep2 = build_ablation_report(ev)
    assert rep2["robust_without_chainlink"] is False

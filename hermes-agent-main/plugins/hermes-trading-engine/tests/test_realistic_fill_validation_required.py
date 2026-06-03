"""Realistic-fill profitability is mandatory for readiness.

Quant scope — *CLOB v2 Execution* + *Backtesting & Simulation*: proves the
campaign will NOT mark a strategy ready when profit only survives optimistic
(guaranteed) fills. A positive optimistic edge with a non-positive realistic-fill
edge must block readiness and mint no certificate.
"""

from __future__ import annotations

from engine.training.validation_campaign import (default_campaign_evidence,
                                                  evaluate_profile, run_campaign)


def test_optimistic_only_profit_blocks_readiness():
    ev = default_campaign_evidence()
    # optimistic after-cost edge stays positive, but realistic-fill edge is gone
    for pid in ev:
        ev[pid]["realistic_fill_expectancy"] = -0.005
    report = run_campaign(ev)
    assert report.overall_ready is False
    assert report.certificate is None
    assert any("realistic_fill_profitability" in b for b in report.blockers)


def test_realistic_fill_profile_requires_positive_realistic_edge():
    ev = default_campaign_evidence()
    ev["realistic_fill_validation"]["realistic_fill_expectancy"] = -0.01
    pr = evaluate_profile("realistic_fill_validation",
                          ev["realistic_fill_validation"])
    assert pr.passed is False
    assert any("realistic_fill" in b for b in pr.blockers)


def test_positive_realistic_fill_passes():
    ev = default_campaign_evidence()
    report = run_campaign(ev)
    # baseline (all good) is profitable under realistic fills -> criterion passes
    assert report.criteria["realistic_fill_profitability"]["passed"] is True

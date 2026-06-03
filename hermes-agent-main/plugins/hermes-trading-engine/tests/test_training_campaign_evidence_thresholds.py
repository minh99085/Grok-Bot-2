"""Campaign evidence threshold gating (PAPER ONLY).

Quant scope — *Strategy Optimization & Robustness Testing*: the verdict depends
on EVIDENCE thresholds, not elapsed time. Insufficient evidence -> keep training;
negative after-cost / realistic-fill expectancy after minimum evidence -> blocked.
"""

from __future__ import annotations

from _campaign_helpers import micro_ready_snapshot

from engine.training.campaign_controller import TrainingCampaignController


def _ctrl():
    return TrainingCampaignController(algorithm_freeze_mode=True)


def test_insufficient_decisions_is_continue_not_ready():
    v = _ctrl().update(micro_ready_snapshot(decisions=100))
    assert v.state == "continue_training"


def test_insufficient_paper_trades_blocks_readiness():
    v = _ctrl().update(micro_ready_snapshot(paper_trades=10))
    assert v.state != "micro_canary_ready"
    assert any("insufficient_paper_trades" in b for b in v.blockers)


def test_insufficient_resolved_labels():
    v = _ctrl().update(micro_ready_snapshot(resolved_labels=5, clean_labels=4))
    assert any("insufficient_resolved_labels" in b for b in v.blockers)


def test_negative_after_cost_blocks_after_min_evidence():
    # all counts satisfied -> minimum evidence exists -> negative edge is a hard block
    v = _ctrl().update(micro_ready_snapshot(after_cost_expectancy=-0.01))
    assert v.state == "blocked"
    assert any("negative_after_cost_expectancy" in b for b in v.blockers)


def test_negative_after_cost_without_evidence_is_continue_not_blocked():
    # not enough decisions -> minimum evidence does NOT exist -> not a hard block yet
    v = _ctrl().update(micro_ready_snapshot(decisions=50, paper_trades=10,
                                            resolved_labels=5, clean_labels=4,
                                            after_cost_expectancy=-0.01))
    assert v.state == "continue_training"
    assert "negative_after_cost_expectancy" not in " ".join(v.blockers)


def test_optimistic_only_profitability_blocks_after_min_evidence():
    v = _ctrl().update(micro_ready_snapshot(after_cost_expectancy=0.02,
                                            realistic_fill_expectancy=-0.005,
                                            optimistic_expectancy=0.03))
    assert v.state == "blocked"
    blob = " ".join(v.blockers)
    assert "negative_realistic_fill_expectancy" in blob
    assert "optimistic_only_profitability" in blob


def test_calibration_regression_prevents_ready():
    v = _ctrl().update(micro_ready_snapshot(calibration_error=0.30,
                                            baseline_calibration_error=0.05))
    assert v.state != "micro_canary_ready"
    assert any("calibration_regression" in b for b in v.blockers)


def test_excessive_drawdown_prevents_ready():
    v = _ctrl().update(micro_ready_snapshot(max_drawdown_pct=0.50))
    assert v.state != "micro_canary_ready"
    assert any("excessive_drawdown" in b for b in v.blockers)

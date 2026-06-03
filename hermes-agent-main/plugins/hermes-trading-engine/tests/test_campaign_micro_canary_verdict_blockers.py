"""Micro-canary verdict blockers — every hard safety failure blocks readiness.

Quant scope — *Risk Management*, *Signal Generation w/ Bregman priority*,
*CLOB v2 Execution*, *Compliance*: a single Bregman false positive, partial-fill
hedge break, risk-gate violation, stale-data signal, dirty-label spike, live
order, optimistic-only profit, or un-frozen algorithm blocks micro-canary.
"""

from __future__ import annotations

import pytest

from _campaign_helpers import micro_ready_snapshot

from engine.training.campaign_controller import TrainingCampaignController


def test_clean_snapshot_reaches_micro_canary():
    v = TrainingCampaignController(algorithm_freeze_mode=True).update(micro_ready_snapshot())
    assert v.state == "micro_canary_ready"


_HARD_BLOCKERS = [
    ("bregman_false_positive", {"bregman_false_positives": 1}),
    ("bregman_partial_fill_hedge_break", {"partial_fill_hedge_breaks": 1}),
    ("risk_gate_violation", {"risk_violations": 1}),
    ("live_order_attempted", {"live_orders": 1}),
    ("stale_chainlink", {"stale_chainlink": True}),
    ("stale_order_book", {"stale_book": True}),
    ("stale_data_confidence_improvement", {"stale_data_confidence_improvement": True}),
    ("dirty_labels", {"resolved_labels": 150, "clean_labels": 40}),
    ("negative_after_cost_expectancy", {"after_cost_expectancy": -0.01}),
    ("negative_realistic_fill_expectancy", {"realistic_fill_expectancy": -0.01}),
]


@pytest.mark.parametrize("blocker,mutation", _HARD_BLOCKERS)
def test_hard_blocker_blocks_micro_canary(blocker, mutation):
    v = TrainingCampaignController(algorithm_freeze_mode=True).update(
        micro_ready_snapshot(**mutation))
    assert v.state == "blocked"
    assert v.state != "micro_canary_ready"
    assert any(blocker in b for b in v.blockers), f"{blocker} not in {v.blockers}"


def test_unfrozen_algorithm_blocks_micro_canary():
    v = TrainingCampaignController(algorithm_freeze_mode=False).update(
        micro_ready_snapshot(algorithm_freeze_mode=False))
    assert v.state != "micro_canary_ready"
    assert any("algorithm_not_frozen" in b for b in v.blockers)


def test_insufficient_bregman_certified_prevents_micro_canary():
    v = TrainingCampaignController(algorithm_freeze_mode=True).update(
        micro_ready_snapshot(bregman_certified=0))
    assert v.state != "micro_canary_ready"
    assert any("insufficient_bregman_certified" in b for b in v.blockers)


def test_non_live_ready_readiness_state_prevents_micro_canary():
    v = TrainingCampaignController(algorithm_freeze_mode=True).update(
        micro_ready_snapshot(live_readiness_state="paper_qualified"))
    assert v.state in ("paper_qualified", "continue_training")
    assert v.state != "micro_canary_ready"

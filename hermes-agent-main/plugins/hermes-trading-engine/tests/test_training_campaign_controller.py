"""Institutional paper-training campaign controller (PAPER ONLY).

Quant scope — *Live Trading & Monitoring* + *Compliance*: the controller is the
bridge between paper training and real-money readiness. It aggregates durable
evidence across runs, produces a hard verdict (never enabling live), and reports
blockers + the next evidence target.
"""

from __future__ import annotations

from _campaign_helpers import micro_ready_snapshot

from engine.training.campaign_controller import (CampaignEvidence, CampaignProgress,
                                                  CampaignThresholds, CampaignVerdict,
                                                  TrainingCampaignController,
                                                  campaign_json, campaign_markdown)


def test_controller_basic_update_and_report():
    ctrl = TrainingCampaignController(campaign_name="t1", algorithm_freeze_mode=True)
    v = ctrl.update(micro_ready_snapshot())
    assert isinstance(v, CampaignVerdict)
    rep = ctrl.report()
    for key in ("campaign_name", "state", "evidence", "progress", "verdict", "blockers",
                "next_target", "thresholds", "no_live_orders"):
        assert key in rep
    assert rep["no_live_orders"] is True
    assert rep["verdict"]["live_trading_enabled"] is False


def test_evidence_progress_verdict_types():
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    ctrl.update(micro_ready_snapshot())
    assert isinstance(ctrl.evidence(), CampaignEvidence)
    assert isinstance(ctrl.progress(), CampaignProgress)
    assert isinstance(ctrl.verdict(), CampaignVerdict)


def test_micro_canary_ready_when_all_pass():
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    v = ctrl.update(micro_ready_snapshot())
    assert v.state == "micro_canary_ready"
    assert v.live_trading_enabled is False


def test_time_alone_does_not_make_ready():
    # plenty of time + runtime, but NO decisions/trades/labels/bregman evidence
    snap = micro_ready_snapshot(decisions=0, paper_trades=0, resolved_labels=0,
                                clean_labels=0, bregman_candidates=0, bregman_certified=0,
                                after_cost_expectancy=0.0, realistic_fill_expectancy=0.0)
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    v = ctrl.update(snap)
    assert v.state == "continue_training"
    assert v.state != "micro_canary_ready"


def test_continue_training_when_decisions_insufficient():
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    v = ctrl.update(micro_ready_snapshot(decisions=120, paper_trades=20, resolved_labels=10,
                                         clean_labels=8, bregman_candidates=5,
                                         bregman_certified=0))
    assert v.state == "continue_training"
    assert any("insufficient_decisions" in b for b in v.blockers)


def test_json_and_markdown_render():
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    ctrl.update(micro_ready_snapshot())
    rep = ctrl.report()
    js = campaign_json(rep)
    import json
    json.loads(js)  # valid JSON
    md = campaign_markdown(rep)
    assert isinstance(md, str)
    assert "Institutional paper-training campaign" in md
    assert "Verdict" in md


def test_thresholds_from_config():
    from engine.training.config import TrainingConfig
    th = CampaignThresholds.from_config(TrainingConfig(campaign_target_min_days=21,
                                                       campaign_target_min_decisions=2000))
    assert th.target_min_days == 21
    assert th.target_min_decisions == 2000
    assert th.max_allowed_bregman_false_positives == 0


def test_next_target_points_to_first_gap():
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    v = ctrl.update(micro_ready_snapshot(decisions=10))
    assert v.next_target  # non-empty string
    assert "decisions" in v.next_target.lower()

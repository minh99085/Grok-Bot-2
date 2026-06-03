"""Campaign state persists across reloads + aggregates multiple updates.

Quant scope — *Live Trading & Monitoring* + *Operational Excellence*: durable
evidence collection across many runs; reloading the controller preserves totals.
"""

from __future__ import annotations

import json

from _campaign_helpers import micro_ready_snapshot

from engine.training.campaign_controller import TrainingCampaignController


def test_persist_and_reload_preserves_evidence(tmp_path):
    path = tmp_path / "polymarket_training_campaign.json"
    ctrl = TrainingCampaignController(campaign_name="persist1", algorithm_freeze_mode=True,
                                      state_path=path)
    ctrl.update(micro_ready_snapshot(run_id="r1", decisions=600, paper_trades=180))
    ctrl.persist()
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["campaign_name"] == "persist1"

    reloaded = TrainingCampaignController.load(path, algorithm_freeze_mode=True)
    assert reloaded.evidence().decisions == 600
    assert reloaded.campaign_name == "persist1"


def test_multiple_runs_aggregate_decisions(tmp_path):
    path = tmp_path / "polymarket_training_campaign.json"
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True, state_path=path)
    ctrl.update(micro_ready_snapshot(run_id="r1", decisions=600, paper_trades=180,
                                     resolved_labels=70, clean_labels=60))
    ctrl.update(micro_ready_snapshot(run_id="r2", decisions=700, paper_trades=200,
                                     resolved_labels=90, clean_labels=80))
    ev = ctrl.evidence()
    assert ev.decisions == 1300            # summed across runs
    assert ev.paper_trades == 380
    assert ev.resolved_labels == 160


def test_repeated_update_same_run_does_not_double_count(tmp_path):
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    ctrl.update(micro_ready_snapshot(run_id="r1", decisions=500))
    ctrl.update(micro_ready_snapshot(run_id="r1", decisions=550))  # same run, later cumulative
    assert ctrl.evidence().decisions == 550   # replaced, not added


def test_aggregation_survives_reload(tmp_path):
    path = tmp_path / "campaign.json"
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True, state_path=path)
    ctrl.update(micro_ready_snapshot(run_id="r1", decisions=600))
    ctrl.persist()
    ctrl2 = TrainingCampaignController.load(path, algorithm_freeze_mode=True)
    ctrl2.update(micro_ready_snapshot(run_id="r2", decisions=700))
    assert ctrl2.evidence().decisions == 1300


def test_stop_requested_persisted(tmp_path):
    path = tmp_path / "campaign.json"
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True, state_path=path)
    ctrl.update(micro_ready_snapshot())
    ctrl.mark_stop_requested()
    data = json.loads(path.read_text())
    assert data["stop_requested"] is True
    # reload keeps evidence
    ctrl2 = TrainingCampaignController.load(path, algorithm_freeze_mode=True)
    assert ctrl2.state.stop_requested is True
    assert ctrl2.evidence().decisions == 1200

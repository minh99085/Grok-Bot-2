"""Algorithm-freeze mode — evidence quality over new code (PAPER ONLY).

Quant scope — *Strategy Optimization & Robustness Testing* + *Compliance*: during
a campaign the bot must NOT promote parameters or relax thresholds; freeze forces
``aggressive_can_promote_params`` off and is required to reach micro-canary.
"""

from __future__ import annotations

from _campaign_helpers import micro_ready_snapshot

from engine.training.campaign_controller import TrainingCampaignController
from engine.training.config import TrainingConfig


def test_freeze_forces_no_param_promotion_in_config():
    c = TrainingConfig.aggressive_paper(algorithm_freeze_mode=True,
                                        aggressive_can_promote_params=True)
    assert c.aggressive_can_promote_params is False


def test_micro_canary_requires_freeze_true():
    # freeze OFF -> cannot reach micro_canary_ready even with perfect evidence
    ctrl_off = TrainingCampaignController(algorithm_freeze_mode=False)
    v_off = ctrl_off.update(micro_ready_snapshot(algorithm_freeze_mode=False))
    assert v_off.state != "micro_canary_ready"
    assert any("algorithm_not_frozen" in b for b in v_off.blockers)

    ctrl_on = TrainingCampaignController(algorithm_freeze_mode=True)
    v_on = ctrl_on.update(micro_ready_snapshot(algorithm_freeze_mode=True))
    assert v_on.state == "micro_canary_ready"


def test_freeze_off_with_require_is_blocked():
    # institutional default requires freeze; running unfrozen is a hard block
    ctrl = TrainingCampaignController(algorithm_freeze_mode=False)
    v = ctrl.update(micro_ready_snapshot(algorithm_freeze_mode=False))
    assert v.state == "blocked"
    assert any("algorithm_not_frozen" in b for b in v.blockers)

"""Campaign never permits live orders (PAPER ONLY).

Quant scope — *Compliance/Security/Operational Excellence*: any live order count
> 0 is a hard safety failure that blocks readiness and the report always asserts
no live orders.
"""

from __future__ import annotations

from _campaign_helpers import micro_ready_snapshot

from engine.training.campaign_controller import TrainingCampaignController


def test_live_order_count_blocks_readiness():
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    v = ctrl.update(micro_ready_snapshot(live_orders=1))
    assert v.state == "blocked"
    assert any("live_order_attempted" in b for b in v.blockers)
    assert ctrl.report()["no_live_orders"] is False


def test_zero_live_orders_reports_clean():
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    ctrl.update(micro_ready_snapshot(live_orders=0))
    rep = ctrl.report()
    assert rep["no_live_orders"] is True
    assert rep["verdict"]["live_trading_enabled"] is False


def test_verdict_never_enables_live_even_when_ready():
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True)
    v = ctrl.update(micro_ready_snapshot())
    assert v.state == "micro_canary_ready"
    assert v.live_trading_enabled is False
    assert ctrl.report()["no_live_orders"] is True

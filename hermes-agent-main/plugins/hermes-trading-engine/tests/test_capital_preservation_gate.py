"""Capital-preservation gate — bounded live notional + downgrade rules.

Quant scope — *Risk Management & Portfolio Optimization* + *Compliance/Security*:
proves the capital-preservation report caps the max allowed initial live notional,
max daily loss, per-market + event exposure, and supplies automatic downgrade
rules — and that NON-live-ready states get zero allowed live notional. This never
enables live trading.
"""

from __future__ import annotations

import pytest

from engine.training.config import TrainingConfig
from engine.training.live_readiness import (
    ReadinessState, capital_preservation_report)


def test_blocked_and_paper_states_allow_zero_live_notional():
    for state in (ReadinessState.BLOCKED, ReadinessState.PAPER_LEARNING,
                  ReadinessState.PAPER_QUALIFIED):
        rep = capital_preservation_report(state, bankroll=1000.0)
        assert rep["max_initial_live_notional"] == 0.0
        assert rep["allowed"] is False


def test_micro_canary_gets_tiny_bounded_notional():
    rep = capital_preservation_report(ReadinessState.MICRO_CANARY_READY, bankroll=1000.0)
    assert rep["allowed"] is True
    assert 0.0 < rep["max_initial_live_notional"] <= 10.0
    assert rep["max_daily_loss"] > 0.0
    assert rep["max_per_market_exposure"] > 0.0
    assert rep["max_event_exposure"] > 0.0
    assert rep["auto_downgrade_rules"]


def test_canary_larger_but_still_bounded_and_capped_by_config():
    cfg = TrainingConfig(mode="paper_train")
    micro = capital_preservation_report(ReadinessState.MICRO_CANARY_READY,
                                        bankroll=100000.0, cfg=cfg)
    canary = capital_preservation_report(ReadinessState.CANARY_READY,
                                         bankroll=100000.0, cfg=cfg)
    assert canary["max_initial_live_notional"] >= micro["max_initial_live_notional"]
    # never exceeds the configured live caps even on a huge bankroll
    assert canary["max_initial_live_notional"] <= float(cfg.live_canary_notional_usd)
    assert micro["max_initial_live_notional"] <= float(cfg.live_micro_canary_notional_usd)


def test_auto_downgrade_rules_cover_loss_and_kill_switch():
    rep = capital_preservation_report(ReadinessState.MICRO_CANARY_READY, bankroll=1000.0)
    triggers = " ".join(r.get("trigger", "") for r in rep["auto_downgrade_rules"]).lower()
    assert "daily_loss" in triggers
    assert "drawdown" in triggers or "kill" in triggers


def test_report_accepts_a_verdict_object():
    from engine.training.live_readiness import evaluate_live_readiness, ReadinessCriteria
    v = evaluate_live_readiness({"samples": 5}, ReadinessCriteria())  # paper_learning
    rep = capital_preservation_report(v, bankroll=1000.0)
    assert rep["state"] == v.state
    assert rep["max_initial_live_notional"] == 0.0

"""Automatic canary rollback to paper/conservative on any degradation.

Quant scope — *Live Trading & Monitoring* + *Compliance/Security*: proves the
canary rolls back to a safe (paper/conservative) mode the moment ANY degradation
appears — drawdown breach, fill-failure spike, slippage blowout, stale data,
settlement ambiguity, reconciliation mismatch, calibration deterioration, or a
risk violation — and that a clean state does NOT roll back. Rollback is a hard
stop; it can never re-enable live trading.
"""

from __future__ import annotations

from engine.micro_live.canary import (CanaryController, CanaryRollbackLimits,
                                       evaluate_canary_rollback)


def _clean():
    return dict(drawdown=0.0, fill_failure_rate=0.0, slippage_bps=0.0, stale_ms=0,
                ambiguity_score=0.0, reconciliation_clean=True, calibration_error=0.0,
                risk_violation=False)


def _limits():
    return CanaryRollbackLimits(max_drawdown_usd=1.0, max_fill_failure_rate=0.34,
                                max_slippage_bps=150.0, max_stale_ms=750,
                                max_ambiguity_score=0.20, max_calibration_error=0.15)


def test_clean_state_does_not_roll_back():
    d = evaluate_canary_rollback(_clean(), limits=_limits())
    assert d.should_rollback is False
    assert d.reasons == []


def test_drawdown_breach_rolls_back():
    d = evaluate_canary_rollback({**_clean(), "drawdown": 2.0}, limits=_limits())
    assert d.should_rollback is True
    assert any("drawdown" in r for r in d.reasons)
    assert d.target_mode in ("paper", "conservative")


def test_fill_failure_spike_rolls_back():
    d = evaluate_canary_rollback({**_clean(), "fill_failure_rate": 0.9}, limits=_limits())
    assert d.should_rollback is True
    assert any("fill" in r for r in d.reasons)


def test_slippage_blowout_rolls_back():
    d = evaluate_canary_rollback({**_clean(), "slippage_bps": 500.0}, limits=_limits())
    assert d.should_rollback is True
    assert any("slippage" in r for r in d.reasons)


def test_stale_data_rolls_back():
    d = evaluate_canary_rollback({**_clean(), "stale_ms": 5000}, limits=_limits())
    assert d.should_rollback is True
    assert any("stale" in r for r in d.reasons)


def test_settlement_ambiguity_rolls_back():
    d = evaluate_canary_rollback({**_clean(), "ambiguity_score": 0.9}, limits=_limits())
    assert d.should_rollback is True
    assert any("ambig" in r for r in d.reasons)


def test_reconciliation_mismatch_rolls_back():
    d = evaluate_canary_rollback({**_clean(), "reconciliation_clean": False}, limits=_limits())
    assert d.should_rollback is True
    assert any("reconcil" in r for r in d.reasons)


def test_calibration_deterioration_rolls_back():
    d = evaluate_canary_rollback({**_clean(), "calibration_error": 0.5}, limits=_limits())
    assert d.should_rollback is True
    assert any("calibration" in r for r in d.reasons)


def test_risk_violation_rolls_back():
    d = evaluate_canary_rollback({**_clean(), "risk_violation": True}, limits=_limits())
    assert d.should_rollback is True
    assert any("risk" in r for r in d.reasons)


def test_controller_engages_rollback_and_disables_canary(tmp_path):
    ks = tmp_path / "CANARY_ROLLBACK_KILL_SWITCH"
    ctrl = CanaryController(rollback_kill_switch_path=str(ks), limits=_limits())
    assert ctrl.is_rolled_back() is False
    decision = ctrl.check_and_rollback({**_clean(), "drawdown": 5.0})
    assert decision.should_rollback is True
    assert ctrl.is_rolled_back() is True
    assert ks.exists()
    # once rolled back, no live order can be authorized
    assert ctrl.live_blocked() is True


def test_controller_clean_does_not_engage(tmp_path):
    ks = tmp_path / "CANARY_ROLLBACK_KILL_SWITCH"
    ctrl = CanaryController(rollback_kill_switch_path=str(ks), limits=_limits())
    decision = ctrl.check_and_rollback(_clean())
    assert decision.should_rollback is False
    assert ctrl.is_rolled_back() is False
    assert not ks.exists()

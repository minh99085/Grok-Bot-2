"""Drawdown governor — reduce / pause / downgrade on degraded conditions.

Quant scope — *Risk Management & Portfolio Optimization* + *Live Trading &
Monitoring*: proves the drawdown governor cuts position size, pauses a strategy,
or downgrades to conservative paper mode after a loss streak, a drawdown breach,
calibration degradation, or an execution-quality failure — and that its size
multiplier is monotone non-increasing in every stress dimension. PAPER ONLY.
"""

from __future__ import annotations

import pytest

from engine.training.capital_allocator import (
    ACTION_DOWNGRADE, ACTION_PAUSE, ACTION_REDUCE, ACTION_TRADE,
    DrawdownGovernorLimits, drawdown_governor)


def test_no_stress_allows_full_trade():
    v = drawdown_governor(loss_streak=0, drawdown=0.0, max_drawdown_usd=50.0,
                          calibration_instability=0.0, execution_quality=1.0)
    assert v["action"] == ACTION_TRADE
    assert v["size_multiplier"] == pytest.approx(1.0)
    assert v["reasons"] == []


def test_drawdown_breach_downgrades_and_zeroes_size():
    v = drawdown_governor(drawdown=60.0, max_drawdown_usd=50.0)
    assert v["action"] == ACTION_DOWNGRADE
    assert v["size_multiplier"] == 0.0
    assert any("drawdown" in r for r in v["reasons"])


def test_long_loss_streak_pauses_strategy():
    lim = DrawdownGovernorLimits(max_loss_streak=4, pause_loss_streak=8)
    v = drawdown_governor(loss_streak=9, drawdown=0.0, max_drawdown_usd=50.0, limits=lim)
    assert v["action"] == ACTION_PAUSE
    assert v["size_multiplier"] == 0.0
    assert any("loss_streak" in r for r in v["reasons"])


def test_moderate_loss_streak_reduces_size():
    lim = DrawdownGovernorLimits(max_loss_streak=4, pause_loss_streak=10)
    v = drawdown_governor(loss_streak=5, drawdown=0.0, max_drawdown_usd=50.0, limits=lim)
    assert v["action"] == ACTION_REDUCE
    assert 0.0 < v["size_multiplier"] < 1.0


def test_calibration_degradation_reduces_size():
    lim = DrawdownGovernorLimits(calibration_instability_limit=0.1)
    v = drawdown_governor(calibration_instability=0.12, drawdown=0.0,
                          max_drawdown_usd=50.0, limits=lim)
    assert v["action"] in (ACTION_REDUCE, ACTION_PAUSE)
    assert v["size_multiplier"] < 1.0
    assert any("calibration" in r for r in v["reasons"])


def test_severe_calibration_breakdown_pauses():
    lim = DrawdownGovernorLimits(calibration_instability_limit=0.1)
    v = drawdown_governor(calibration_instability=0.5, drawdown=0.0,
                          max_drawdown_usd=50.0, limits=lim)
    assert v["action"] == ACTION_PAUSE
    assert v["size_multiplier"] == 0.0


def test_execution_quality_failure_reduces_size():
    lim = DrawdownGovernorLimits(execution_quality_floor=0.5)
    v = drawdown_governor(execution_quality=0.2, drawdown=0.0,
                          max_drawdown_usd=50.0, limits=lim)
    assert v["action"] in (ACTION_REDUCE, ACTION_PAUSE)
    assert v["size_multiplier"] < 1.0
    assert any("execution" in r for r in v["reasons"])


def test_size_multiplier_monotone_in_drawdown():
    prev = 1.0001
    for dd in (0.0, 10.0, 20.0, 30.0, 45.0):
        m = drawdown_governor(drawdown=dd, max_drawdown_usd=50.0)["size_multiplier"]
        assert m <= prev + 1e-9
        prev = m


def test_size_multiplier_monotone_in_loss_streak():
    lim = DrawdownGovernorLimits(max_loss_streak=3, pause_loss_streak=20)
    prev = 1.0001
    for s in (0, 2, 5, 10, 15):
        m = drawdown_governor(loss_streak=s, drawdown=0.0, max_drawdown_usd=50.0,
                              limits=lim)["size_multiplier"]
        assert m <= prev + 1e-9
        prev = m


def test_limits_from_config_smoke():
    from engine.training.config import TrainingConfig
    lim = DrawdownGovernorLimits.from_config(TrainingConfig(mode="paper_train"))
    assert lim.max_drawdown_usd > 0
    assert lim.pause_loss_streak >= lim.max_loss_streak

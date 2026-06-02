"""Adverse-selection markout + slippage forecast error.

Quant scope — *Live Trading & Monitoring* + *CLOB v2 Execution* + *Risk
Management*: proves the markout model flags adverse selection (the mid moving
against a fill) and that the slippage forecast carries an error band whose
conservative forecast is never below the point estimate. PAPER ONLY.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engine.execution.slippage import markout_bps
from engine.training.execution_quality import (
    conservative_slippage_forecast, markout_by_horizon, slippage_forecast,
    slippage_forecast_error)


def test_markout_bps_flags_adverse_buy():
    # BUY filled at 0.50; the mid later DROPS to 0.48 -> adverse (negative markout)
    adv = markout_bps(Decimal("0.50"), Decimal("0.48"), "BUY")
    fav = markout_bps(Decimal("0.50"), Decimal("0.52"), "BUY")
    assert adv < 0 and fav > 0


def test_markout_by_horizon_signs():
    out = markout_by_horizon(0.50, {"5s": 0.48, "60s": 0.55}, side="BUY")
    assert out["5s"] < 0    # mid fell below the buy -> adverse
    assert out["60s"] > 0   # mid rose above the buy -> favourable


def test_slippage_forecast_error_grows_with_size():
    small = slippage_forecast_error(order_usd=100.0, depth_usd=5000.0)
    large = slippage_forecast_error(order_usd=5000.0, depth_usd=5000.0)
    assert large > small >= 0.0


def test_conservative_slippage_forecast_never_below_point_estimate():
    point = slippage_forecast(order_usd=2000.0, depth_usd=5000.0)
    cons = conservative_slippage_forecast(order_usd=2000.0, depth_usd=5000.0)
    assert cons >= point


def test_slippage_forecast_error_zero_for_no_order():
    assert slippage_forecast_error(order_usd=0.0, depth_usd=5000.0) == 0.0

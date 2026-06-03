"""Micro-live canary capital limits (strictly capped real-money canary).

Quant scope — *Risk Management & Portfolio Optimization* + *Compliance/Security*:
proves the canary caps are tiny, hard-capped in code (env can only shrink), and
that every cap (order notional, orders/day, daily loss, open exposure, event
exposure, strategy exposure, Bregman bundle capital lock) blocks an order that
would breach it. These caps only ever TIGHTEN the live-execution control surface.
"""

from __future__ import annotations

from decimal import Decimal

from engine.micro_live.canary import CanaryCaps
from engine.micro_live.config import (HARD_MAX_DAILY_NOTIONAL_USD,
                                       HARD_MAX_ORDER_NOTIONAL_USD)


def _within():
    return dict(notional=0.5, orders_today=0, daily_loss=0.0, open_exposure=0.0,
                event_exposure=0.0, strategy_exposure=0.0, bregman_bundle_lock=0.0,
                strategy="certified_bregman")


def test_defaults_are_tiny():
    caps = CanaryCaps()
    assert caps.max_order_notional_usd <= float(HARD_MAX_ORDER_NOTIONAL_USD)
    assert caps.max_orders_per_day <= 3
    assert caps.max_daily_loss_usd <= float(HARD_MAX_DAILY_NOTIONAL_USD)


def test_within_limits_passes():
    ok, reason = CanaryCaps().check(**_within())
    assert ok is True
    assert reason == "ok"


def test_order_notional_cap_blocks():
    caps = CanaryCaps(max_order_notional_usd=1.0)
    ok, reason = caps.check(**{**_within(), "notional": 2.0})
    assert ok is False
    assert "notional" in reason


def test_max_orders_per_day_blocks():
    caps = CanaryCaps(max_orders_per_day=3)
    ok, reason = caps.check(**{**_within(), "orders_today": 3})
    assert ok is False
    assert "orders_per_day" in reason


def test_daily_loss_cap_blocks():
    caps = CanaryCaps(max_daily_loss_usd=1.0)
    ok, reason = caps.check(**{**_within(), "daily_loss": 2.0})
    assert ok is False
    assert "daily_loss" in reason


def test_open_exposure_cap_blocks():
    caps = CanaryCaps(max_open_exposure_usd=1.0)
    ok, reason = caps.check(**{**_within(), "open_exposure": 0.9, "notional": 0.5})
    assert ok is False
    assert "open_exposure" in reason


def test_event_exposure_cap_blocks():
    caps = CanaryCaps(max_event_exposure_usd=1.0)
    ok, reason = caps.check(**{**_within(), "event_exposure": 0.9, "notional": 0.5})
    assert ok is False
    assert "event_exposure" in reason


def test_strategy_exposure_cap_blocks():
    caps = CanaryCaps(max_strategy_exposure_usd=1.0)
    ok, reason = caps.check(**{**_within(), "strategy_exposure": 0.9, "notional": 0.5})
    assert ok is False
    assert "strategy_exposure" in reason


def test_bregman_bundle_capital_lock_cap_blocks():
    caps = CanaryCaps(max_bregman_bundle_capital_lock_usd=1.0)
    ok, reason = caps.check(**{**_within(), "strategy": "certified_bregman",
                               "bregman_bundle_lock": 0.9, "notional": 0.5})
    assert ok is False
    assert "bregman_bundle" in reason


def test_from_config_respects_hard_caps():
    class Cfg:  # an attacker-supplied config trying to raise caps
        canary_max_order_notional_usd = 100.0
        canary_max_open_exposure_usd = 100.0
        canary_max_event_exposure_usd = 100.0
        canary_max_strategy_exposure_usd = 100.0
        canary_max_bregman_bundle_capital_lock_usd = 100.0
        canary_max_daily_loss_usd = 100.0
        canary_max_orders_per_day = 100
    caps = CanaryCaps.from_config(Cfg())
    assert caps.max_order_notional_usd <= float(HARD_MAX_ORDER_NOTIONAL_USD)
    assert caps.max_open_exposure_usd <= float(HARD_MAX_DAILY_NOTIONAL_USD)
    assert caps.max_event_exposure_usd <= float(HARD_MAX_DAILY_NOTIONAL_USD)
    assert caps.max_strategy_exposure_usd <= float(HARD_MAX_DAILY_NOTIONAL_USD)
    assert caps.max_bregman_bundle_capital_lock_usd <= float(HARD_MAX_DAILY_NOTIONAL_USD)
    assert caps.max_daily_loss_usd <= float(HARD_MAX_DAILY_NOTIONAL_USD)
    assert caps.max_orders_per_day <= 3


def test_to_dict_is_serializable():
    d = CanaryCaps().to_dict()
    assert "max_order_notional_usd" in d
    assert "max_bregman_bundle_capital_lock_usd" in d

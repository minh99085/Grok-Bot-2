import os

import pytest

from engine.robinhood.config import RobinhoodConfig
from engine.robinhood.safety_gates import RobinhoodSafetyGates


@pytest.fixture
def gates(tmp_path, monkeypatch):
    monkeypatch.setenv("RH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RH_LIVE_TRADING_ENABLED", "1")
    cfg = RobinhoodConfig.from_env()
    return RobinhoodSafetyGates(cfg)


def test_blocks_live_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("RH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RH_LIVE_TRADING_ENABLED", "0")
    cfg = RobinhoodConfig.from_env()
    g = RobinhoodSafetyGates(cfg)
    v = g.evaluate("place_equity_order", {"symbol": "AAPL", "notional": 10})
    assert not v.allowed
    assert v.reason == "live_trading_disabled"


def test_blocks_oversized_notional(gates):
    v = gates.evaluate("place_equity_order", {"symbol": "AAPL", "notional": 500})
    assert not v.allowed
    assert "exceeds max" in v.reason


def test_requires_review_above_threshold(gates):
    v = gates.evaluate("place_equity_order", {"symbol": "AAPL", "notional": 75})
    assert v.allowed
    assert v.review_required
    assert v.review_tool == "review_equity_order"


def test_pdt_limit(gates):
    for _ in range(3):
        gates.day_trades.record()
    v = gates.evaluate("place_equity_order", {"symbol": "AAPL", "notional": 10})
    assert not v.allowed
    assert "pdt_limit" in v.reason


def test_daily_loss_limit(gates):
    gates.record_realized_pnl(-250)
    v = gates.evaluate("place_equity_order", {"symbol": "AAPL", "notional": 10})
    assert not v.allowed
    assert v.reason == "daily_loss_limit_reached"


def test_concentration_check(gates):
    portfolio = {"total_value": 1000, "buying_power": 500, "positions": []}
    v = gates.evaluate(
        "place_equity_order",
        {"symbol": "AAPL", "notional": 200},
        portfolio=portfolio,
    )
    assert not v.allowed
    assert "exceeds max" in v.reason


def test_read_tool_passes(gates):
    v = gates.evaluate("get_portfolio", {})
    assert v.allowed
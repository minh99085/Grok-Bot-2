"""Realistic CLOB v2 fill simulator — fills are never guaranteed.

Quant scope — *CLOB v2 Execution* + *Probabilistic Fill Modeling* + *Backtesting
& Simulation*: proves the fill-probability model responds monotonically to order
size, depth, spread, book age, volatility, queue, aggressiveness, time-to-
resolution, and recent trade velocity, that conservative mode is strictly more
pessimistic, and that the PaperBroker realistic path never guarantees a fill.
PAPER ONLY.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from engine.execution.paper_broker import PaperBroker, RealisticFillModel


def _fp(model, **kw):
    base = dict(spread=0.02, depth_usd=5000.0, order_usd=200.0, book_age_ms=0.0,
                volatility=0.0, queue_proxy=0.0, aggressiveness=1.0, stale=False)
    base.update(kw)
    return model.fill_probability(**base)


def test_fill_probability_monotone_in_every_factor():
    m = RealisticFillModel()
    # order size up -> prob down
    assert _fp(m, order_usd=100.0) > _fp(m, order_usd=10000.0)
    # depth up -> prob up
    assert _fp(m, depth_usd=10000.0) > _fp(m, depth_usd=500.0)
    # spread up -> prob down
    assert _fp(m, spread=0.005) > _fp(m, spread=0.07)
    # book age up -> prob down
    assert _fp(m, book_age_ms=0.0) > _fp(m, book_age_ms=2500.0)
    # volatility up -> prob down
    assert _fp(m, volatility=0.0) > _fp(m, volatility=0.3)
    # queue further back -> prob down
    assert _fp(m, queue_proxy=0.0) > _fp(m, queue_proxy=0.8)
    # more aggressive (crosses deeper) -> prob up
    assert _fp(m, aggressiveness=2.0) > _fp(m, aggressiveness=0.5)


def test_fill_probability_uses_ttr_and_trade_velocity():
    m = RealisticFillModel()
    # very short time-to-resolution dampens fills vs a long horizon
    short = _fp(m, time_to_resolution_s=60.0)
    long = _fp(m, time_to_resolution_s=7 * 86400.0)
    assert long > short
    # higher recent trade velocity -> more fills
    quiet = _fp(m, recent_trade_velocity=0.0)
    busy = _fp(m, recent_trade_velocity=2.0)
    assert busy > quiet


def test_stale_book_never_fills():
    m = RealisticFillModel()
    assert _fp(m, stale=True) == 0.0
    assert _fp(m, depth_usd=0.0) == 0.0


def test_conservative_mode_is_strictly_more_pessimistic():
    normal = RealisticFillModel()
    cons = RealisticFillModel(conservative=True)
    kw = dict(spread=0.03, depth_usd=3000.0, order_usd=1000.0, volatility=0.1)
    assert cons.fill_probability(**kw) < normal.fill_probability(**kw)
    # conservative fill fraction is also no larger
    assert (cons.fill_fraction(order_usd=5000.0, depth_usd=3000.0)
            <= normal.fill_fraction(order_usd=5000.0, depth_usd=3000.0))


def test_paper_broker_realistic_fill_is_not_guaranteed():
    # a large order against thin depth must NOT fully fill under realistic mode
    from engine.execution.types import OrderRequest, OrderSide, OrderType, TimeInForce

    class _Book:
        bids = {Decimal("0.49"): Decimal("100")}
        asks = {Decimal("0.50"): Decimal("100")}   # ~ $50 of depth
        best_bid = Decimal("0.49")
        best_ask = Decimal("0.50")
        spread = Decimal("0.01")
        resolved = False

        def is_stale(self, _ms):
            return False

    broker = PaperBroker(realistic=True)
    order = OrderRequest(
        client_order_id="coid-thin-1", venue="polymarket", market_id="m1",
        asset_id="a1", side=OrderSide.BUY, order_type=OrderType.MARKETABLE_LIMIT,
        limit_price=Decimal("0.50"), quantity=Decimal("100000"),  # ~$50k vs $50 depth
        time_in_force=TimeInForce.IOC)
    res = broker.execute(order, book=_Book())
    # realistic mode: either no fill (lost the probabilistic draw) or a partial —
    # NEVER a full guaranteed fill of a $50k order against $50 of depth.
    assert res.filled_quantity < order.quantity

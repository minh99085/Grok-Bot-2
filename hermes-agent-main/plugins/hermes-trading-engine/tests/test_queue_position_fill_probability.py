"""Queue-position-aware fill probability (paper/replay forward estimates).

Quant scope — *Statistical & Probabilistic Modeling* + *CLOB v2 Execution*:
proves the queue-position approximation and that the forward fill-probability
estimate responds to queue depth, price aggressiveness, time-to-resolution, and
recent trade velocity. Analytics only — never places or sizes an order.
"""

from __future__ import annotations

import pytest

from engine.training.execution_quality import (
    fill_probability, queue_position_approximation)


def test_queue_position_front_to_back():
    front = queue_position_approximation(ahead_size=0.0, order_size=100.0)
    mid = queue_position_approximation(ahead_size=100.0, order_size=100.0)
    back = queue_position_approximation(ahead_size=1000.0, order_size=100.0)
    assert front < mid < back
    assert 0.0 <= front and back <= 1.0


def test_refreshed_depth_pushes_us_further_back():
    base = queue_position_approximation(ahead_size=100.0, order_size=100.0)
    refreshed = queue_position_approximation(ahead_size=100.0, order_size=100.0,
                                             refreshed_depth=300.0)
    assert refreshed > base


def _fp(**kw):
    base = dict(spread=0.02, depth_usd=5000.0, order_usd=200.0)
    base.update(kw)
    return fill_probability(**base)


def test_forward_fill_probability_monotone_in_queue_and_aggressiveness():
    assert _fp(queue_proxy=0.0) > _fp(queue_proxy=0.8)
    assert _fp(aggressiveness=2.0) > _fp(aggressiveness=0.5)


def test_forward_fill_probability_uses_ttr_and_velocity():
    assert _fp(time_to_resolution_s=7 * 86400.0) > _fp(time_to_resolution_s=30.0)
    assert _fp(recent_trade_velocity=2.0) > _fp(recent_trade_velocity=0.0)


def test_forward_fill_probability_conservative_is_lower():
    assert _fp(conservative=True) < _fp(conservative=False)


def test_backward_compatible_three_arg_call():
    # the original (spread, depth, order) call still works unchanged
    assert 0.0 <= fill_probability(0.02, 5000.0, 200.0) <= 1.0
    assert fill_probability(0.02, 5000.0, 200.0, stale=True) == 0.0

"""Tests for Bregman certificate executable-depth gating + certified sizing.

Certified arbs may size larger ONLY when all legs pass executable depth and the
worst-case payoff proof holds; otherwise size is zero.
"""

from __future__ import annotations

from engine.arbitrage.certificate import (
    FeeModel,
    certified_trade_size,
    certify_group,
)
from engine.arbitrage.constraint_graph import ConstraintGraph, Outcome


def _underpriced_complement(depth_a=100, depth_b=100):
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="a", price=0.40, ask=0.40, ask_depth=depth_a))
    g.add_outcome(Outcome(id="b", price=0.40, ask=0.40, ask_depth=depth_b))
    g.add_complement("a", "b")
    return g


def test_certified_when_depth_and_profit_ok():
    g = _underpriced_complement()
    cert = certify_group(g, g.constraints()[0], fee_model=FeeModel())
    assert cert.certified is True
    assert cert.executable_depth_ok is True
    assert cert.size > 0
    assert cert.min_leg_depth == 100


def test_zero_depth_blocks_certification():
    g = _underpriced_complement(depth_a=0)
    cert = certify_group(g, g.constraints()[0])
    assert cert.certified is False
    assert cert.executable_depth_ok is False
    assert cert.size == 0.0
    assert certified_trade_size(cert, equity=1000) == 0.0


def test_min_leg_depth_requirement():
    g = _underpriced_complement(depth_a=5, depth_b=100)
    # require >=10 shares on every leg; thinnest is 5 -> blocked
    cert = certify_group(g, g.constraints()[0], min_leg_depth=10)
    assert cert.executable_depth_ok is False
    assert cert.certified is False
    assert cert.reason == "insufficient_executable_depth"


def test_fairly_priced_not_certified_even_with_depth():
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="a", price=0.50, ask=0.50, ask_depth=100))
    g.add_outcome(Outcome(id="b", price=0.50, ask=0.50, ask_depth=100))
    g.add_complement("a", "b")
    cert = certify_group(g, g.constraints()[0])
    assert cert.certified is False
    assert cert.reason == "no_positive_worst_case_profit"
    assert certified_trade_size(cert, equity=1000) == 0.0


def test_certified_trade_size_scales_with_depth_and_equity_cap():
    g = _underpriced_complement(depth_a=1000, depth_b=1000)
    cert = certify_group(g, g.constraints()[0])
    # depth allows 1000 sets, cost ~0.8/set; equity cap 0.5*1000/0.8 = 625
    sized = certified_trade_size(cert, equity=1000, max_frac=0.5)
    assert 0 < sized <= 1000
    assert sized <= (0.5 * 1000) / cert.cost_per_set + 1e-6


def test_certified_trade_size_zero_for_uncertified():
    class _FakeCert:
        certified = False
        executable_depth_ok = True
        size = 100.0
        cost_per_set = 0.8
    assert certified_trade_size(_FakeCert(), equity=1000) == 0.0
    assert certified_trade_size(None, equity=1000) == 0.0


def test_fees_can_block_certification():
    g = _underpriced_complement()  # 0.40+0.40 = 0.80, gross edge 0.20/set
    # huge taker fee wipes the edge -> not certified
    cert = certify_group(g, g.constraints()[0],
                         fee_model=FeeModel(taker_fee_bps=5000))
    assert cert.certified is False
    assert cert.reason == "no_positive_worst_case_profit"

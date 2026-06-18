"""6D: cost-model refinement — size/depth-aware market impact, partial-fill, and a
slippage forecast-error band, plus maker/taker fee selection.

All additions only ever make a paper fill WORSE (conservative). With the legacy
defaults (no size params) drag_breakdown is byte-identical to the prior model, so the
Bregman certifier (which passes no size params) is UNCHANGED.
"""

from __future__ import annotations

from engine.execution.slippage import drag_breakdown
from engine.training.config import TrainingConfig
from engine.training.paper_execution import (PaperExecutionContext, PaperExecutionPolicy,
                                             SRC_LIVE_CLOB)


def test_legacy_call_is_unchanged():
    b = drag_breakdown(0.30, 0.28, 0.01, slippage_bps=25.0, fee_bps=0.0)
    assert b["market_impact"] == 0.0
    assert b["slippage_error_band"] == 0.0
    assert b["partial_fill_expected"] is False
    assert b["fillable_fraction"] == 1.0
    # exec price = tick-up + bps slippage only (no impact)
    assert b["exec_price"] == round(0.30 + 0.30 * 0.0025, 8)


def test_size_aware_costs_more_than_legacy():
    legacy = drag_breakdown(0.30, 0.28, 0.01, slippage_bps=25.0, fee_bps=0.0)
    sized = drag_breakdown(0.30, 0.28, 0.01, slippage_bps=25.0, fee_bps=0.0,
                           order_usd=5.0, depth_usd=100.0, impact_coeff=0.5, error_coeff=50.0)
    assert sized["market_impact"] > 0.0
    assert sized["exec_price"] > legacy["exec_price"]
    assert sized["depth_share"] == 0.05 and sized["fillable_fraction"] == 1.0


def test_oversized_order_flags_partial_fill_and_heavier_impact():
    big = drag_breakdown(0.30, 0.28, 0.01, slippage_bps=25.0, fee_bps=0.0,
                         order_usd=200.0, depth_usd=100.0, impact_coeff=0.5, error_coeff=50.0)
    assert big["partial_fill_expected"] is True
    assert big["fillable_fraction"] == 0.5            # only half fits the touch depth
    assert big["depth_share"] == 2.0


def test_only_ever_worse():
    # impact + error band can never reduce the executable price below the tick-up base
    base = drag_breakdown(0.40, 0.39, 0.01, slippage_bps=25.0, fee_bps=0.0)["exec_price"]
    sized = drag_breakdown(0.40, 0.39, 0.01, slippage_bps=25.0, fee_bps=0.0,
                           order_usd=50.0, depth_usd=60.0, impact_coeff=0.5, error_coeff=50.0)
    assert sized["exec_price"] >= base


def test_policy_after_cost_is_size_aware_and_shrinks_edge():
    cfg = TrainingConfig.aggressive_paper()
    pol = PaperExecutionPolicy(cfg)
    # a small, deep-book order vs a large order against the same book: the larger order
    # has a smaller (or negative) after-cost edge because impact scales with depth share.
    def edge(notional):
        ctx = PaperExecutionContext(fill_source=SRC_LIVE_CLOB, ask=0.30, bid=0.28,
                                    spread=0.02, depth_usd=40.0, tick_size=0.01,
                                    notional_usd=notional, gross_edge=0.05,
                                    fresh_book=True, accepting_orders=True)
        return pol._after_cost(ctx)["after_cost_edge"]
    small_edge = edge(2.0)
    large_edge = edge(35.0)
    assert small_edge > large_edge        # bigger order eats more impact
    assert pol.cost_model_size_aware is True


def test_maker_vs_taker_fee_selection():
    cfg = TrainingConfig.aggressive_paper()
    cfg.taker_fee_bps = 30.0
    cfg.maker_fee_bps = 10.0
    pol = PaperExecutionPolicy(cfg)
    # paper crosses the spread -> charges the (worse) taker fee by default
    assert pol.fee_bps == 30.0
    assert pol.taker_fee_bps == 30.0 and pol.maker_fee_bps == 10.0


def test_size_aware_can_be_disabled():
    cfg = TrainingConfig.aggressive_paper()
    cfg.cost_model_size_aware = False
    pol = PaperExecutionPolicy(cfg)
    assert pol.impact_coeff == 0.0 and pol.slippage_error_coeff == 0.0
    ctx = PaperExecutionContext(fill_source=SRC_LIVE_CLOB, ask=0.30, bid=0.28, spread=0.02,
                                depth_usd=10.0, tick_size=0.01, notional_usd=50.0,
                                gross_edge=0.05, fresh_book=True, accepting_orders=True)
    drag = pol._after_cost(ctx)["drag"]
    assert drag["market_impact"] == 0.0 and drag["slippage_error_band"] == 0.0

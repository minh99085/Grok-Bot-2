"""Option A: size-accurate executable-depth requirement.

The fixed $25 depth gate rejected ~all books for $1-$10 paper probes. The required depth
now scales with the order notional (factor x notional), floored at min_depth_floor_usd and
capped at depth_requirement_cap_usd ($10). This is size-accurate realism — required depth =
the size we actually fill — not a blanket loosening; Bregman still sizes sets DOWN to real
depth. Base profile keeps the legacy fixed gate.
"""

from __future__ import annotations

import pytest

from engine.training.config import TrainingConfig, size_aware_min_depth_usd
from engine.training.bregman_execution import BregmanArbitrageEngine
from engine.training.paper_execution import (PaperExecutionPolicy, PaperExecutionContext,
                                             SRC_LIVE_CLOB, EXECUTABLE, SHADOW)


def test_helper_scales_floors_and_caps():
    agg = TrainingConfig.aggressive_paper()
    assert size_aware_min_depth_usd(agg, 2.0, fallback=25.0) == 2.0
    assert size_aware_min_depth_usd(agg, 10.0, fallback=25.0) == 10.0
    assert size_aware_min_depth_usd(agg, 0.5, fallback=25.0) == 1.0       # floor
    assert size_aware_min_depth_usd(agg, 50.0, fallback=25.0) == 10.0     # cap ($10)
    assert size_aware_min_depth_usd(agg, 0.0, fallback=25.0) == 25.0      # size unknown -> fallback


def test_base_profile_uses_fixed_fallback():
    base = TrainingConfig()
    assert base.size_aware_depth_enabled is False
    assert size_aware_min_depth_usd(base, 2.0, fallback=25.0) == 25.0


def test_bregman_certifier_floor_drops_to_cap():
    agg = TrainingConfig.aggressive_paper()
    e = BregmanArbitrageEngine(cfg=agg)
    assert e._effective_min_depth_usd() == 10.0          # was 25
    base = BregmanArbitrageEngine(cfg=TrainingConfig())
    assert base._effective_min_depth_usd() == base.min_depth_usd  # unchanged


def _ctx(depth, notional):
    return PaperExecutionContext(fill_source=SRC_LIVE_CLOB, ask=0.30, bid=0.29, spread=0.01,
                                 depth_usd=depth, tick_size=0.01, notional_usd=notional,
                                 gross_edge=0.05, fresh_book=True, accepting_orders=True)


def test_directional_thin_book_now_executable_for_small_order():
    agg = TrainingConfig.aggressive_paper()
    pol = PaperExecutionPolicy(agg)
    # $12 depth: rejected under the old fixed $25 gate, but ample for a $2 order under
    # Option A (small depth-share -> low impact -> positive after cost -> executable).
    d = pol.evaluate(_ctx(depth=12.0, notional=2.0))
    assert d.mode == EXECUTABLE


def test_old_gate_would_have_rejected_same_book():
    # same $12 book under the base (fixed $25) profile -> SHADOW thin_depth (proves the
    # unlock is Option A, not the book)
    base = TrainingConfig()
    pol = PaperExecutionPolicy(base)
    d = pol.evaluate(_ctx(depth=12.0, notional=2.0))
    assert d.mode == SHADOW and d.reason == "thin_depth"


def test_directional_still_rejects_when_depth_below_order_size():
    agg = TrainingConfig.aggressive_paper()
    pol = PaperExecutionPolicy(agg)
    # $1 of depth cannot support a $5 order -> still SHADOW thin_depth (size-accurate)
    d = pol.evaluate(_ctx(depth=1.0, notional=5.0))
    assert d.mode == SHADOW and d.reason == "thin_depth"


def test_base_profile_keeps_strict_gate():
    base = TrainingConfig()
    pol = PaperExecutionPolicy(base)
    # $12 depth, $2 order: base profile still requires the fixed $25 -> SHADOW
    d = pol.evaluate(_ctx(depth=12.0, notional=2.0))
    assert d.mode == SHADOW and d.reason == "thin_depth"

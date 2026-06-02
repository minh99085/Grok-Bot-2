"""Fractional-Kelly sizing with hard risk haircuts (capital allocation).

Quant scope — *Risk Management & Portfolio Optimization*: proves the
capital-allocation Kelly haircut shrinks size monotonically for every risk
factor (uncertainty, calibration error, low liquidity, wide spread, slippage,
poor label quality, event correlation, settlement ambiguity, adverse-selection
markout), never *increases* a base size, is bounded to ``[0, 1]``, and collapses
toward zero when every factor is at its worst. PAPER ONLY — sizing analytics.
"""

from __future__ import annotations

import pytest

from engine.training.capital_allocator import (
    kelly_haircut, kelly_haircut_components, kelly_haircut_size_usd)


def _neutral():
    return dict(uncertainty=0.0, calibration_error=0.0, liquidity=1.0, spread=0.0,
                slippage=0.0, label_quality=1.0, event_correlation=0.0,
                settlement_ambiguity=0.0, adverse_selection=0.0)


def test_neutral_inputs_give_full_size():
    assert kelly_haircut(**_neutral()) == pytest.approx(1.0, abs=1e-9)


def test_haircut_is_bounded_unit_interval():
    # random-ish stress combinations all stay within [0, 1]
    for u in (0.0, 0.3, 1.0):
        for liq in (0.0, 0.5, 1.0):
            for amb in (0.0, 0.5, 1.0):
                f = kelly_haircut(uncertainty=u, liquidity=liq, settlement_ambiguity=amb)
                assert 0.0 <= f <= 1.0


@pytest.mark.parametrize("field,worse", [
    ("uncertainty", 0.8),
    ("calibration_error", 0.8),
    ("spread", 0.8),
    ("slippage", 0.8),
    ("event_correlation", 0.8),
    ("settlement_ambiguity", 0.8),
    ("adverse_selection", 0.8),
])
def test_risk_factors_are_monotonic_down(field, worse):
    base = _neutral()
    f0 = kelly_haircut(**base)
    bad = dict(base)
    bad[field] = worse
    f1 = kelly_haircut(**bad)
    assert f1 < f0
    assert f1 <= 1.0


@pytest.mark.parametrize("field", ["liquidity", "label_quality"])
def test_quality_factors_are_monotonic_up(field):
    # lower quality => smaller size
    base = _neutral()
    good = kelly_haircut(**base)
    bad = dict(base)
    bad[field] = 0.1
    worse = kelly_haircut(**bad)
    assert worse < good


def test_all_factors_worst_collapses_to_near_zero():
    f = kelly_haircut(uncertainty=1.0, calibration_error=1.0, liquidity=0.0,
                      spread=1.0, slippage=1.0, label_quality=0.0,
                      event_correlation=1.0, settlement_ambiguity=1.0,
                      adverse_selection=1.0)
    assert f < 0.05


def test_components_match_factor_product():
    comps = kelly_haircut_components(uncertainty=0.4, liquidity=0.6, spread=0.2)
    prod = 1.0
    for v in comps.values():
        assert 0.0 <= v <= 1.0
        prod *= v
    assert kelly_haircut(uncertainty=0.4, liquidity=0.6, spread=0.2) == pytest.approx(
        prod, abs=1e-9)


def test_haircut_size_never_exceeds_base_or_cap():
    base_kelly = 8.0
    # heavy haircut
    sz = kelly_haircut_size_usd(base_kelly, max_size_usd=5.0,
                                uncertainty=0.5, settlement_ambiguity=0.4)
    assert 0.0 <= sz <= base_kelly
    assert sz <= 5.0


def test_haircut_size_respects_hard_cap_even_with_no_haircut():
    sz = kelly_haircut_size_usd(100.0, max_size_usd=5.0)  # neutral haircut -> factor 1
    assert sz == pytest.approx(5.0)


def test_haircut_never_increases_size_for_any_single_factor():
    base_kelly = 6.0
    full = kelly_haircut_size_usd(base_kelly, max_size_usd=50.0)
    for field in ("uncertainty", "calibration_error", "spread", "slippage",
                  "event_correlation", "settlement_ambiguity", "adverse_selection"):
        sz = kelly_haircut_size_usd(base_kelly, max_size_usd=50.0, **{field: 0.5})
        assert sz <= full

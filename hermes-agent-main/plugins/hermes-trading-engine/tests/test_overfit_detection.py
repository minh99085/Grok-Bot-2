"""Overfit detection + overfit-penalized parameters.

Quant scope — *Statistical Modeling* + *Risk/Portfolio Optimization* +
*Bregman arbitrage robustness*: proves the in-sample/out-of-sample overfit
detector, the monotone overfit penalty, the conservative shrink of
thresholds/shrink-factors/risk-sizes/exploration as the penalty rises, and the
Bregman false-positive arbitrage robustness check.
"""

from __future__ import annotations

import pytest

from engine.training.edge_engine import overfit_adjusted_min_edge
from engine.training.overfit_governor import (
    OverfitDetector, bregman_false_positive_robustness, overfit_penalized_params,
    overfit_penalty)
from engine.training.probability_stack import overfit_adjusted_shrink


# --------------------------------------------------------------------------- #
# overfit penalty (scalar)
# --------------------------------------------------------------------------- #
def test_overfit_penalty_zero_when_oos_matches_is():
    assert overfit_penalty(1.0, 1.0, higher_better=True) == pytest.approx(0.0)


def test_overfit_penalty_monotone_higher_better():
    small = overfit_penalty(1.0, 0.9, higher_better=True)
    big = overfit_penalty(1.0, 0.2, higher_better=True)
    assert 0.0 < small < big <= 1.0


def test_overfit_penalty_lower_better_metric():
    # Brier/log-loss/ECE: OOS WORSE means OOS > IS
    p = overfit_penalty(0.10, 0.30, higher_better=False)
    assert p > 0.5
    assert overfit_penalty(0.10, 0.10, higher_better=False) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# overfit detector (IS vs OOS metric bundle)
# --------------------------------------------------------------------------- #
def test_detector_clean_when_oos_tracks_is():
    det = OverfitDetector()
    v = det.detect({"sharpe": 1.0, "brier": 0.18, "ece": 0.03, "realized_edge": 0.02},
                   {"sharpe": 0.95, "brier": 0.19, "ece": 0.035, "realized_edge": 0.018})
    assert v.overfit is False
    assert v.score < 0.5


def test_detector_flags_sharpe_collapse():
    det = OverfitDetector()
    v = det.detect({"sharpe": 2.4, "brier": 0.10},
                   {"sharpe": 0.1, "brier": 0.28})
    assert v.overfit is True
    assert v.reasons
    assert v.score > 0.5


def test_detector_flags_calibration_blowup():
    det = OverfitDetector()
    v = det.detect({"sharpe": 1.0, "ece": 0.02}, {"sharpe": 0.95, "ece": 0.20})
    assert v.overfit is True
    assert any("ece" in r for r in v.reasons)


# --------------------------------------------------------------------------- #
# overfit-penalized parameters (thresholds / shrink / risk / exploration)
# --------------------------------------------------------------------------- #
_CONS = {"min_net_edge": 0.05, "base_shrink_factor": 0.20,
         "fixed_notional_usd": 2.0, "exploration_rate": 0.0}


def test_penalized_params_zero_penalty_is_identity():
    agg = {"min_net_edge": 0.005, "base_shrink_factor": 0.45,
           "fixed_notional_usd": 5.0, "exploration_rate": 0.25}
    out = overfit_penalized_params(agg, 0.0, conservative=_CONS)
    assert out == agg


def test_penalized_params_full_penalty_is_conservative():
    agg = {"min_net_edge": 0.005, "base_shrink_factor": 0.45,
           "fixed_notional_usd": 5.0, "exploration_rate": 0.25}
    out = overfit_penalized_params(agg, 1.0, conservative=_CONS)
    for k, v in _CONS.items():
        assert out[k] == pytest.approx(v)


def test_penalized_params_tightens_with_penalty():
    agg = {"min_net_edge": 0.005, "fixed_notional_usd": 5.0, "exploration_rate": 0.25}
    out = overfit_penalized_params(agg, 0.5, conservative=_CONS)
    # threshold rises toward conservative, size + exploration shrink
    assert out["min_net_edge"] > agg["min_net_edge"]
    assert out["fixed_notional_usd"] < agg["fixed_notional_usd"]
    assert out["exploration_rate"] < agg["exploration_rate"]


def test_edge_and_shrink_helpers_track_penalty():
    base = overfit_adjusted_min_edge(0.005, 0.0, conservative=0.05)
    high = overfit_adjusted_min_edge(0.005, 1.0, conservative=0.05)
    assert base == pytest.approx(0.005)
    assert high == pytest.approx(0.05)
    # shrink pulls toward the conservative (lower) shrink as penalty rises
    s0 = overfit_adjusted_shrink(0.45, 0.0, conservative=0.2)
    s1 = overfit_adjusted_shrink(0.45, 1.0, conservative=0.2)
    assert s0 == pytest.approx(0.45)
    assert s1 == pytest.approx(0.2)


# --------------------------------------------------------------------------- #
# Bregman false-positive arbitrage robustness
# --------------------------------------------------------------------------- #
def test_bregman_fp_robustness_clean():
    certs = [{"certified_profit": 0.5, "realized_pnl": 0.4, "all_leg_fill_prob": 0.99},
             {"certified_profit": 0.3, "realized_pnl": 0.25, "all_leg_fill_prob": 0.98}]
    rep = bregman_false_positive_robustness(certs)
    assert rep["false_positives"] == 0
    assert rep["fp_rate"] == pytest.approx(0.0)
    assert rep["robust"] is True


def test_bregman_fp_robustness_flags_false_positive():
    # certified risk-free but settled to a LOSS -> false-positive arbitrage
    certs = [{"certified_profit": 0.5, "realized_pnl": -0.2, "all_leg_fill_prob": 0.6},
             {"certified_profit": 0.4, "realized_pnl": -0.1, "all_leg_fill_prob": 0.5},
             {"certified_profit": 0.6, "realized_pnl": 0.5, "all_leg_fill_prob": 0.99}]
    rep = bregman_false_positive_robustness(certs, max_fp_rate=0.1)
    assert rep["false_positives"] == 2
    assert rep["fp_rate"] > 0.1
    assert rep["robust"] is False

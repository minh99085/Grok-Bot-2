"""Tests for ablation attribution + production-readiness separation."""

from __future__ import annotations

from engine.strategies.strategy_attribution import (
    ABLATION_COMPONENTS,
    ablation_report,
    production_readiness,
)


def test_ablation_components_cover_required():
    for c in ("bregman", "chainlink", "fast_btc", "news", "grok", "calibration"):
        assert c in ABLATION_COMPONENTS


def test_ablation_contribution_positive_when_component_helps():
    # baseline sharpe 1.5; removing bregman drops to 0.5 -> contribution 1.0
    rep = ablation_report(1.5, {"bregman": 0.5, "news": 1.49, "grok": 1.6},
                          metric_name="sharpe", min_contribution=0.05)
    assert rep["components"]["bregman"]["contribution"] == 1.0
    assert rep["components"]["bregman"]["necessary"] is True
    # news barely matters (contribution ~0.01 < 0.05) -> not necessary
    assert rep["components"]["news"]["necessary"] is False
    # grok HURTS (removing it improved the metric) -> harmful
    assert rep["components"]["grok"]["harmful"] is True
    assert "grok" in rep["harmful"]


def test_ablation_ranking_orders_by_contribution():
    rep = ablation_report(2.0, {"a": 0.0, "b": 1.0, "c": 1.9})
    assert rep["ranking"] == ["a", "b", "c"]


def test_production_ready_true_when_all_gates_pass():
    out = production_readiness(
        validation={"n_validation": 100, "validation_pnl": 12.0},
        exploration={"exploration_pnl": 3.0},
        significance={"passed": True},
        ablations={"harmful": []},
        overfit=False,
        min_validation_trades=50)
    assert out["production_ready"] is True
    assert out["blocking_reasons"] == []
    assert out["exploration_excluded_from_readiness"] is True


def test_production_blocked_by_insufficient_trades():
    out = production_readiness(validation={"n_validation": 10},
                              significance={"passed": True}, min_validation_trades=50)
    assert out["production_ready"] is False
    assert any("insufficient_validation_trades" in r for r in out["blocking_reasons"])


def test_production_blocked_by_failed_significance():
    out = production_readiness(validation={"n_validation": 100},
                              significance={"passed": False})
    assert out["production_ready"] is False
    assert "significance_gate_failed" in out["blocking_reasons"]


def test_production_blocked_by_harmful_ablation():
    out = production_readiness(validation={"n_validation": 100},
                              significance={"passed": True},
                              ablations={"harmful": ["grok"]})
    assert out["production_ready"] is False
    assert any("harmful_components" in r for r in out["blocking_reasons"])


def test_production_blocked_by_overfit():
    out = production_readiness(validation={"n_validation": 100},
                              significance={"passed": True}, overfit=True)
    assert out["production_ready"] is False
    assert "overfit_flagged" in out["blocking_reasons"]


def test_exploration_never_in_verdict():
    # huge exploration PnL must not make it production ready
    out = production_readiness(validation={"n_validation": 0},
                              exploration={"exploration_pnl": 1e9},
                              significance={"passed": True})
    assert out["production_ready"] is False

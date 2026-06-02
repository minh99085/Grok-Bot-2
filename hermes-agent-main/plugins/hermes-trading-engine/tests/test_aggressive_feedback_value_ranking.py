"""Feedback-value scoring + aggressive ranking.

``feedback_value_score`` rewards where a paper trade teaches the model the most:
uncertainty, category under-sampling, liquidity quality, time-to-resolution,
Chainlink relevance, calibration weakness, Bregman-group relevance, expected
label availability. Aggressive mode then increases USEFUL feedback samples per
risk unit vs. a naive (edge-ordered) fill. PAPER-ONLY.
"""

from __future__ import annotations

from types import SimpleNamespace

from engine.training.active_learning import (
    ActiveLearningSelector,
    FeedbackValueWeights,
    feedback_value_score,
)


def _base(**kw):
    f = dict(uncertainty=0.3, category_samples=10, category_target=50,
             liquidity_quality=0.7, time_to_resolution_s=5 * 86400,
             chainlink_relevance=0.2, calibration_gap=0.05, bregman_relevance=0.0,
             expected_label_availability=0.8)
    f.update(kw)
    return f


def _score(**kw):
    return feedback_value_score(**_base(**kw))[0]


def test_score_in_unit_interval_and_components():
    s, comp = feedback_value_score(**_base())
    assert 0.0 <= s <= 1.0
    for k in ("uncertainty", "category_undersampling", "liquidity_quality",
              "time_to_resolution", "chainlink_relevance", "calibration_gap",
              "bregman_relevance", "expected_label_availability"):
        assert k in comp


def test_higher_uncertainty_increases_value():
    assert _score(uncertainty=0.9) > _score(uncertainty=0.1)


def test_category_undersampling_increases_value():
    # few samples vs. far over target
    assert _score(category_samples=1) > _score(category_samples=500)


def test_calibration_weakness_increases_value():
    assert _score(calibration_gap=0.25) > _score(calibration_gap=0.0)


def test_chainlink_relevance_increases_value():
    assert _score(chainlink_relevance=0.9) > _score(chainlink_relevance=0.0)


def test_bregman_relevance_increases_value():
    assert _score(bregman_relevance=0.9) > _score(bregman_relevance=0.0)


def test_label_availability_increases_value():
    assert _score(expected_label_availability=0.95) > _score(expected_label_availability=0.1)


def test_low_liquidity_reduces_value():
    assert _score(liquidity_quality=0.1) < _score(liquidity_quality=0.95)


def test_weights_sum_to_one():
    w = FeedbackValueWeights()
    assert abs(w.total() - 1.0) < 1e-9


def _cfg(**kw):
    base = dict(active_learning_enabled=True, exploration_split=1.0,
                exploration_min_edge=-0.05, exploration_notional_usd=2.0,
                exploration_budget_usd=12.0, category_sample_target=50,
                max_explore_per_category=10, max_explore_per_event=1)
    base.update(kw)
    return SimpleNamespace(**base)


def test_aggressive_increases_feedback_per_risk_unit():
    # Pool of near-miss candidates: some high feedback value (under-sampled,
    # uncertain), some low (over-sampled, certain) but with HIGHER net_edge.
    pool = []
    for i in range(6):
        high_fv = i < 3
        pool.append({
            "market_id": f"m{i}", "category": f"cat{i}", "group_key": f"g{i}",
            "edge_reason": "edge_too_low",
            "net_edge": 0.001 if high_fv else 0.02,    # naive (edge) prefers the LOW-value ones
            "feedback_value": 0.9 if high_fv else 0.2,
        })
    cfg = _cfg()
    al = ActiveLearningSelector(cfg).select(pool, budget=3)

    # Naive fill: take the highest net_edge near-misses (ignores feedback value).
    naive = sorted(pool, key=lambda c: c["net_edge"], reverse=True)[:3]

    def feedback_per_risk(selected_fv, n):
        spent = n * cfg.exploration_notional_usd
        return (sum(selected_fv) / spent) if spent else 0.0

    al_fb = [s["feedback_value"] for s in al.selected if s["mode"] == "feedback"]
    al_ratio = feedback_per_risk(al_fb, len(al_fb))
    naive_ratio = feedback_per_risk([c["feedback_value"] for c in naive], len(naive))

    assert al.diagnostics["selected_for_feedback"] == 3
    assert al_ratio > naive_ratio          # AL learns more per paper dollar at risk
    # AL picked the high-feedback-value markets
    assert {s["market_id"] for s in al.selected} == {"m0", "m1", "m2"}

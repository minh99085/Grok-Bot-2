"""Bregman/KL projection scaffold (WS4 Layer 2)."""

from __future__ import annotations

from engine.pulse.bregman_projection import (
    kl_divergence,
    projection_distance_nested,
    frank_wolfe_scaffold,
)


def test_kl_zero_at_equal():
    assert kl_divergence(0.5, 0.5) == 0.0


def test_projection_distance_nested_violation():
    d = projection_distance_nested(0.45, 0.55, epsilon=0.02)
    assert d["max_theoretical_profit_per_share"] == 0.1
    assert d["actionable_projection"] is True
    assert d["solver_status"] == "brute_force_lcmm"


def test_frank_wolfe_scaffold_logs():
    s = frank_wolfe_scaffold({"a": 0.5}, [{"type": "nested_implication", "weight": 0.1}])
    assert s["solver_status"] == "scaffold_only"
    assert s["iterations"] >= 1
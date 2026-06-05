"""Tests for implied-probability projection onto the constraint set + residuals."""

from __future__ import annotations

from engine.arbitrage.bregman_projection import (
    bregman_project,
    incoherence,
    kl_divergence,
    local_incoherence,
)
from engine.arbitrage.constraint_graph import ConstraintGraph, Outcome


def _complement(p_a, p_b, depth=100):
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="a", price=p_a, ask=p_a, ask_depth=depth))
    g.add_outcome(Outcome(id="b", price=p_b, ask=p_b, ask_depth=depth))
    g.add_complement("a", "b")
    return g


def test_coherent_complement_has_zero_residual():
    g = _complement(0.5, 0.5)
    proj = bregman_project(g.price_vector(), g.to_primitives())
    inc = incoherence(g.price_vector(), proj.x)
    assert inc["l1"] < 1e-9
    assert proj.max_violation < 1e-9


def test_incoherent_complement_has_positive_residual():
    g = _complement(0.40, 0.40)        # sums to 0.80 -> incoherent
    pv = g.price_vector()
    proj = bregman_project(pv, g.to_primitives())
    # projection restores sum == 1
    assert abs(proj.x["a"] + proj.x["b"] - 1.0) < 1e-6
    inc = incoherence(pv, proj.x)
    assert inc["l1"] > 0.0
    assert local_incoherence(pv, proj.x, ["a", "b"]) > 0.0


def test_multi_outcome_mece_normalizes():
    g = ConstraintGraph()
    for i, p in enumerate([0.3, 0.3, 0.3]):
        g.add_outcome(Outcome(id=f"o{i}", price=p, ask=p, ask_depth=100))
    g.add_mece(["o0", "o1", "o2"])
    proj = bregman_project(g.price_vector(), g.to_primitives())
    assert abs(sum(proj.x.values()) - 1.0) < 1e-6
    assert proj.max_violation < 1e-6


def test_kl_divergence_zero_for_identical():
    assert kl_divergence({"a": 0.5}, {"a": 0.5}) == 0.0
    assert kl_divergence({"a": 0.4}, {"a": 0.5}) > 0.0


def test_projection_deterministic():
    g = _complement(0.40, 0.45)
    a = bregman_project(g.price_vector(), g.to_primitives())
    b = bregman_project(g.price_vector(), g.to_primitives())
    assert a.x == b.x and a.kl_gap == b.kl_gap


def test_malformed_group_does_not_crash_projection():
    # primitive references an id not in the vector -> tolerated, no crash
    g = _complement(0.5, 0.5)
    prims = g.to_primitives()
    proj = bregman_project({"a": 0.5}, prims)   # missing "b"
    assert "a" in proj.x

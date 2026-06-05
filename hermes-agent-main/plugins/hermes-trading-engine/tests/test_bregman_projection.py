"""Tests for engine.arbitrage.bregman_projection (KL projection). Tests-first."""

from __future__ import annotations

from engine.arbitrage.bregman_projection import (bregman_project, incoherence,
                                                 kl_divergence, local_incoherence,
                                                 max_violation)
from engine.arbitrage.constraint_graph import Primitive


def test_complement_projects_to_sum_one():
    res = bregman_project({"a": 0.4, "b": 0.4},
                          [Primitive("sum", ["a", "b"], "==", 1.0)])
    assert abs(res.x["a"] - 0.5) < 1e-6 and abs(res.x["b"] - 0.5) < 1e-6
    assert res.converged and res.max_violation < 1e-6


def test_mece_three_normalizes():
    res = bregman_project({"x": 0.3, "y": 0.3, "z": 0.3},
                          [Primitive("sum", ["x", "y", "z"], "==", 1.0)])
    assert abs(sum(res.x.values()) - 1.0) < 1e-6
    for k in ("x", "y", "z"):
        assert abs(res.x[k] - 1 / 3) < 1e-6


def test_equal_projects_to_geomean():
    res = bregman_project({"a": 0.4, "b": 0.6}, [Primitive("equal", ["a", "b"])])
    assert abs(res.x["a"] - res.x["b"]) < 1e-9
    assert abs(res.x["a"] - (0.24 ** 0.5)) < 1e-4


def test_implies_fixes_violation_only():
    # a <= b violated (0.7 > 0.3) -> both move to geomean
    res = bregman_project({"a": 0.7, "b": 0.3}, [Primitive("implies", ["a", "b"])])
    assert res.x["a"] <= res.x["b"] + 1e-9
    assert abs(res.x["a"] - (0.21 ** 0.5)) < 1e-4
    # already satisfied -> unchanged
    res2 = bregman_project({"a": 0.2, "b": 0.8}, [Primitive("implies", ["a", "b"])])
    assert abs(res2.x["a"] - 0.2) < 1e-9 and abs(res2.x["b"] - 0.8) < 1e-9


def test_mutually_exclusive_only_projects_when_violated():
    # sum <= 1 violated (1.2) -> scaled down to 1
    res = bregman_project({"a": 0.6, "b": 0.6}, [Primitive("sum", ["a", "b"], "<=", 1.0)])
    assert abs(sum(res.x.values()) - 1.0) < 1e-6
    # sum <= 1 satisfied -> unchanged
    res2 = bregman_project({"a": 0.3, "b": 0.3}, [Primitive("sum", ["a", "b"], "<=", 1.0)])
    assert abs(res2.x["a"] - 0.3) < 1e-9


def test_coherent_input_is_fixed_point():
    res = bregman_project({"a": 0.5, "b": 0.5}, [Primitive("sum", ["a", "b"], "==", 1.0)])
    assert res.converged and res.iterations <= 2 and res.max_violation < 1e-9


def test_empty_primitives_returns_input():
    res = bregman_project({"a": 0.3}, [])
    assert res.x == {"a": 0.3} and res.converged


def test_incoherence_and_kl():
    inc = incoherence({"a": 0.4, "b": 0.4}, {"a": 0.5, "b": 0.5})
    assert inc["l1"] > 0 and inc["max_abs"] > 0 and inc["kl"] > 0
    assert kl_divergence({"a": 0.5}, {"a": 0.5}) == 0.0
    assert local_incoherence({"a": 0.4, "b": 0.4}, {"a": 0.5, "b": 0.5}, ["a"]) > 0


def test_max_violation_zero_when_coherent():
    prims = [Primitive("sum", ["a", "b"], "==", 1.0)]
    assert max_violation({"a": 0.5, "b": 0.5}, prims) < 1e-9
    assert max_violation({"a": 0.4, "b": 0.4}, prims) > 0.1

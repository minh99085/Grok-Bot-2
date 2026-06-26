"""Gated Bregman/KL projection for dependent market groups (WS4 Layer 2).

Only invoked for small dependent groups when ``PULSE_BREGMAN_PROJECTION_ENABLED=1``.
Single 2-outcome windows are trivial — callers must skip them. PAPER ONLY / observe-first.
"""

from __future__ import annotations

import math
from typing import Optional


def kl_divergence(p: float, q: float) -> Optional[float]:
    """KL(p || q) for binary probabilities."""
    try:
        eps = 1e-9
        p = max(eps, min(1.0 - eps, float(p)))
        q = max(eps, min(1.0 - eps, float(q)))
        return round(p * math.log(p / q) + (1.0 - p) * math.log((1.0 - p) / (1.0 - q)), 6)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _project_implication_feasible(parent_p: float, child_p: float) -> tuple[float, float]:
    """Feasible point on nested implication: parent_p >= child_p."""
    p = float(parent_p)
    c = float(child_p)
    if p >= c:
        return p, c
    # Raise parent to child (minimum KL move on parent holding child fixed).
    return c, c


def projection_distance_nested(
    parent_mid: float,
    child_mid: float,
    *,
    epsilon: float = 0.02,
) -> dict:
    """KL-style projection distance for one nested-implication pair.

    Returns diagnostics only — execution still requires VWAP validation elsewhere.
    """
    p_mid = float(parent_mid)
    c_mid = float(child_mid)
    violation = max(0.0, c_mid - p_mid)
    fp, fc = _project_implication_feasible(p_mid, c_mid)
    kl_parent = kl_divergence(p_mid, fp) or 0.0
    kl_child = kl_divergence(c_mid, fc) or 0.0
    dist = round(kl_parent + kl_child, 6)
    max_theoretical = round(violation, 6)
    actionable = violation > float(epsilon)
    return {
        "constraint_type": "nested_implication",
        "projection_distance": dist,
        "max_theoretical_profit_per_share": max_theoretical,
        "feasible_parent_p": round(fp, 6),
        "feasible_child_p": round(fc, 6),
        "solver_status": "brute_force_lcmm",
        "convergence_reason": "closed_form_implication",
        "iterations": 1,
        "actionable_projection": actionable,
        "note": "Layer-2 observe-only unless execute path validates VWAP fills.",
    }


def frank_wolfe_scaffold(
    prices: dict,
    constraints: list[dict],
    *,
    max_iterations: int = 10,
    alpha: float = 0.9,
) -> dict:
    """Minimal Frank-Wolfe scaffold for logging / lessons loop (no external solver).

    For production groups, plug OR-Tools/PuLP behind the IP oracle hook when group size warrants it.
    """
    iters = 0
    active_vertices: list = []
    status = "skipped_trivial"
    reason = "no_constraints"
    dist = 0.0
    if constraints:
        iters = min(1, max_iterations)
        active_vertices = [constraints[0].get("type", "unknown")]
        status = "scaffold_only"
        reason = "open_source_ip_oracle_not_wired"
        dist = float(alpha) * sum(float(c.get("weight") or 0.0) for c in constraints)
    return {
        "projection_distance": round(dist, 6),
        "solver_status": status,
        "convergence_reason": reason,
        "iterations": iters,
        "active_vertices": active_vertices,
        "alpha": alpha,
        "optimal_trade_vector": None,
        "executable_profit_after_depth": None,
    }
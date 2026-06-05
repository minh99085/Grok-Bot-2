"""Bregman / KL projection onto the coherent probability set (PAPER ONLY, pure).

Market-implied probabilities are frequently *incoherent*: complements that don't
sum to 1, MECE buckets that sum to != 1, cross-market equivalences priced apart,
etc. The coherent set is the convex set defined by the constraint primitives. We
find the nearest coherent vector under the **KL (Bregman) divergence** via cyclic
I-projections (closed-form per primitive), which converges for these convex
constraints. The gap between the market vector and its projection localizes the
mispricing and bounds where an arbitrage may exist (certification is separate).

Closed-form KL (I-)projections used:
* ``sum`` of a subset to ``c``: multiplicative scaling ``x_i *= c / sum`` (only
  applied when an inequality is violated).
* ``equal`` of a set: replace each with their geometric mean.
* ``implies`` (a <= b): if violated, set both to ``sqrt(x_a * x_b)``.

Pure stdlib; deterministic; no I/O.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .constraint_graph import Primitive

logger = logging.getLogger("hte.arbitrage.projection")

_PMIN, _PMAX = 1e-6, 1.0 - 1e-6


def _clip(x: float) -> float:
    return min(_PMAX, max(_PMIN, float(x)))


def _bernoulli_kl(p: float, q: float) -> float:
    p, q = _clip(p), _clip(q)
    return p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))


def kl_divergence(p: Mapping[str, float], q: Mapping[str, float]) -> float:
    """Sum of per-outcome Bernoulli KL(p || q) over shared keys."""
    return round(sum(_bernoulli_kl(p[k], q[k]) for k in p if k in q), 10)


@dataclass
class ProjectionResult:
    x: dict
    iterations: int
    converged: bool
    max_violation: float
    kl_gap: float = 0.0

    def to_dict(self) -> dict:
        return {"x": dict(self.x), "iterations": self.iterations,
                "converged": self.converged, "max_violation": self.max_violation,
                "kl_gap": self.kl_gap}


def _geomean(vals: Sequence[float]) -> float:
    vals = [_clip(v) for v in vals]
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def project_primitive(x: dict, prim: Primitive) -> None:
    """Apply one closed-form KL projection in place. Tolerant of missing ids."""
    ids = [i for i in prim.ids if i in x]
    if not ids:
        return
    if prim.kind == "sum":
        s = sum(x[i] for i in ids)
        if s <= 0:
            return
        if prim.op == "==" or (prim.op == "<=" and s > prim.rhs) \
                or (prim.op == ">=" and s < prim.rhs):
            factor = prim.rhs / s
            for i in ids:
                x[i] = _clip(x[i] * factor)
    elif prim.kind == "equal":
        g = _geomean([x[i] for i in ids])
        for i in ids:
            x[i] = _clip(g)
    elif prim.kind == "implies":  # ids = [a, b] with a <= b
        if len(ids) == 2 and x[ids[0]] > x[ids[1]]:
            g = _geomean([x[ids[0]], x[ids[1]]])
            x[ids[0]] = _clip(g)
            x[ids[1]] = _clip(g)


def max_violation(x: Mapping[str, float], primitives: Sequence[Primitive]) -> float:
    """Largest constraint violation magnitude at ``x`` (0 == fully coherent)."""
    worst = 0.0
    for prim in primitives:
        ids = [i for i in prim.ids if i in x]
        if not ids:
            continue
        if prim.kind == "sum":
            s = sum(x[i] for i in ids)
            if prim.op == "==":
                worst = max(worst, abs(s - prim.rhs))
            elif prim.op == "<=":
                worst = max(worst, max(0.0, s - prim.rhs))
            elif prim.op == ">=":
                worst = max(worst, max(0.0, prim.rhs - s))
        elif prim.kind == "equal":
            worst = max(worst, max(x[i] for i in ids) - min(x[i] for i in ids))
        elif prim.kind == "implies" and len(ids) == 2:
            worst = max(worst, max(0.0, x[ids[0]] - x[ids[1]]))
    return round(worst, 10)


def bregman_project(x0: Mapping[str, float], primitives: Sequence[Primitive], *,
                    max_iter: int = 500, tol: float = 1e-9) -> ProjectionResult:
    """Cyclic KL projection of ``x0`` onto the coherent set.

    Returns the projected coherent vector + diagnostics. Deterministic.
    """
    x = {k: _clip(v) for k, v in x0.items()}
    if not primitives:
        return ProjectionResult(x=x, iterations=0, converged=True,
                                max_violation=0.0, kl_gap=0.0)
    iterations = 0
    converged = False
    for it in range(1, max_iter + 1):
        iterations = it
        prev = dict(x)
        for prim in primitives:
            project_primitive(x, prim)
        delta = max(abs(x[k] - prev[k]) for k in x)
        if delta < tol:
            converged = True
            break
    return ProjectionResult(
        x=x, iterations=iterations, converged=converged,
        max_violation=max_violation(x, primitives),
        kl_gap=kl_divergence(x0, x))


def incoherence(x_market: Mapping[str, float], x_proj: Mapping[str, float]) -> dict:
    """Summarize the gap between market prices and their coherent projection."""
    keys = [k for k in x_market if k in x_proj]
    l1 = sum(abs(x_market[k] - x_proj[k]) for k in keys)
    max_abs = max((abs(x_market[k] - x_proj[k]) for k in keys), default=0.0)
    return {"l1": round(l1, 10), "max_abs": round(max_abs, 10),
            "kl": kl_divergence(x_market, x_proj), "n": len(keys)}


def local_incoherence(x_market: Mapping[str, float], x_proj: Mapping[str, float],
                      ids: Sequence[str]) -> float:
    """L1 incoherence restricted to a subset of outcome ids."""
    return round(sum(abs(x_market[i] - x_proj[i]) for i in ids
                     if i in x_market and i in x_proj), 10)

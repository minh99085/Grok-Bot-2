"""Calibration-weighted probability ensemble (PAPER ONLY; pure).

Combines independent probability members (statistical ``model``, ``market`` mid, and
``research``/Grok) into one ``p_ensemble`` via a weighted average where each member's
weight is its base prior times its MEASURED calibration weight. Also returns the
weighted member disagreement and a confidence interval (member disagreement is the
honest uncertainty: when the sources agree the band is tight, when they diverge it's
wide).

Pure + deterministic. Produces a probability only — never a position size or a gate.
"""

from __future__ import annotations

import math
from typing import Optional


def _clamp01(x) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def calibration_weighted_stack(members: dict, *, ci_k: float = 1.0,
                               fallback: Optional[float] = None) -> dict:
    """Combine ``{name: {"p": prob, "weight": w}}`` into a weighted-average probability.

    Returns ``p_ensemble``, the normalized weights, the weighted disagreement (std),
    and a [ci_low, ci_high] band = p +/- ci_k * disagreement (clamped). When all weights
    are <= 0 it returns ``fallback`` (or the simple mean, or 0.5)."""
    items = [(name, _clamp01(m.get("p")), max(0.0, float(m.get("weight", 0.0) or 0.0)))
             for name, m in (members or {}).items() if m is not None]
    total_w = sum(w for _, _, w in items)
    if total_w <= 0.0:
        if fallback is not None:
            p = _clamp01(fallback)
        elif items:
            p = sum(p for _, p, _ in items) / len(items)
        else:
            p = 0.5
        return {"p_ensemble": round(p, 6), "weights": {}, "disagreement": 0.0,
                "ci_low": round(p, 6), "ci_high": round(p, 6), "members_used": 0}
    p_ens = sum(p * w for _, p, w in items) / total_w
    var = sum(w * (p - p_ens) ** 2 for _, p, w in items) / total_w
    disagree = math.sqrt(max(0.0, var))
    half = max(0.0, float(ci_k)) * disagree
    weights = {name: round(w / total_w, 6) for name, _, w in items}
    return {
        "p_ensemble": round(_clamp01(p_ens), 6),
        "weights": weights,
        "disagreement": round(disagree, 6),
        "ci_low": round(_clamp01(p_ens - half), 6),
        "ci_high": round(_clamp01(p_ens + half), 6),
        "members_used": len(items),
    }

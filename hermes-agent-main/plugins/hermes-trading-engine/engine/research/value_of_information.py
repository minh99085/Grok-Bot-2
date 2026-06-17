"""Value-of-information (VOI) targeting for Grok's bounded compute (PAPER ONLY).

Quant scope — *active learning / experimental design*: spend Grok's limited, rate-
limited research calls where they are worth the most — markets whose edge is most
UNCERTAIN **and** most ACTIONABLE (near the trade threshold) **and** tradeable (liquid).
Resolving uncertainty there has the highest expected value of information.

Built on the ensemble (#4): ``ensemble_disagreement`` is the honest "how unsure are
the sources" signal. Pure + deterministic; never places, sizes, or gates a trade — it
only RANKS what Grok should research next.
"""

from __future__ import annotations

from typing import Optional


def _clamp01(x) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def actionability(edge: float, min_edge: float, *, band: float = 0.03) -> float:
    """1.0 when the after-cost edge sits right at the trade threshold (resolving
    uncertainty could FLIP the decision), decaying to 0 as it moves away. ``band`` is
    the half-width (in edge units) over which it decays."""
    try:
        dist = abs(float(edge) - float(min_edge))
    except (TypeError, ValueError):
        return 0.0
    if band <= 0:
        return 1.0 if dist == 0 else 0.0
    return _clamp01(1.0 - dist / band)


def voi_score(*, disagreement: float, uncertainty: float = 0.0,
              liquidity_usd: float = 0.0, edge: float = 0.0, min_edge: float = 0.0,
              band: float = 0.03, liquidity_ref: float = 2000.0) -> float:
    """Expected value of a Grok call on this market in [0, ~1]. High when the sources
    DISAGREE / it's uncertain, it's NEAR the trade threshold, and it's liquid."""
    unc = max(_clamp01(disagreement), 0.5 * _clamp01(uncertainty))
    act = actionability(edge, min_edge, band=band)
    liq = _clamp01(float(liquidity_usd) / max(1e-9, float(liquidity_ref)))
    # actionability gates (a market we can't act on has low value); liquidity scales it.
    return round(unc * (0.25 + 0.75 * act) * (0.25 + 0.75 * liq), 6)


def rank_voi(items: list, *, top_n: int = 10, min_score: float = 1e-6) -> list:
    """Rank market dicts (each with a ``voi`` key) descending; drop near-zero. Pure."""
    sel = [it for it in (items or []) if float(it.get("voi", 0.0)) > min_score]
    sel.sort(key=lambda it: float(it.get("voi", 0.0)), reverse=True)
    return sel[: max(0, int(top_n))]

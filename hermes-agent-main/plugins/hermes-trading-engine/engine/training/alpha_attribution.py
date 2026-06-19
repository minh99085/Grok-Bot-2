"""Tier-3 alpha attribution (PAPER ONLY, pure/read-only).

Decomposes realized paper PnL by STRATEGY (bregman / directional / exploration) and by
SIGNAL SOURCE (grok-research / chainlink / model-or-market) so we know WHAT is actually
making (or losing) money — the institutional requirement to cut what doesn't work and scale
what does. Pure: reads closed positions; no I/O, no trading.
"""

from __future__ import annotations

_GROK_SOURCES = ("grok_online", "grok_cache")


def _f(x, d: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _strategy_bucket(p) -> str:
    if bool(getattr(p, "exploration", False)):
        return "exploration"
    if str(getattr(p, "strategy", "directional")) == "bregman":
        return "bregman"
    return "directional"


def _source_bucket(p) -> str:
    if str(getattr(p, "research_source", "") or "") in _GROK_SOURCES:
        return "grok_research"
    if bool(getattr(p, "chainlink_linked", False)):
        return "chainlink"
    return "model_market"


def _agg(positions) -> dict:
    n = len(positions)
    pnls = [_f(getattr(p, "realized_pnl", 0.0)) for p in positions]
    wins = sum(1 for x in pnls if x > 0)
    total = sum(pnls)
    cost = sum(_f(getattr(p, "cost", 0.0)) for p in positions)
    return {
        "trades": n,
        "wins": wins,
        "win_rate": round(wins / n, 4) if n else 0.0,
        "total_pnl": round(total, 6),
        "avg_pnl": round(total / n, 6) if n else 0.0,
        "total_cost_usd": round(cost, 4),
        "return_on_cost": round(total / cost, 6) if cost else 0.0,
    }


def attribute_pnl(closed_positions) -> dict:
    """Attribution report over CLOSED positions. Buckets by strategy and by signal source,
    plus the overall total. Read-only; deterministic."""
    closed = [p for p in (closed_positions or []) if getattr(p, "closed", False)]
    by_strategy: dict = {}
    by_source: dict = {}
    for p in closed:
        by_strategy.setdefault(_strategy_bucket(p), []).append(p)
        by_source.setdefault(_source_bucket(p), []).append(p)
    # readiness-only (exclude exploration probes) overall — the durable performance view
    readiness = [p for p in closed if not bool(getattr(p, "exploration", False))]
    return {
        "schema": "alpha_attribution/1.0", "paper_only": True,
        "closed_trades": len(closed),
        "overall": _agg(closed),
        "readiness_only": _agg(readiness),
        "by_strategy": {k: _agg(v) for k, v in sorted(by_strategy.items())},
        "by_signal_source": {k: _agg(v) for k, v in sorted(by_source.items())},
        "best_strategy": max(((k, _agg(v)["total_pnl"]) for k, v in by_strategy.items()),
                             key=lambda kv: kv[1], default=("none", 0.0))[0],
        "best_signal_source": max(((k, _agg(v)["total_pnl"]) for k, v in by_source.items()),
                                  key=lambda kv: kv[1], default=("none", 0.0))[0],
    }

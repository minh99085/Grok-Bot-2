"""Tier-2 #6 execution attribution (PAPER ONLY, pure/read-only).

Institutional execution analytics over CLOSED paper trades: implementation shortfall (the
cost of crossing vs the decision mid), realized entry slippage, markout-by-horizon (post-fill
price drift = adverse selection / alpha decay), and per-strategy / per-source execution cost.
Tells us how much edge is lost to EXECUTION (vs the model), which is what the maker/passive
sizing (#5) and the cost model are trying to recover. Pure: reads positions + the learner's
markout aggregates; no I/O, no trading.
"""

from __future__ import annotations


def _f(x, d: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _impl_shortfall(p) -> float:
    """Per-share implementation shortfall: how much WORSE the fill was than the decision mid
    (entry fill price − market mid at decision). >=0 means we paid up to execute."""
    fill = _f(getattr(p, "entry_price", 0.0)) or _f(getattr(p, "executable_price_entry", 0.0))
    mid = _f(getattr(p, "p_market_entry", 0.0))
    if fill <= 0.0 or mid <= 0.0:
        return 0.0
    return fill - mid


def _strategy_bucket(p) -> str:
    if bool(getattr(p, "exploration", False)):
        return "exploration"
    if str(getattr(p, "strategy", "directional")) == "bregman":
        return "bregman"
    return "directional"


def _agg(positions) -> dict:
    n = len(positions)
    if not n:
        return {"trades": 0, "avg_impl_shortfall": 0.0, "avg_impl_shortfall_bps": 0.0,
                "total_exec_cost_usd": 0.0}
    shortfalls = [_impl_shortfall(p) for p in positions]
    mids = [_f(getattr(p, "p_market_entry", 0.0)) for p in positions]
    qtys = [_f(getattr(p, "qty", 0.0)) for p in positions]
    bps = [(s / m) * 1e4 for s, m in zip(shortfalls, mids) if m > 0]
    exec_cost = sum(s * q for s, q in zip(shortfalls, qtys))
    return {
        "trades": n,
        "avg_impl_shortfall": round(sum(shortfalls) / n, 6),
        "avg_impl_shortfall_bps": round(sum(bps) / len(bps), 2) if bps else 0.0,
        "total_exec_cost_usd": round(exec_cost, 6),
        "avg_fill_quality": round(sum(_f(getattr(p, "fill_quality", 1.0))
                                      for p in positions) / n, 4),
    }


def execution_attribution(closed_positions, *, learner_markouts=None) -> dict:
    """Execution-attribution report over CLOSED positions + (optional) the learner's
    markout-by-horizon aggregates. Read-only; deterministic.

    ``learner_markouts``: ``{horizon: avg_markout_bps_or_ratio}`` from
    ``OnlineLearner.markout_summary()`` — post-fill price drift by horizon (adverse selection
    when negative for a long)."""
    closed = [p for p in (closed_positions or []) if getattr(p, "closed", False)]
    by_strategy: dict = {}
    by_source: dict = {}
    for p in closed:
        by_strategy.setdefault(_strategy_bucket(p), []).append(p)
        src = str(getattr(p, "research_source", "") or "") or "model_market"
        by_source.setdefault(src, []).append(p)
    readiness = [p for p in closed if not bool(getattr(p, "exploration", False))]
    return {
        "schema": "execution_attribution/1.0", "paper_only": True,
        "closed_trades": len(closed),
        "overall": _agg(closed),
        "readiness_only": _agg(readiness),
        "by_strategy": {k: _agg(v) for k, v in sorted(by_strategy.items())},
        "by_signal_source": {k: _agg(v) for k, v in sorted(by_source.items())},
        # markout-by-horizon (post-fill drift): negative for a long = adverse selection.
        "markout_by_horizon": dict(learner_markouts or {}),
    }

"""Helpers for the Grok decision bundle (v1.3 extras). Pure functions — unit-testable."""

from __future__ import annotations

from typing import Optional

from engine.pulse.tradingview import (
    DEFAULT_MTF_TIMEFRAMES,
    tf_age_key,
    tf_dir_key,
    tf_label,
)


def gate_funnel_top(rejected_by_stage: dict, *, top_n: int = 8) -> dict:
    """Summarize where candidate trades get blocked (highest counts first)."""
    rbs = {str(k): int(v or 0) for k, v in (rejected_by_stage or {}).items() if int(v or 0) > 0}
    ranked = sorted(rbs.items(), key=lambda x: (-x[1], x[0]))[: max(1, int(top_n))]
    return {
        "total_rejected": sum(rbs.values()),
        "top_blockers": [{"stage": stage, "count": count} for stage, count in ranked],
    }


def tv_trend_snapshot(
    *,
    mtf: Optional[dict],
    latest_by_timeframe: dict,
    feature_symbol: str = "BTCUSD",
) -> dict:
    """All configured TV chart alerts (default 4/5/10/13/15m) with strength + MTF trend verdict."""
    mtf = mtf or {}
    feat = str(feature_symbol or "BTCUSD").strip() or "BTCUSD"
    tfs = tuple(mtf.get("mtf_timeframes") or DEFAULT_MTF_TIMEFRAMES)
    n = int(mtf.get("mtf_count") or len(tfs))
    charts = {}
    for tf in tfs:
        label = tf_label(tf)
        snap = latest_by_timeframe.get("%s@%s" % (feat, tf)) or {}
        fresh_dir = mtf.get(tf_dir_key(tf))
        stored_dir = snap.get("direction")
        charts[label] = {
            "timeframe": tf,
            "direction": fresh_dir or stored_dir,
            "strength": snap.get("strength"),
            "fresh": fresh_dir is not None,
            "age_s": mtf.get(tf_age_key(tf)),
            "stale_stored_dir": (stored_dir if fresh_dir is None and stored_dir else None),
        }
    confirm_ntf = mtf.get("confirm_%dtf" % n) if n else None
    direction_ntf = mtf.get("direction_%dtf" % n) if n else None
    return {
        "mtf_timeframes": list(tfs),
        "mtf_count": n,
        "fast_pair": mtf.get("fast_pair"),
        "fast_pair_confirm": mtf.get("confirm"),
        "fast_pair_direction": mtf.get("direction"),
        "confirm_mtf": mtf.get("confirm_mtf"),
        "direction_mtf": mtf.get("direction_mtf"),
        "confirm_%dtf" % n: confirm_ntf,
        "direction_%dtf" % n: direction_ntf,
        "fresh_tf_count": mtf.get("trend_fresh_count"),
        "trend_by_tf": mtf.get("trend_by_tf"),
        "charts": charts,
    }
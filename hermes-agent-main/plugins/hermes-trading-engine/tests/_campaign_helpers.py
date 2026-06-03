"""Shared helpers for campaign-controller tests (PAPER ONLY)."""

from __future__ import annotations

import time


def micro_ready_snapshot(**over) -> dict:
    """A snapshot that satisfies EVERY campaign threshold + safety gate so the
    verdict can reach ``micro_canary_ready`` (when algorithm freeze is on)."""
    now = time.time()
    snap = {
        "run_id": "run-1",
        "started_ts": now - 15 * 86400,        # 15 days ago
        "runtime_seconds": 80 * 3600,          # 80h > 72h target
        "decisions": 1200,
        "paper_trades": 350,
        "resolved_labels": 150,
        "clean_labels": 135,
        "bregman_candidates": 60,
        "bregman_certified": 3,
        "bregman_false_positives": 0,
        "partial_fill_hedge_breaks": 0,
        "risk_violations": 0,
        "live_orders": 0,
        "after_cost_expectancy": 0.020,
        "realistic_fill_expectancy": 0.012,
        "optimistic_expectancy": 0.030,
        "calibration_error": 0.05,
        "baseline_calibration_error": 0.06,
        "brier": 0.18, "log_loss": 0.52, "ece": 0.05,
        "stale_data_rejection_rate": 0.0,
        "stale_chainlink": False, "stale_book": False,
        "stale_data_confidence_improvement": False,
        "max_drawdown_pct": 0.08, "slippage_bps": 18.0,
        "algorithm_freeze_mode": True,
        "live_readiness_state": "micro_canary_ready",
        "validation_campaign": None,
        "replay_validation_ran": False,
    }
    snap.update(over)
    return snap

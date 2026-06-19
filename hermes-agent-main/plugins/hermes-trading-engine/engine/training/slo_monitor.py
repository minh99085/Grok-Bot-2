"""Tier-3 SLO / drift monitor (PAPER ONLY, pure/read-only).

Turns the existing telemetry into explicit Service-Level-Objective checks with OK / WARN /
BREACH states + an overall status, so operational degradation (calibration drift, stale
training loop, stale feeds, poor execution-fill quality, kill-switch downgrade) is surfaced
as alerts instead of being buried in raw metrics. Pure: evaluates supplied numbers; no I/O,
no trading. Intended to be persisted to metrics/slo_monitor.json each tick.
"""

from __future__ import annotations

OK, WARN, BREACH = "ok", "warn", "breach"
_RANK = {OK: 0, WARN: 1, BREACH: 2}


def _f(x, d: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _check(name: str, value, *, warn=None, breach=None, lower_is_better: bool = True,
           reason: str = "") -> dict:
    """One SLO check. ``warn``/``breach`` are thresholds; when ``lower_is_better`` a value at/
    above the threshold is worse (and vice-versa)."""
    v = _f(value)
    state = OK
    if lower_is_better:
        if breach is not None and v >= breach:
            state = BREACH
        elif warn is not None and v >= warn:
            state = WARN
    else:
        if breach is not None and v <= breach:
            state = BREACH
        elif warn is not None and v <= warn:
            state = WARN
    return {"name": name, "value": round(v, 6), "state": state,
            "warn": warn, "breach": breach, "reason": reason if state != OK else ""}


def evaluate_slos(*, calibration_error: float = 0.0, baseline_calibration_error=None,
                  training_file_age_s: float = 0.0, training_file_max_age_s: float = 300.0,
                  chainlink_stale: bool = False, btc_stale: bool = False,
                  stale_data_rejection_rate: float = 0.0,
                  fill_quality: float = 1.0, kill_switch_downgraded: bool = False,
                  bregman_false_positive_rate: float = 0.0) -> dict:
    """Evaluate the operational SLOs and return a structured report with per-check states +
    an overall ``status`` (worst of all applicable checks). Read-only."""
    checks = []

    # 1) training-loop liveness: the training file must stay fresh (this is the exact signal
    # the Docker healthcheck uses; surfacing it early catches tick stalls).
    checks.append(_check("training_loop_fresh", training_file_age_s,
                         warn=training_file_max_age_s * 0.6, breach=training_file_max_age_s,
                         reason="training file stale -> tick loop slow/stalled"))

    # 2) calibration drift vs a baseline (when provided): current ECE/cal-error rising.
    if baseline_calibration_error is not None:
        drift = _f(calibration_error) - _f(baseline_calibration_error)
        checks.append(_check("calibration_drift", drift, warn=0.05, breach=0.10,
                             reason="calibration error degraded vs baseline"))
    checks.append(_check("calibration_error", calibration_error, warn=0.10, breach=0.20,
                         reason="absolute calibration error high"))

    # 3) data freshness / feeds
    checks.append(_check("chainlink_fresh", 1.0 if chainlink_stale else 0.0,
                         breach=1.0, reason="chainlink oracle stale"))
    checks.append(_check("btc_feed_fresh", 1.0 if btc_stale else 0.0,
                         warn=1.0, reason="btc fast-price feed stale"))
    checks.append(_check("stale_data_rejection_rate", stale_data_rejection_rate,
                         warn=0.10, breach=0.25, reason="high stale-book rejection rate"))

    # 4) execution quality
    checks.append(_check("fill_quality", fill_quality, warn=0.8, breach=0.5,
                         lower_is_better=False, reason="degraded paper fill quality"))

    # 5) safety: kill-switch + Bregman false positives (institutional hard alerts)
    checks.append(_check("not_kill_switch_downgraded", 1.0 if kill_switch_downgraded else 0.0,
                         breach=1.0, reason="kill-switch downgraded to conservative"))
    checks.append(_check("bregman_zero_false_positives", bregman_false_positive_rate,
                         breach=1e-9, reason="Bregman false-positive detected"))

    overall = max((c["state"] for c in checks), key=lambda s: _RANK[s], default=OK)
    return {
        "schema": "slo_monitor/1.0", "paper_only": True,
        "status": overall,
        "breaches": [c["name"] for c in checks if c["state"] == BREACH],
        "warnings": [c["name"] for c in checks if c["state"] == WARN],
        "checks": checks,
    }

"""Probability calibration for replay (Brier, log-loss, ECE).

Separates RESOLVED predictions (matched to a realized 0/1 outcome) from
UNRESOLVED ones (no outcome yet) and excludes unresolved from realized metrics.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

_EPS = 1e-6


def _clamp(p: float) -> float:
    return min(1.0 - _EPS, max(_EPS, float(p)))


def brier_score(pairs: list[tuple[float, int]]) -> Optional[float]:
    """mean (p - y)^2 over resolved (p, y) pairs. None if no pairs."""
    if not pairs:
        return None
    return sum((float(p) - float(y)) ** 2 for p, y in pairs) / len(pairs)


def log_loss(pairs: list[tuple[float, int]]) -> Optional[float]:
    """Mean negative log-likelihood with p clamped to [1e-6, 1-1e-6] (no inf)."""
    if not pairs:
        return None
    import math
    total = 0.0
    for p, y in pairs:
        pc = _clamp(p)
        y = int(y)
        total += -(y * math.log(pc) + (1 - y) * math.log(1.0 - pc))
    return total / len(pairs)


def calibration_table(pairs: list[tuple[float, int]], buckets: int = 10) -> list[dict]:
    if not pairs:
        return []
    table = []
    for b in range(buckets):
        lo = b / buckets
        hi = (b + 1) / buckets
        # last bucket is inclusive of 1.0
        in_bucket = [(p, y) for p, y in pairs
                     if (p >= lo and (p < hi or (b == buckets - 1 and p <= hi)))]
        if not in_bucket:
            table.append({"bucket": f"{lo:.2f}-{hi:.2f}", "count": 0,
                          "avg_predicted": None, "realized_frequency": None})
            continue
        avg_p = sum(p for p, _ in in_bucket) / len(in_bucket)
        freq = sum(y for _, y in in_bucket) / len(in_bucket)
        table.append({"bucket": f"{lo:.2f}-{hi:.2f}", "count": len(in_bucket),
                      "avg_predicted": round(avg_p, 6), "realized_frequency": round(freq, 6)})
    return table


def expected_calibration_error(pairs: list[tuple[float, int]], buckets: int = 10) -> Optional[float]:
    """Weighted mean |avg_predicted - realized_frequency| across buckets."""
    if not pairs:
        return None
    n = len(pairs)
    ece = 0.0
    for row in calibration_table(pairs, buckets):
        if row["count"] == 0:
            continue
        ece += (row["count"] / n) * abs(row["avg_predicted"] - row["realized_frequency"])
    return ece


# --------------------------------------------------------------------------- #
def match_predictions(predictions: list[dict], outcomes: list[dict]) -> dict:
    """Match probability predictions to realized outcomes.

    ``predictions``: dicts with venue/market_id/asset_id/outcome/predicted_probability.
    ``outcomes``: dicts with venue/market_id/asset_id/outcome/realized_outcome (0/1)
    and an OPTIONAL ``label_state`` (settlement-truth state). When a matched
    outcome carries a *dirty* label_state (void / ambiguous / unresolved /
    partially_invalid / stale_resolution) it is EXCLUDED from the resolved pairs
    so calibration is fit only on clean settlement truth — dirty labels can never
    pollute Brier / log-loss / ECE. Outcomes with no ``label_state`` are treated
    as clean (back-compat). Returns resolved (p, y) pairs, unresolved count,
    suppressed-dirty count, per-state breakdown, and per-row tagging.
    """
    from engine.training.settlement import is_trainable_state

    index = {}
    for o in outcomes:
        key = (o.get("venue"), o.get("market_id"), o.get("asset_id"), o.get("outcome"))
        index[key] = o
        index[(o.get("venue"), o.get("market_id"), o.get("asset_id"), None)] = o
        index[(o.get("venue"), o.get("market_id"), None, None)] = o

    resolved: list[tuple[float, int]] = []
    rows: list[dict] = []
    unresolved = 0
    suppressed_dirty = 0
    by_state: dict = {}
    for pr in predictions:
        p = pr.get("predicted_probability")
        if p is None:
            continue
        keys = [
            (pr.get("venue"), pr.get("market_id"), pr.get("asset_id"), pr.get("outcome")),
            (pr.get("venue"), pr.get("market_id"), pr.get("asset_id"), None),
            (pr.get("venue"), pr.get("market_id"), None, None),
        ]
        out = next((index[k] for k in keys if k in index), None)
        if out is None or out.get("realized_outcome") is None:
            unresolved += 1
            rows.append({**pr, "realized_outcome": None, "resolved": False})
            continue
        label_state = out.get("label_state")
        if label_state is not None:
            by_state[label_state] = by_state.get(label_state, 0) + 1
        if not is_trainable_state(label_state):
            # terminal-but-dirty: matched + has a realized value, but the label is
            # not clean settlement truth -> never used for calibration.
            suppressed_dirty += 1
            rows.append({**pr, "realized_outcome": int(out.get("realized_outcome")),
                         "resolved": False, "label_state": label_state,
                         "suppressed_dirty": True})
            continue
        y = int(out.get("realized_outcome"))
        resolved.append((float(p), y))
        rows.append({**pr, "realized_outcome": y, "resolved": True,
                     "label_state": label_state})
    return {"pairs": resolved, "unresolved": unresolved,
            "suppressed_dirty": suppressed_dirty, "label_states": by_state,
            "rows": rows}


def calibration_slope_intercept(pairs: list[tuple[float, int]]) -> tuple[float, float]:
    """Cox calibration slope + intercept (1.0 / 0.0 == perfectly calibrated)."""
    from engine.calibration_models import calibration_slope_intercept as _csi
    return _csi(pairs)


def export_calibration_artifact(predictions: list[dict], outcomes: list[dict], *,
                                buckets: int = 10, method: str = "auto",
                                min_samples: int = 20) -> dict:
    """Fit + export a calibration artifact comparing the BASELINE (raw predicted)
    probabilities against the UPGRADED (fitted-calibrator) probabilities.

    The artifact (method, effective sample size, slope/intercept, reliability
    buckets, before/after Brier-log-loss-ECE) is a plain dict suitable for replay
    reports + training reports. No network, deterministic.
    """
    from engine.calibration_models import InstitutionalCalibrator

    matched = match_predictions(predictions, outcomes)
    pairs = matched["pairs"]
    cal = InstitutionalCalibrator(method=method, min_samples=min_samples, bins=buckets)
    cal.fit(pairs)
    slope, intercept = calibration_slope_intercept(pairs)
    artifact = cal.to_artifact()
    artifact.update({
        "resolved_count": len(pairs),
        "unresolved_count": matched["unresolved"],
        "suppressed_dirty_count": matched.get("suppressed_dirty", 0),
        "label_states": matched.get("label_states", {}),
        "baseline": {
            "brier_score": brier_score(pairs),
            "log_loss": log_loss(pairs),
            "expected_calibration_error": expected_calibration_error(pairs, buckets),
            "calibration_slope": slope,
            "calibration_intercept": intercept,
        },
        "upgraded": {
            "brier_score": brier_score([(cal.transform(p), y) for p, y in pairs]),
            "log_loss": log_loss([(cal.transform(p), y) for p, y in pairs]),
            "expected_calibration_error": expected_calibration_error(
                [(cal.transform(p), y) for p, y in pairs], buckets),
        },
    })
    return artifact


def summarize_calibration(predictions: list[dict], outcomes: list[dict], buckets: int = 10) -> dict:
    matched = match_predictions(predictions, outcomes)
    pairs = matched["pairs"]
    slope, intercept = calibration_slope_intercept(pairs)
    return {
        "resolved_count": len(pairs),
        "unresolved_count": matched["unresolved"],
        "suppressed_dirty_count": matched.get("suppressed_dirty", 0),
        "label_states": matched.get("label_states", {}),
        "brier_score": brier_score(pairs),
        "log_loss": log_loss(pairs),
        "expected_calibration_error": expected_calibration_error(pairs, buckets),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "calibration_by_probability_bucket": calibration_table(pairs, buckets),
        "average_predicted_probability": (sum(p for p, _ in pairs) / len(pairs)) if pairs else None,
        "realized_frequency": (sum(y for _, y in pairs) / len(pairs)) if pairs else None,
        "rows": matched["rows"],
    }

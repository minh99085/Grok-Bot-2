"""Tier-3 model registry + reproducibility (PAPER ONLY, pure/read-only).

Produces a versioned, content-addressed SNAPSHOT of the active decision stack — config
(the gating/sizing thresholds), the learner's calibration state, the calibration artifact,
warm-start provenance, the random seed, and the code commit — so any paper result is
reproducible and auditable, and a champion can be compared against a challenger by version
id. Pure: hashes in-memory state; no I/O, no trading.
"""

from __future__ import annotations

import hashlib
import json

# Config fields that materially define the decision stack (gates, sizing, risk, research).
# Hashing only these keeps the version id stable across irrelevant config noise.
_REGISTRY_CONFIG_FIELDS = (
    "mode", "min_net_edge", "base_uncertainty", "base_shrink_factor", "max_shrink_factor",
    "min_shrink_factor", "max_spread", "min_depth_at_price", "require_credible_after_cost_edge",
    "min_credible_after_cost_edge", "size_aware_depth_enabled", "depth_requirement_cap_usd",
    "maker_capture_fraction", "paper_max_order_notional_usd", "fixed_notional_usd",
    "max_kelly_size_usd", "portfolio_risk_enabled", "max_event_exposure_frac",
    "max_category_exposure_frac", "confidence_kelly_enabled", "regime_aware_sizing_enabled",
    "probability_ensemble_enabled", "grok_calibration_enabled",
    "readiness_min_oos_expectancy_samples", "family_completion_enabled",
)


def _hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _config_fingerprint(cfg) -> dict:
    out = {}
    for f in _REGISTRY_CONFIG_FIELDS:
        if hasattr(cfg, f):
            out[f] = getattr(cfg, f)
    return out


def _calibration_fingerprint(learner) -> dict:
    """Stable summary of the learner's calibration state (bucket predicted/actual rates +
    per-category reliability) — the part that actually drives p_model."""
    if learner is None:
        return {}
    try:
        buckets = {str(b): {"n": int(v.get("n", 0)),
                            "wins": int(v.get("wins", 0)),
                            "sum_pred": round(float(v.get("sum_pred", 0.0)), 4)}
                   for b, v in (getattr(learner, "prob_buckets", {}) or {}).items()}
        cats = {str(k): {"n": int(v.get("n", 0)),
                         "reliability": round(float(v.get("reliability", 0.5)), 4)}
                for k, v in (getattr(learner, "categories", {}) or {}).items()}
        return {"prob_buckets": buckets, "categories": cats}
    except Exception:  # noqa: BLE001
        return {}


def build_snapshot(*, cfg, learner=None, commit: str = "", seed: int = 0,
                   warm_start_samples: int = 0,
                   calibration_artifact=None) -> dict:
    """Content-addressed registry snapshot of the active decision stack. The ``version_id``
    is a hash of (config fingerprint + calibration fingerprint + commit), so identical
    stacks share a version and any change produces a new, auditable id."""
    cfg_fp = _config_fingerprint(cfg)
    cal_fp = _calibration_fingerprint(learner)
    cfg_hash = _hash(cfg_fp)
    cal_hash = _hash(cal_fp)
    version_id = _hash({"cfg": cfg_hash, "cal": cal_hash, "commit": commit})
    snap = {
        "schema": "model_registry/1.0", "paper_only": True, "live_trading_enabled": False,
        "version_id": version_id,
        "config_hash": cfg_hash, "calibration_hash": cal_hash,
        "code_commit": str(commit or "")[:40],
        "random_seed": int(seed),
        "warm_start_samples": int(warm_start_samples),
        "calibration_samples": int(getattr(learner, "closed", 0)) if learner else 0,
        "calibration_error": (round(float(learner.calibration_error()), 6)
                              if learner is not None else None),
        "config_fingerprint": cfg_fp,
        "reproducible": bool(cfg_hash and cal_hash),
    }
    if calibration_artifact is not None:
        try:
            snap["calibration_method"] = (calibration_artifact.get("method")
                                          or calibration_artifact.get("fitted_method"))
        except Exception:  # noqa: BLE001
            pass
    return snap


class ModelRegistry:
    """Holds the champion snapshot and compares a challenger by version id."""

    def __init__(self):
        self.champion: dict = {}

    def register_champion(self, snapshot: dict) -> dict:
        self.champion = dict(snapshot or {})
        return self.champion

    def compare(self, challenger: dict) -> dict:
        """Diff a challenger snapshot against the champion (version + calibration error)."""
        champ = self.champion or {}
        ch = challenger or {}
        return {
            "champion_version": champ.get("version_id"),
            "challenger_version": ch.get("version_id"),
            "changed": champ.get("version_id") != ch.get("version_id"),
            "config_changed": champ.get("config_hash") != ch.get("config_hash"),
            "calibration_changed": champ.get("calibration_hash") != ch.get("calibration_hash"),
            "champion_calibration_error": champ.get("calibration_error"),
            "challenger_calibration_error": ch.get("calibration_error"),
        }

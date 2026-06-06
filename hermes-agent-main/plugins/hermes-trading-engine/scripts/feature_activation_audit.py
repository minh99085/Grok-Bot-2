#!/usr/bin/env python3
"""Generate the runtime feature-activation audit artifacts (PAPER, read-only).

Writes a machine-readable ``metrics/feature_activation.json`` and a human-readable
``reports/feature_activation_audit.md`` from :mod:`engine.feature_activation`. This
is Pass-1 instrumentation only — it performs no trading and changes no behavior.

Usage:
    python scripts/feature_activation_audit.py [--out-dir .] [--data-dir <dir>]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.feature_activation import build_feature_activation, to_markdown  # noqa: E402

logger = logging.getLogger("hte.feature_activation_audit")


def _load_cfg():
    """Best-effort live TrainingConfig (default profile) to refine flags. Read-only."""
    try:
        from engine.training.config import TrainingConfig
        return TrainingConfig()
    except Exception:  # noqa: BLE001
        return None


def _load_status(data_dir: Optional[str]):
    if not data_dir:
        return None
    try:
        p = Path(data_dir) / "polymarket_training.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return None


def generate(out_dir: str = ".", data_dir: Optional[str] = None) -> dict:
    """Build the audit and write the JSON + markdown artifacts. Returns the audit."""
    audit = build_feature_activation(cfg=_load_cfg(), status=_load_status(data_dir))
    out = Path(out_dir)
    (out / "metrics").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    json_path = out / "metrics" / "feature_activation.json"
    md_path = out / "reports" / "feature_activation_audit.md"
    json_path.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    md_path.write_text(to_markdown(audit), encoding="utf-8")
    logger.info("feature activation audit: %s + %s", json_path, md_path)
    return audit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate the feature-activation audit (PAPER).")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args(argv)
    audit = generate(args.out_dir, args.data_dir)
    s = audit["summary"]
    print("Feature Activation Audit (PAPER, read-only)")
    print(f"  truly active   : {s['truly_active']}")
    print(f"  telemetry only : {s['telemetry_only']}")
    print(f"  dead/unused    : {s['dead_or_unused']}")
    print(f"  pnl inflation  : {s['pnl_inflation_risks']}")
    print(f"  top leak       : {audit['top_edge_leaks'][0]['leak']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

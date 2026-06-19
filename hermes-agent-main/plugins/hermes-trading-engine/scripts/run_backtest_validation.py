#!/usr/bin/env python3
"""Tier-1 backtest / walk-forward validation runner (PAPER / RESEARCH ONLY).

Fetches resolved Polymarket markets, builds point-in-time (no-look-ahead) observations,
runs the walk-forward out-of-sample validation, writes the validation artifact, and
(optionally) WARM-STARTS the online learner's calibration state from the resolved history
so the live trainer starts calibrated instead of cold.

Usage:
  python3 scripts/run_backtest_validation.py \
      --limit 3000 --out <data_dir>/metrics/backtest_validation.json \
      [--warm-start <data_dir>/polymarket_training_learner.json] \
      [--cache resolved_markets.json]   # reuse a saved fetch instead of hitting the network

NEVER trades, sizes, or touches a live venue. Read-only research.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.training.historical_dataset import (build_observations,  # noqa: E402
                                                 fetch_resolved_markets)
from engine.training.backtest import BacktestConfig, walk_forward_validate  # noqa: E402


def _load_cache(path: str) -> list:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Tier-1 backtest / walk-forward validation")
    ap.add_argument("--limit", type=int, default=int(os.getenv("BACKTEST_RESOLVED_LIMIT", 3000)))
    ap.add_argument("--out", default="metrics/backtest_validation.json")
    ap.add_argument("--warm-start", default=None,
                    help="learner state JSON to warm-start (e.g. <data_dir>/"
                         "polymarket_training_learner.json)")
    ap.add_argument("--cache", default=None,
                    help="path to a cached resolved-markets JSON (skip network fetch)")
    ap.add_argument("--save-cache", default=None,
                    help="save the fetched resolved markets to this JSON for reuse")
    ap.add_argument("--leads", default="1d,1w,1mo")
    ap.add_argument("--train-frac", type=float, default=0.7)
    ap.add_argument("--edge-threshold", type=float, default=0.0)
    ap.add_argument("--cost-per-trade", type=float,
                    default=float(os.getenv("BACKTEST_COST_PER_TRADE", 0.01)))
    args = ap.parse_args(argv)

    if args.cache and Path(args.cache).exists():
        resolved = _load_cache(args.cache)
        print(f"[backtest] loaded {len(resolved)} resolved markets from cache {args.cache}")
    else:
        print(f"[backtest] fetching up to {args.limit} resolved markets from Gamma ...")
        resolved = fetch_resolved_markets(limit=args.limit)
        print(f"[backtest] fetched {len(resolved)} resolved markets")
        if args.save_cache:
            Path(args.save_cache).write_text(json.dumps(resolved), encoding="utf-8")

    leads = tuple(s.strip() for s in args.leads.split(",") if s.strip())
    obs = build_observations(resolved, leads=leads)
    print(f"[backtest] built {len(obs)} point-in-time observations (leads={leads})")

    cfg = BacktestConfig(train_frac=args.train_frac, edge_threshold=args.edge_threshold,
                         cost_per_trade=args.cost_per_trade)
    report = walk_forward_validate(obs, cfg=cfg)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"[backtest] wrote validation report -> {out_path}")
    cmb = report.get("calibrated_model_backtest", {})
    print(f"[backtest] status={report.get('status')} promotable={report.get('promotable')} "
          f"train_n={report.get('train_n')} test_n={report.get('test_n')} "
          f"calibration_improved_oos={report.get('calibration_improved_oos')}")
    print(f"[backtest] OOS calibrated strategy: trades={cmb.get('trades')} "
          f"expectancy={cmb.get('expectancy')} hit_rate={cmb.get('hit_rate')} "
          f"sharpe={cmb.get('sharpe')}")

    if args.warm_start:
        from engine.training.online_learner import OnlineLearner
        learner = OnlineLearner(path=Path(args.warm_start))
        n = learner.warm_start(obs)
        learner.persist()
        print(f"[backtest] warm-started learner ({n} observations) -> {args.warm_start} "
              f"(calibration_error={learner.calibration_error()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

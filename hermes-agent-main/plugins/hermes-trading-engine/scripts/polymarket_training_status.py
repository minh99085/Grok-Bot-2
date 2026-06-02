#!/usr/bin/env python3
"""Print a simple Polymarket PAPER training status: scan counts, open paper
positions, PnL, risk status, and safety locks. Read-only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _data_dir() -> Path:
    try:
        from engine.config import Settings
        return Path(Settings().data_dir)
    except Exception:  # noqa: BLE001
        import os
        return Path(os.getenv("HTE_DATA_DIR") or ".")


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Print Polymarket PAPER training status (read-only).")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--json", action="store_true", help="print raw JSON status")
    args = ap.parse_args(argv)

    dd = Path(args.data_dir) if args.data_dir else _data_dir()
    path = dd / "polymarket_training.json"
    if not path.exists():
        print(f"no training status at {path} — start training first.")
        return 0
    st = json.loads(path.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(st, indent=2, default=str))
        return 0

    pnl = st.get("pnl", {})
    scan = st.get("scan_metrics", {})
    risk = st.get("risk", {})
    safety = st.get("safety", {})
    print("=" * 56)
    print(f"Polymarket PAPER Training — {st.get('run_id')}")
    print(f"  mode: {st.get('mode')} (PAPER) · tick: {st.get('tick')} · "
          f"runtime: {st.get('runtime_seconds')}s")
    print(f"  scanned: {scan.get('scanned')} kept: {scan.get('kept')} "
          f"subscribed_assets: {scan.get('subscribed_assets')} "
          f"scan_ms: {scan.get('scan_latency_ms')}")
    print(f"  open positions: {pnl.get('open_positions')} · closed: {pnl.get('trades_closed')} "
          f"· win_rate: {pnl.get('win_rate')}")
    print(f"  equity: {pnl.get('equity')} (start {pnl.get('starting_bankroll')}) · "
          f"total PnL: {pnl.get('total_pnl')}")
    print(f"  risk: approvals={risk.get('approvals')} rejections={risk.get('rejections')}")
    print(f"  safety: preflight_ok={safety.get('ok')} live_detected={safety.get('live_detected')}")
    print(f"  arbitrage_disabled: {safety.get('checks', {}).get('arbitrage_disabled')}")
    mon = st.get("monitoring", {}) or {}
    ks = st.get("kill_switch", {}) or {}
    if mon:
        print(f"  profile: {st.get('profile', mon.get('profile'))} · kill_switch: "
              f"{ks.get('severity', 'OK')}"
              + (f" (downgraded: {', '.join(ks.get('triggered', []))})"
                 if st.get("downgraded") else ""))
        print(f"  learning: trades/hr={mon.get('paper_trades_per_hour')} "
              f"feedback/hr={mon.get('useful_feedback_per_hour')} "
              f"labels/day={mon.get('labels_resolved_per_day')}")
        print(f"  quality: calib_improvement={mon.get('calibration_improvement')} "
              f"brier_trend={mon.get('brier_trend')} ece_trend={mon.get('ece_trend')} "
              f"loss_streak={mon.get('loss_streak')}")
        print(f"  bregman: opps={mon.get('bregman_opportunities')} "
              f"certified_profit={mon.get('certified_bregman_profit')} "
              f"fp_rate={mon.get('bregman_false_positive_rate')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

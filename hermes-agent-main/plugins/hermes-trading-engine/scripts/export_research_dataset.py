#!/usr/bin/env python3
"""Export the offline research dataset to CSV (PAPER/RESEARCH, read-only).

Dumps the persisted research tables — probability estimates, research evidence,
market-rule summaries, and research runs — to CSV for offline analysis and
dataset building. Read-only: it never trades, places an order, or mutates state.

Usage:
    python scripts/export_research_dataset.py --db <sqlite> --out <dir>
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("hte.export_research_dataset")

# (table_name, output_csv) pairs exported by :func:`export`.
_TABLES = (
    ("probability_estimates", "probability_estimates.csv"),
    ("research_evidence", "research_evidence.csv"),
    ("market_rule_summaries", "market_rule_summaries.csv"),
    ("research_runs", "research_runs.csv"),
)


def _dump_table(conn, table: str, path: Path) -> int:
    """Write one SQLite table to CSV (header + rows); empty file if absent. Pure I/O."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        cur = conn.execute(f"SELECT * FROM {table}")  # noqa: S608 — fixed table allowlist
    except Exception as exc:  # noqa: BLE001 — missing table -> empty export
        logger.warning("table %s unavailable (%s); writing empty CSV", table, exc)
        path.write_text("", encoding="utf-8")
        return 0
    cols = [d[0] for d in (cur.description or [])]
    rows = cur.fetchall()
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if cols:
            w.writerow(cols)
        for r in rows:
            w.writerow(list(r))
    return len(rows)


def export(store, out_dir) -> dict:
    """Export all research tables from ``store`` to ``out_dir`` as CSV (read-only).

    Returns ``{table: row_count}``. ``store`` is an :class:`engine.storage.Store`
    (uses its ``_conn`` SQLite connection)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts: dict = {}
    for table, fname in _TABLES:
        counts[table] = _dump_table(store._conn, table, out / fname)
    logger.info("exported research dataset to %s: %s", out, counts)
    return counts


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Export the offline research dataset to CSV.")
    ap.add_argument("--db", default=None, help="operational sqlite path")
    ap.add_argument("--out", default="research_dataset", help="output directory")
    args = ap.parse_args(argv)
    import os
    from engine.storage import Store
    db = args.db or os.path.join(os.getenv("HTE_DATA_DIR", "."), "trading_engine.sqlite3")
    store = Store(Path(db))
    counts = export(store, args.out)
    print(f"exported research dataset -> {args.out}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

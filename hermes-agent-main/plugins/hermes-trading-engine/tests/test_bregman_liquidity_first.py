"""Priority-2: liquidity-first selection for Bregman discovery.

The discovery slice is filled DEEPEST-book-first so the completion/hydration/certification
budget targets markets that can clear the depth gate (the report showed depth_too_thin /
no_depth dominating). Selection-only — never a gate, never drops a market.
"""

from __future__ import annotations

import time
import types

import pytest

from engine.markets import universe_manager as um
from engine.training.polymarket_trainer import PolymarketPaperTrainer
from engine.training.family_completion import expand_event_families


def _rec(mid, *, depth, liq=0.0, vol=0.0):
    raw = {"id": mid, "question": mid, "clobTokenIds": [f"{mid}a", f"{mid}b"],
           "topDepthUsd": depth, "liquidityNum": liq, "volume24hr": vol,
           "bestAsk": "0.30", "bestBid": "0.28"}
    return um.MarketRecord.from_raw(raw, now=time.time())


def test_liquidity_first_orders_deepest_book_first():
    recs = [_rec("thin", depth=5.0), _rec("deep", depth=500.0), _rec("mid", depth=50.0)]
    ordered = PolymarketPaperTrainer._liquidity_first_order(recs)
    assert [r.market_id for r in ordered] == ["deep", "mid", "thin"]


def test_liquidity_first_is_stable_on_ties():
    a, b = _rec("a", depth=50.0, liq=10.0), _rec("b", depth=50.0, liq=10.0)
    ordered = PolymarketPaperTrainer._liquidity_first_order([a, b])
    assert [r.market_id for r in ordered] == ["a", "b"]   # stable tie -> input order


def test_liquidity_first_tiebreak_by_liquidity_then_volume():
    recs = [_rec("x", depth=50.0, liq=1.0, vol=100.0),
            _rec("y", depth=50.0, liq=9.0, vol=1.0)]
    ordered = PolymarketPaperTrainer._liquidity_first_order(recs)
    assert [r.market_id for r in ordered] == ["y", "x"]   # higher liquidity first


def test_family_completion_processes_liquid_families_first():
    now = time.time()

    def event_markets(prefix, n):
        return [{"id": f"{prefix}{i}", "clobTokenIds": [f"{prefix}{i}a", f"{prefix}{i}b"],
                 "question": f"{prefix} {i}"} for i in range(n)]

    def member(prefix, *, liq):
        full = event_markets(prefix, 5)
        raw = dict(full[0])
        raw["events"] = [{"id": prefix, "slug": prefix, "markets": full}]
        raw["liquidityNum"] = liq
        return um.MarketRecord.from_raw(raw, now=now)

    # two families: LO (illiquid) and HI (liquid). With a global cap of 4, the liquid
    # family must be completed first.
    scanned = [member("LO", liq=10.0), member("HI", liq=9000.0)]
    out, tel = expand_event_families(scanned, now=now, max_total_new=4, max_per_family=8)
    added_prefixes = [r.market_id[:2] for r in out if r.market_id not in ("LO0", "HI0")]
    assert added_prefixes and all(p == "HI" for p in added_prefixes)  # liquid family first
    assert tel["family_completion_missing_siblings_added"] == 4

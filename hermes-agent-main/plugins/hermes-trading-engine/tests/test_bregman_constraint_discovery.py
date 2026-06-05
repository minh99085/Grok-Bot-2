"""Discovery -> graph -> Bregman: normalized executable quotes + arb certification."""

from __future__ import annotations

from engine.arbitrage.constraint_discovery import discover_constraints
from engine.strategies.bregman import BregmanStrategy
from engine.strategies.bregman_scanner import BregmanPaperScanner


def test_normalized_quotes_have_executable_prices():
    markets = [{"id": "pm1", "active": True, "enableOrderBook": True,
                "clobTokenIds": ["pm1y", "pm1n"], "outcomePrices": ["0.41", "0.59"],
                "bestBid": 0.40, "bestAsk": 0.42, "topDepthUsd": 1000,
                "bookUpdatedTs": 1_700_000_000}]
    res = discover_constraints(markets, now_ms=1_700_000_000_000, fee_bps=60.0)
    q = res.normalized_quotes["pm1y"]
    for k in ("best_bid", "best_ask", "mid", "spread", "depth_usd", "depth_shares",
              "fee_bps", "ts_ms", "stale"):
        assert k in q, k
    assert q["best_ask"] == 0.42 and q["best_bid"] == 0.40
    assert abs(q["mid"] - 0.41) < 1e-9 and abs(q["spread"] - 0.02) < 1e-9
    assert q["fee_bps"] == 60.0 and q["depth_shares"] > 0


def test_stale_book_flagged():
    markets = [{"id": "old", "active": True, "enableOrderBook": True,
                "clobTokenIds": ["oy", "on"], "outcomePrices": ["0.5", "0.5"],
                "bestBid": 0.49, "bestAsk": 0.51, "topDepthUsd": 1000,
                "bookUpdatedTs": 1_000}]  # ancient
    res = discover_constraints(markets, now_ms=10_000_000_000_000, max_book_age_ms=60_000)
    assert res.normalized_quotes["oy"]["stale"] is True


def test_discovery_graph_certifies_underpriced_mece():
    # neg-risk style 3-way where the asks sum < 1 -> certifiable MECE arb
    ms = [{"id": f"c{i}", "event_id": "evt", "group_kind": "mece", "active": True,
           "enableOrderBook": True, "clobTokenIds": [f"c{i}:y", f"c{i}:n"],
           "price": 0.30, "bestBid": 0.29, "bestAsk": 0.30, "topDepthUsd": 1000}
          for i in range(3)]  # 0.30 * 3 = 0.90 < 1 -> arb
    res = discover_constraints(ms)
    strat = BregmanStrategy()
    out = strat.evaluate(res.graph, now=0.0)
    assert out.candidates >= 1
    assert out.certified >= 1


def test_scanner_surfaces_discovery_metrics():
    ms = ([{"id": f"c{i}", "event_id": "evt", "group_kind": "mutually_exclusive",
            "active": True, "enableOrderBook": True, "clobTokenIds": [f"c{i}:y", f"c{i}:n"],
            "price": 0.30, "bestBid": 0.29, "bestAsk": 0.30, "topDepthUsd": 1000}
           for i in range(3)])
    tel = BregmanPaperScanner().scan(ms, now=0.0)
    assert tel["bregman_paper_enabled"] is True
    assert tel["groups_discovered"] == 1
    assert tel["constraint_groups_scanned"] >= 1
    assert "mutually_exclusive" in tel["group_type_counts"]
    assert "metadata_coverage" in tel and "book_coverage" in tel
    assert tel["avg_outcomes_per_group"] == 3.0

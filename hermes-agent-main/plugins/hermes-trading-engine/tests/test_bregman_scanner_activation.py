"""Acceptance tests for the paper-only Bregman scan loop.

Required acceptance (this file is the contract):
after a mocked scan with valid market data —
  * ``bregman_paper_enabled is True``
  * ``arbitrage_disabled is False``
  * ``constraint_groups_scanned > 0``
  * every skipped group carries a typed skip reason.

The scanner must never depend on BTC Pulse, Grok, or news being enabled.
"""

from __future__ import annotations

from engine.arbitrage.constraint_graph import (
    SKIP_REASONS,
    build_constraint_graph,
)
from engine.strategies.bregman_scanner import BregmanPaperScanner


def _markets():
    return [
        # underpriced complement (0.40 + 0.40 = 0.80) -> certifiable arb
        {"id": "m_arb", "active": True, "enableOrderBook": True,
         "outcomes": [{"id": "m_arb:yes", "price": 0.40, "ask": 0.40, "ask_depth": 100},
                      {"id": "m_arb:no", "price": 0.40, "ask": 0.40, "ask_depth": 100}],
         "relation": "complement"},
        # fairly priced complement -> scanned, coherent (no arb)
        {"id": "m_fair", "active": True, "enableOrderBook": True,
         "outcomes": [{"id": "m_fair:yes", "price": 0.50, "ask": 0.50, "ask_depth": 100},
                      {"id": "m_fair:no", "price": 0.50, "ask": 0.50, "ask_depth": 100}],
         "relation": "complement"},
        # closed market -> skipped (typed reason)
        {"id": "m_closed", "active": False, "closed": True,
         "outcomes": [{"id": "x", "price": 0.5, "ask": 0.5, "ask_depth": 10},
                      {"id": "y", "price": 0.5, "ask": 0.5, "ask_depth": 10}]},
        # missing prices -> skipped (typed reason)
        {"id": "m_noprice", "active": True, "enableOrderBook": True, "outcomes": []},
    ]


# --- graph builder ----------------------------------------------------------
def test_build_constraint_graph_scans_valid_and_skips_typed():
    graph, skipped = build_constraint_graph(_markets())
    assert len(graph.constraints()) == 2          # m_arb + m_fair
    skipped_ids = {s["market_id"] for s in skipped}
    assert skipped_ids == {"m_closed", "m_noprice"}
    for s in skipped:
        assert s["reason"] in SKIP_REASONS         # every skip is typed


# --- scanner telemetry (the acceptance contract) ----------------------------
def test_scan_activates_bregman_in_paper_mode():
    tel = BregmanPaperScanner().scan(_markets())
    assert tel["bregman_paper_enabled"] is True
    assert tel["arbitrage_disabled"] is False
    assert tel["enabled"] is True
    assert tel["constraint_groups_scanned"] > 0
    assert tel["constraint_groups_scanned"] == 2
    assert tel["groups_skipped"] == 2
    for s in tel["skipped_groups"]:
        assert s["reason"] in SKIP_REASONS
    # the underpriced complement is detected + certified
    assert tel["candidate_arbitrages"] >= 1
    assert tel["certified_arbitrages"] >= 1


def test_scan_is_independent_of_pulse_grok_news():
    # No pulse/grok/news inputs anywhere; scan still activates + scans.
    tel = BregmanPaperScanner().scan(_markets())
    assert tel["bregman_paper_enabled"] is True
    assert tel["constraint_groups_scanned"] == 2


def test_scanner_disabled_only_with_logged_reason():
    s = BregmanPaperScanner(enabled=False, disabled_reason="explicitly disabled by config")
    tel = s.scan(_markets())
    assert tel["bregman_paper_enabled"] is False
    assert tel["arbitrage_disabled"] is True
    assert tel["disabled_reason"] == "explicitly disabled by config"
    assert tel["constraint_groups_scanned"] == 0


def test_empty_markets_scans_zero_but_stays_enabled():
    tel = BregmanPaperScanner().scan([])
    assert tel["bregman_paper_enabled"] is True
    assert tel["arbitrage_disabled"] is False
    assert tel["constraint_groups_scanned"] == 0
    assert tel["groups_skipped"] == 0


def test_polymarket_binary_shape_scanned():
    # real Polymarket-style binary market (outcomePrices + clobTokenIds + quotes)
    markets = [{
        "id": "pm1", "active": True, "closed": False, "enableOrderBook": True,
        "clobTokenIds": ["pm1a", "pm1b"], "outcomePrices": ["0.41", "0.59"],
        "bestBid": 0.40, "bestAsk": 0.42, "topDepthUsd": 1000,
    }]
    tel = BregmanPaperScanner().scan(markets)
    assert tel["constraint_groups_scanned"] == 1
    assert tel["bregman_paper_enabled"] is True


def test_telemetry_has_all_required_fields():
    tel = BregmanPaperScanner().scan(_markets())
    for k in ("enabled", "bregman_paper_enabled", "arbitrage_disabled",
              "disabled_reason", "constraint_groups_scanned", "groups_skipped",
              "skipped_groups", "incoherent_groups", "candidate_arbitrages",
              "certified_arbitrages", "executable_depth_certified",
              "rejected_fees_spread_depth_slippage", "expected_min_profit",
              "worst_case_payoff", "execution_atomicity_risk",
              "opportunity_decay_half_life_s", "markets_seen"):
        assert k in tel, k

"""Tests for ABCAS activation + market normalization (the constraint_groups=0 fix).

Real Polymarket gamma encodes outcomePrices/clobTokenIds as JSON STRINGS; these
must normalize into constraint groups, not be skipped as non_numeric/insufficient.
"""

from __future__ import annotations

from engine.arbitrage.constraint_discovery import discover_constraints
from engine.arbitrage.constraint_graph import parse_list_field
from engine.strategies.bregman_scanner import BregmanPaperScanner


def _gamma_markets(n=5):
    # gamma-style: outcomePrices + clobTokenIds are JSON STRINGS (the failure case)
    out = []
    for i in range(n):
        out.append({
            "id": f"0xmarket{i}", "conditionId": f"0xcond{i}", "eventSlug": f"evt-{i}",
            "active": True, "closed": False, "enableOrderBook": True,
            "outcomePrices": f'["0.4{i}", "0.6{i}"]'.replace("0.6{}".format(i), "0.59"),
            "clobTokenIds": f'["0xtok{i}a", "0xtok{i}b"]',
            "bestBid": 0.40, "bestAsk": 0.42, "topDepthUsd": 1000,
            "bookUpdatedTs": 1_700_000_000})
    return out


# --- parser ----------------------------------------------------------------
def test_parse_list_field_handles_json_string():
    assert parse_list_field('["0.41","0.59"]') == ["0.41", "0.59"]
    assert parse_list_field('["0xabc","0xdef"]') == ["0xabc", "0xdef"]
    assert parse_list_field(["a", "b"]) == ["a", "b"]
    assert parse_list_field("0.4,0.6") == ["0.4", "0.6"]
    assert parse_list_field("") == []
    assert parse_list_field(None) == []


# --- normalization fixes the constraint_groups=0 bug ------------------------
def test_gamma_string_markets_normalize_into_groups():
    res = discover_constraints(_gamma_markets(5))
    assert res.metrics["normalized_markets"] > 0
    assert res.metrics["groups_discovered"] > 0
    assert res.metrics["groups_scanned"] > 0
    # no markets wrongly skipped as non-numeric/insufficient now
    sr = res.metrics["skip_reasons"]
    assert sr.get("non_numeric_price", 0) == 0
    assert sr.get("insufficient_outcomes", 0) == 0


def test_missing_quotes_falls_back_to_reference_quote():
    # no bestBid/bestAsk -> derive a reference quote from prices (not skipped)
    m = [{"id": "m", "active": True, "enableOrderBook": True,
          "outcomePrices": '["0.5","0.5"]', "clobTokenIds": '["a","b"]',
          "topDepthUsd": 500}]
    res = discover_constraints(m)
    assert res.metrics["groups_discovered"] == 1


def test_missing_depth_uses_paper_reference_depth():
    m = [{"id": "m", "active": True, "enableOrderBook": True,
          "outcomePrices": '["0.45","0.55"]', "clobTokenIds": '["a","b"]',
          "bestBid": 0.44, "bestAsk": 0.46}]  # no topDepthUsd
    res = discover_constraints(m)
    assert res.metrics["groups_discovered"] == 1


def test_closed_market_still_skipped_typed():
    m = [{"id": "closed", "active": False, "closed": True,
          "outcomePrices": '["0.5","0.5"]', "clobTokenIds": '["a","b"]'}]
    res = discover_constraints(m)
    assert res.metrics["groups_discovered"] == 0
    assert res.skipped and res.skipped[0]["reason"] == "market_inactive"


# --- ABCAS telemetry --------------------------------------------------------
def test_abcas_scanner_telemetry_fields():
    tel = BregmanPaperScanner().scan(_gamma_markets(5))
    assert tel["abcas_enabled"] is True
    assert tel["abcas_mode"] in ("paper", "aggressive_paper")
    assert tel["normalized_markets"] > 0
    assert tel["constraint_groups_discovered"] > 0
    assert tel["constraint_groups_scanned"] > 0
    assert "sample_skipped_market_ids" in tel
    assert tel["abcas_feedback_samples"] >= tel["constraint_groups_scanned"]


def test_abcas_aggressive_mode_label(monkeypatch):
    monkeypatch.setenv("AGGRESSIVE_PAPER_TRAINING", "1")
    tel = BregmanPaperScanner().scan(_gamma_markets(3))
    assert tel["abcas_mode"] == "aggressive_paper"

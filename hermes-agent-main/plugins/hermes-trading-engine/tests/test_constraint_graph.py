"""Tests for the constraint graph builder + typed skip reasons."""

from __future__ import annotations

from engine.arbitrage.constraint_graph import (
    SKIP_DEGENERATE_PRICE,
    SKIP_INSUFFICIENT_OUTCOMES,
    SKIP_MARKET_INACTIVE,
    SKIP_NO_DEPTH,
    SKIP_REASONS,
    ConstraintGraph,
    Outcome,
    RelationType,
    build_constraint_graph,
)


def test_binary_market_builds_complement():
    markets = [{"id": "pm1", "active": True, "enableOrderBook": True,
                "clobTokenIds": ["a", "b"], "outcomePrices": ["0.41", "0.59"],
                "bestBid": 0.40, "bestAsk": 0.42, "topDepthUsd": 1000}]
    g, skipped = build_constraint_graph(markets)
    assert skipped == []
    cs = g.constraints()
    assert len(cs) == 1 and cs[0].type == RelationType.COMPLEMENT


def test_explicit_outcomes_relation():
    markets = [{"id": "m", "active": True, "relation": "mece",
                "outcomes": [{"id": "a", "price": 0.3, "ask": 0.3, "ask_depth": 10},
                             {"id": "b", "price": 0.3, "ask": 0.3, "ask_depth": 10},
                             {"id": "c", "price": 0.3, "ask": 0.3, "ask_depth": 10}]}]
    g, skipped = build_constraint_graph(markets)
    assert skipped == []
    assert g.constraints()[0].type == RelationType.MECE


def test_typed_skips_are_all_known():
    markets = [
        {"id": "closed", "active": False, "outcomes": []},
        {"id": "noprice", "active": True, "enableOrderBook": True, "outcomes": []},
        {"id": "degenerate", "active": True,
         "outcomes": [{"id": "x", "price": 1.5, "ask": 1.5, "ask_depth": 10},
                      {"id": "y", "price": 0.5, "ask": 0.5, "ask_depth": 10}]},
        {"id": "nodepth", "active": True,
         "outcomes": [{"id": "p", "price": 0.5, "ask": 0.5, "ask_depth": 0},
                      {"id": "q", "price": 0.5, "ask": 0.5, "ask_depth": 0}]},
    ]
    g, skipped = build_constraint_graph(markets)
    by_id = {s["market_id"]: s["reason"] for s in skipped}
    assert by_id["closed"] == SKIP_MARKET_INACTIVE
    assert by_id["noprice"] == SKIP_INSUFFICIENT_OUTCOMES
    assert by_id["degenerate"] == SKIP_DEGENERATE_PRICE
    assert by_id["nodepth"] == SKIP_NO_DEPTH
    for s in skipped:
        assert s["reason"] in SKIP_REASONS


def test_graph_to_primitives_and_validate():
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="a", price=0.4, ask=0.4, ask_depth=100))
    g.add_outcome(Outcome(id="b", price=0.4, ask=0.4, ask_depth=100))
    g.add_complement("a", "b")
    assert g.to_primitives()
    assert g.validate() == []  # clean


def test_empty_markets_yield_empty_graph():
    g, skipped = build_constraint_graph([])
    assert g.constraints() == [] and skipped == []

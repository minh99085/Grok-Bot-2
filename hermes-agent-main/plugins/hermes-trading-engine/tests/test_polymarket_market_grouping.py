"""Tests for Polymarket constraint discovery: clustering, typed group kinds,
INSUFFICIENT_METADATA, and the required discovery metrics."""

from __future__ import annotations

from engine.arbitrage.constraint_discovery import (
    SKIP_INSUFFICIENT_METADATA,
    discover_constraints,
)
from engine.arbitrage.constraint_graph import RelationType


def _cluster_market(mid, event, kind, price=0.30, threshold=None, role=None):
    m = {"id": mid, "event_id": event, "group_kind": kind, "active": True,
         "enableOrderBook": True, "clobTokenIds": [f"{mid}:y", f"{mid}:n"],
         "price": price, "bestBid": price - 0.01, "bestAsk": price + 0.01,
         "topDepthUsd": 1000, "bookUpdatedTs": 1_000_000}
    if threshold is not None:
        m["threshold"] = threshold
    if role is not None:
        m["role"] = role
    return m


# --- typed group kinds ------------------------------------------------------
def test_mutually_exclusive_cluster():
    ms = [_cluster_market(f"c{i}", "evt_election", "mutually_exclusive") for i in range(3)]
    res = discover_constraints(ms)
    assert len(res.groups) == 1
    g = res.groups[0]
    assert g.relation == RelationType.MUTUALLY_EXCLUSIVE.value
    assert g.n_outcomes == 3


def test_negrisk_infers_mutually_exclusive():
    ms = [{"id": f"n{i}", "eventId": "evt_neg", "negRisk": True, "active": True,
           "enableOrderBook": True, "clobTokenIds": [f"n{i}:y", f"n{i}:n"],
           "price": 0.25, "bestBid": 0.24, "bestAsk": 0.26, "topDepthUsd": 500}
          for i in range(4)]
    res = discover_constraints(ms)
    assert res.groups[0].relation == RelationType.MUTUALLY_EXCLUSIVE.value
    assert res.groups[0].source == "negrisk"


def test_mece_and_range_and_exhaustive():
    for kind, rel in (("mece", RelationType.MECE), ("range", RelationType.RANGE),
                      ("collectively_exhaustive", RelationType.COLLECTIVELY_EXHAUSTIVE)):
        ms = [_cluster_market(f"{kind}{i}", f"evt_{kind}", kind) for i in range(3)]
        res = discover_constraints(ms)
        assert res.groups[0].relation == rel.value, kind


def test_scalar_threshold_builds_implication_chain():
    ms = [_cluster_market(f"t{k}", "evt_btc", "scalar_threshold", threshold=k)
          for k in (60000, 70000, 80000)]
    res = discover_constraints(ms)
    g = res.groups[0]
    assert g.relation == RelationType.CROSS_MARKET_IMPLIES.value
    # implication edges connect the 3 thresholds (2 edges)
    implies = [c for c in res.graph.constraints()
               if c.type == RelationType.CROSS_MARKET_IMPLIES]
    assert len(implies) == 2


def test_hierarchy_parent_child():
    parent = _cluster_market("parent", "evt_h", "hierarchy", role="parent")
    kids = [_cluster_market(f"kid{i}", "evt_h", "hierarchy", role="child") for i in range(2)]
    res = discover_constraints([parent] + kids)
    assert res.groups[0].relation == RelationType.HIERARCHY.value


# --- conservatism: no invented constraints ----------------------------------
def test_insufficient_metadata_when_event_cluster_has_no_kind():
    # two markets share an event but provide NO relationship metadata -> do not invent
    ms = [{"id": "a", "event_id": "evt_x", "active": True, "enableOrderBook": True,
           "clobTokenIds": ["a:y", "a:n"], "price": 0.5, "bestBid": 0.49,
           "bestAsk": 0.51, "topDepthUsd": 100},
          {"id": "b", "event_id": "evt_x", "active": True, "enableOrderBook": True,
           "clobTokenIds": ["b:y", "b:n"], "price": 0.5, "bestBid": 0.49,
           "bestAsk": 0.51, "topDepthUsd": 100}]
    res = discover_constraints(ms)
    assert res.groups == []
    assert all(s["reason"] == SKIP_INSUFFICIENT_METADATA for s in res.skipped)


# --- metrics ----------------------------------------------------------------
def test_discovery_metrics_complete():
    ms = ([_cluster_market(f"e{i}", "evt_e", "mece") for i in range(3)]
          + [{"id": "solo", "active": True, "enableOrderBook": True,
             "clobTokenIds": ["s:y", "s:n"], "outcomePrices": ["0.4", "0.6"],
             "bestBid": 0.39, "bestAsk": 0.41, "topDepthUsd": 1000}]
          + [{"id": "closed", "active": False, "outcomes": []}])
    res = discover_constraints(ms)
    m = res.metrics
    for k in ("groups_discovered", "groups_scanned", "group_type_counts",
              "avg_outcomes_per_group", "malformed_groups_rejected",
              "metadata_coverage", "book_coverage", "skip_reasons", "markets_seen"):
        assert k in m, k
    assert m["groups_discovered"] == 2          # mece cluster + solo complement
    assert m["group_type_counts"][RelationType.MECE.value] == 1
    assert 0.0 < m["metadata_coverage"] <= 1.0
    assert m["markets_seen"] == 5


def test_malformed_cluster_rejected():
    # a 'mece' cluster with only one usable outcome -> malformed, not invented
    ms = [_cluster_market("only", "evt_m", "mece"),
          {"id": "bad", "event_id": "evt_m", "group_kind": "mece", "active": True,
           "enableOrderBook": True, "price": None, "topDepthUsd": 0}]
    res = discover_constraints(ms)
    assert res.groups == []
    assert res.metrics["malformed_groups_rejected"] == 1

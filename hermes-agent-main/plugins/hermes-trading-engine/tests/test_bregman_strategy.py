"""Tests for engine.strategies.bregman (primary strategy). Tests-first."""

from __future__ import annotations

from engine.arbitrage.certificate import FeeModel
from engine.arbitrage.constraint_graph import (
    ConstraintGraph,
    Outcome,
    build_constraint_graph,
)
from engine.strategies.bregman import BregmanResult, BregmanStrategy


def test_evaluate_graph_built_from_markets_certifies_arb():
    # The activation path: markets -> graph -> evaluate. An underpriced complement
    # (0.40 + 0.40 = 0.80) must be detected + certified from market dicts.
    markets = [
        {"id": "arb", "active": True, "enableOrderBook": True, "relation": "complement",
         "outcomes": [{"id": "arb:y", "price": 0.40, "ask": 0.40, "ask_depth": 100},
                      {"id": "arb:n", "price": 0.40, "ask": 0.40, "ask_depth": 100}]},
        {"id": "fair", "active": True, "enableOrderBook": True, "relation": "complement",
         "outcomes": [{"id": "fair:y", "price": 0.50, "ask": 0.50, "ask_depth": 100},
                      {"id": "fair:n", "price": 0.50, "ask": 0.50, "ask_depth": 100}]},
    ]
    graph, skipped = build_constraint_graph(markets)
    assert skipped == []
    res = BregmanStrategy().evaluate(graph, now=0.0)
    assert res.candidates >= 1
    assert res.certified >= 1
    diag = res.audit_diagnostics()
    assert diag["constraint_groups_scanned"] == 2


def _mixed_graph():
    g = ConstraintGraph()
    # 1) underpriced complement -> certifiable arb (0.4 + 0.4 = 0.8)
    g.add_outcome(Outcome(id="a1", price=0.4, ask=0.4, ask_depth=100))
    g.add_outcome(Outcome(id="a2", price=0.4, ask=0.4, ask_depth=100))
    g.add_complement("a1", "a2")
    # 2) fairly-priced complement -> coherent, not a candidate
    g.add_outcome(Outcome(id="b1", price=0.5, ask=0.5, ask_depth=100))
    g.add_outcome(Outcome(id="b2", price=0.5, ask=0.5, ask_depth=100))
    g.add_complement("b1", "b2")
    # 3) mutually-exclusive priced > 1 -> incoherent but NOT certifiable -> FP
    g.add_outcome(Outcome(id="c1", price=0.6, ask=0.6, ask_depth=100))
    g.add_outcome(Outcome(id="c2", price=0.6, ask=0.6, ask_depth=100))
    g.add_mutually_exclusive(["c1", "c2"])
    return g


def test_evaluate_counts_candidates_certified_and_false_positives():
    res = BregmanStrategy(profit_floor=0.005).evaluate(_mixed_graph())
    assert isinstance(res, BregmanResult)
    assert res.certified == 1                       # only the underpriced complement
    assert res.certified_profit > 0
    # the >1 ME group is incoherent but not buy-set certifiable -> false positive
    assert res.false_positives >= 1
    assert res.fill_feasible == 1


def test_tradeable_only_returns_certified_fill_feasible():
    strat = BregmanStrategy(profit_floor=0.005)
    res = strat.evaluate(_mixed_graph())
    tr = res.tradeable()
    assert len(tr) == 1
    assert all(o.tradeable for o in tr)
    assert tr[0].outcome_ids == ["a1", "a2"]


def test_no_certificate_means_no_trade():
    # A profitable-looking but zero-depth complement must NOT be tradeable.
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="a", price=0.3, ask=0.3, ask_depth=0))
    g.add_outcome(Outcome(id="b", price=0.3, ask=0.3, ask_depth=0))
    g.add_complement("a", "b")
    res = BregmanStrategy().evaluate(g)
    assert res.certified == 0
    assert res.tradeable() == []


def test_certified_profit_matches_sum_of_opportunities():
    res = BregmanStrategy(profit_floor=0.005).evaluate(_mixed_graph())
    total = sum(o.certificate.total_after_fee_profit
                for o in res.opportunities if o.certificate.certified)
    assert abs(res.certified_profit - total) < 1e-6


def test_opportunity_decay():
    res = BregmanStrategy(decay_half_life_s=300.0).evaluate(_mixed_graph(), now=1000.0)
    opp = res.tradeable()[0]
    full = opp.decayed_edge(now=1000.0)
    half = opp.decayed_edge(now=1000.0 + 300.0)     # one half-life later
    assert abs(half - full * 0.5) < 1e-6
    assert half < full


def test_tradeable_respects_min_decayed_edge():
    strat = BregmanStrategy(decay_half_life_s=60.0, profit_floor=0.005)
    res = strat.evaluate(_mixed_graph(), now=0.0)
    # far in the future the decayed edge collapses below any positive threshold
    assert strat.tradeable(res, now=100000.0, min_decayed_edge=0.001) == []
    assert len(strat.tradeable(res, now=0.0, min_decayed_edge=0.0)) == 1


def test_result_to_dict_serializable():
    import json
    res = BregmanStrategy().evaluate(_mixed_graph())
    json.dumps(res.to_dict())  # must not raise

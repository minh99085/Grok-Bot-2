"""Tests for Bregman arbitrage candidate generation + telemetry."""

from __future__ import annotations

from engine.arbitrage.candidate import (
    REJECT_NOT_BUY_SET,
    REJECT_REASONS,
    REJECT_RESIDUAL_BELOW_THRESHOLD,
    CandidateBundle,
    generate_candidates,
)
from engine.arbitrage.certificate import FeeModel
from engine.arbitrage.constraint_graph import ConstraintGraph, Outcome


def _complement(a_price, b_price, depth=100, ids=("a", "b")):
    g = ConstraintGraph()
    g.add_outcome(Outcome(id=ids[0], price=a_price, ask=a_price, bid=a_price - 0.01,
                          ask_depth=depth))
    g.add_outcome(Outcome(id=ids[1], price=b_price, ask=b_price, bid=b_price - 0.01,
                          ask_depth=depth))
    g.add_complement(ids[0], ids[1])
    return g


def _mece(prices, depth=100):
    g = ConstraintGraph()
    ids = []
    for i, p in enumerate(prices):
        oid = f"m{i}"
        ids.append(oid)
        g.add_outcome(Outcome(id=oid, price=p, ask=p, bid=p - 0.01, ask_depth=depth))
    g.add_mece(ids)
    return g


TELEMETRY_FIELDS = ("projection_residual", "divergence_score", "implied_edge",
                    "gross_candidate_profit", "after_cost_candidate_profit",
                    "confidence_band", "reject_reason")


def test_coherent_group_produces_no_candidate():
    g = _complement(0.50, 0.50)
    bundles = generate_candidates(g, fee_model=FeeModel())
    assert len(bundles) == 1
    b = bundles[0]
    assert b.is_candidate is False
    assert b.reject_reason == REJECT_RESIDUAL_BELOW_THRESHOLD
    assert abs(b.projection_residual) < 1e-6


def test_incoherent_complement_produces_candidate_with_telemetry():
    g = _complement(0.40, 0.40)        # asks sum 0.80 -> arb
    bundles = generate_candidates(g, fee_model=FeeModel())
    b = bundles[0]
    assert b.is_candidate is True
    assert b.reject_reason is None
    assert b.implied_edge > 0
    assert b.gross_candidate_profit > 0
    assert b.after_cost_candidate_profit > 0
    assert b.certified is True
    lo, hi = b.confidence_band
    assert lo <= b.after_cost_candidate_profit <= hi
    d = b.to_dict()
    for f in TELEMETRY_FIELDS:
        assert f in d


def test_incoherent_multi_outcome_mece_produces_candidate():
    g = _mece([0.30, 0.30, 0.30])      # asks sum 0.90 -> arb
    bundles = generate_candidates(g, fee_model=FeeModel())
    b = bundles[0]
    assert b.is_candidate is True
    assert b.implied_edge > 0


def test_fairly_priced_mece_rejected():
    g = _mece([0.34, 0.33, 0.33])      # ~1.0 -> coherent
    b = generate_candidates(g, fee_model=FeeModel())[0]
    assert b.is_candidate is False


def test_all_reject_reasons_are_typed():
    g = _complement(0.50, 0.50)
    for b in generate_candidates(g):
        if not b.is_candidate:
            assert b.reject_reason in REJECT_REASONS


def test_candidate_ranking_is_deterministic():
    g = ConstraintGraph()
    # group 1: big arb (sum 0.80)
    g.add_outcome(Outcome(id="a1", price=0.40, ask=0.40, bid=0.39, ask_depth=100))
    g.add_outcome(Outcome(id="a2", price=0.40, ask=0.40, bid=0.39, ask_depth=100))
    g.add_complement("a1", "a2")
    # group 2: small arb (sum 0.95)
    g.add_outcome(Outcome(id="b1", price=0.475, ask=0.475, bid=0.47, ask_depth=100))
    g.add_outcome(Outcome(id="b2", price=0.475, ask=0.475, bid=0.47, ask_depth=100))
    g.add_complement("b1", "b2")
    r1 = [b.group_id for b in generate_candidates(g)]
    r2 = [b.group_id for b in generate_candidates(g)]
    assert r1 == r2                      # deterministic
    # the bigger after-cost profit ranks first
    assert generate_candidates(g)[0].group_id == "a1"


def test_friction_threshold_blocks_tiny_residual():
    # tiny mispricing (sum 0.995) below fee+spread friction -> rejected
    g = _complement(0.4975, 0.4975, depth=100)
    b = generate_candidates(g, fee_model=FeeModel(taker_fee_bps=100))[0]
    assert b.is_candidate is False
    assert b.reject_reason in (REJECT_RESIDUAL_BELOW_THRESHOLD, "edge_below_costs")


def test_non_buy_set_relation_rejected():
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="x", price=0.6, ask=0.6, bid=0.59, ask_depth=100))
    g.add_outcome(Outcome(id="y", price=0.6, ask=0.6, bid=0.59, ask_depth=100))
    g.add_mutually_exclusive(["x", "y"])   # not exactly-one-true buy set
    b = generate_candidates(g)[0]
    assert b.reject_reason == REJECT_NOT_BUY_SET

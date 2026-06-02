"""Compliance: Grok/research is advisory-only and can never bypass risk.

Quant scope — *Compliance/Security* + *Risk Management*: proves research cannot
size, approve, place, or override the EdgeEngine / risk gates. A high-confidence
research estimate is still blocked by hard gates (stale book), is held to a
stricter ambiguity bar (research_confident_but_ambiguous), and never flips
should_trade without genuine net edge. Execution/size fields emitted by Grok are
stripped before any estimate is produced.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.research.probability import ProbabilityEstimator
from engine.research.schemas import EvidenceItem, GrokProbabilityOutput, ProbabilityEstimateBundle
from engine.research.validators import (
    FORBIDDEN_EXECUTION_KEYS, forbidden_execution_keys, research_is_advisory_only,
    strip_forbidden, validate_probability_output)
from engine.training.config import TrainingConfig
from engine.training.edge_engine import EdgeEngine
from engine.training.probability_stack import ProbabilityEstimate

_NOW = 1_700_000_000_000


def _est(**kw):
    base = dict(
        market_id="m1", p_market_mid=0.5, p_model=0.5, p_research=0.95, p_raw=0.5,
        p_final=0.5, shrink=0.3, confidence=0.95, research_source="grok_cache",
        research_usable=True, model_has_edge=False, ambiguity_score=0.05,
        evidence_score=0.8, stale_score=0.0, spread=0.02, liquidity_usd=20000.0,
        calibration_error=0.0, fresh_book=True, best_ask=0.5)
    base.update(kw)
    return ProbabilityEstimate(**base)


def _rec(**kw):
    base = dict(market_id="m1", group_key="m1", top_depth_usd=1000.0,
                clob_token_ids=["t1", "t2"],
                raw={"bestBid": 0.49, "bestAsk": 0.51})
    base.update(kw)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------- #
# execution/size fields are stripped — research can never carry an order
# --------------------------------------------------------------------------- #
def test_forbidden_execution_keys_detected_and_stripped():
    raw = {"market_id": "m1", "fair_probability": 0.7, "confidence": 0.8,
           "order_size": 100, "place_order": True, "notional": 50, "approve": True}
    found = forbidden_execution_keys(raw)
    assert "order_size" in found and "place_order" in found and "notional" in found
    cleaned = strip_forbidden(raw)
    assert not any(k in cleaned for k in ("order_size", "place_order", "notional"))


def test_validated_output_has_no_execution_fields():
    raw = {"market_id": "m1", "fair_probability": 0.7, "confidence": 0.8,
           "order_size": 100, "submit_order": True}
    out = validate_probability_output(raw)
    assert out is not None
    for k in FORBIDDEN_EXECUTION_KEYS:
        assert not hasattr(out, k)


def test_probability_bundle_carries_no_size_or_approval_field():
    b = ProbabilityEstimateBundle(market_id="m1")
    for k in ("order_size", "size", "quantity", "notional", "approve",
              "place_order", "submit_order", "should_trade", "approved"):
        assert not hasattr(b, k)
    assert research_is_advisory_only() is True


# --------------------------------------------------------------------------- #
# high-confidence research + ambiguous settlement -> no-trade (estimator)
# --------------------------------------------------------------------------- #
def test_estimator_blocks_confident_but_ambiguous():
    out = GrokProbabilityOutput(
        market_id="m1", fair_probability=0.85, confidence=0.95, ambiguity_score=0.7,
        source_coverage_score=0.8,
        evidence=[EvidenceItem(source_type="official", credibility=0.9, relevance=0.9,
                               freshness=0.9, weight=0.9, direction="supports_yes")])
    b = ProbabilityEstimator().estimate(out, p_market=0.5, ts_ms=_NOW)
    assert b.no_trade_reason == "research_confident_but_ambiguous"


# --------------------------------------------------------------------------- #
# EdgeEngine: research cannot override hard gates / approve without edge
# --------------------------------------------------------------------------- #
def test_confident_research_cannot_override_stale_book():
    eng = EdgeEngine(TrainingConfig(mode="paper_train"))
    r = eng.evaluate(_est(fresh_book=False, confidence=1.0, p_final=0.9, best_ask=0.5),
                     _rec(), outcome="YES")
    assert r.should_trade is False
    assert r.reason == "no_fresh_book"


def test_confident_research_held_to_stricter_ambiguity_bar():
    cfg = TrainingConfig(mode="paper_train")
    eng = EdgeEngine(cfg)
    # ambiguity between the confident-research bar and the hard max ambiguity
    amb = 0.6 * float(cfg.max_ambiguity_score) + 0.02
    confident = eng.evaluate(_est(confidence=0.95, ambiguity_score=amb, p_final=0.9,
                                  best_ask=0.5), _rec(), outcome="YES")
    assert confident.should_trade is False
    assert confident.reason == "research_confident_but_ambiguous"
    # low-confidence research at the same ambiguity is NOT gated by this rule
    low_conf = eng.evaluate(_est(confidence=0.2, ambiguity_score=amb, p_final=0.9,
                                 best_ask=0.5), _rec(), outcome="YES")
    assert low_conf.reason != "research_confident_but_ambiguous"


def test_research_confidence_alone_does_not_approve_without_edge():
    eng = EdgeEngine(TrainingConfig(mode="paper_train"))
    # passes every hard gate but p_final == executable price -> no real edge
    r = eng.evaluate(_est(confidence=1.0, p_final=0.5, best_ask=0.5, ambiguity_score=0.05),
                     _rec(), outcome="YES")
    assert r.should_trade is False
    assert r.reason in ("edge_too_low", "uncertainty_too_high")


def test_should_trade_is_derived_from_edge_math_not_a_research_flag():
    eng = EdgeEngine(TrainingConfig(mode="paper_train"))
    r = eng.evaluate(_est(confidence=1.0, p_final=0.5, best_ask=0.5), _rec(), outcome="YES")
    # EdgeResult exposes no research-approval field that could short-circuit risk
    assert not hasattr(r, "approved")
    assert not hasattr(r, "research_approved")


# --------------------------------------------------------------------------- #
# weak-research exploration: tiny size + explicit label, never bypasses risk
# --------------------------------------------------------------------------- #
def test_weak_research_explorable_only_in_aggressive_and_never_hard_gates():
    from engine.training.edge_engine import is_explorable, is_weak_research_reason

    assert is_weak_research_reason("evidence_too_weak") is True
    # conservative mode: weak research is NOT explorable
    assert is_explorable("evidence_too_weak", aggressive_weak_research=False) is False
    # aggressive mode: weak research IS explorable
    assert is_explorable("evidence_too_weak", aggressive_weak_research=True) is True
    # hard risk/quality gates are NEVER explorable, even in aggressive mode
    for hard in ("no_fresh_book", "ambiguity_too_high", "chainlink_stale_or_irrelevant",
                 "risk_rejected", "research_confident_but_ambiguous"):
        assert is_explorable(hard, aggressive_weak_research=True) is False


def test_exploration_proposal_is_tiny_and_explicitly_labelled():
    from engine.training.paper_policy import PaperPolicy

    cfg = TrainingConfig.aggressive_paper()
    pol = PaperPolicy(cfg)
    est = _est()
    edge = pol.engine.evaluate(est, _rec(), outcome="YES")
    prop = pol.build_exploration_proposal(edge, est, _rec(), label="weak_research")
    assert prop.exploration_label == "weak_research"
    assert prop.sizing_method == "active_learning_exploration"
    # tiny: never exceeds the clamped exploratory size / paper order ceiling
    assert prop.notional_usd <= pol.explore_size() + 1e-9
    assert prop.notional_usd <= float(cfg.max_order_notional_usd) + 1e-9

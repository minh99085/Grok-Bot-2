"""Source-quality weighting + calibration impact of evidence scoring.

Quant scope — *Data Acquisition* + *Probabilistic Modeling* + *Backtesting*:
proves source diversity scoring, that higher-quality source types are weighted
above weak ones at equal credibility, that the probability estimator surfaces the
new evidence scores, and that evidence scoring improves calibration (pulls an
overconfident research probability back toward the market when evidence is weak).
"""

from __future__ import annotations

import pytest

from engine.research.ensemble import ForecastEnsemble
from engine.research.evidence_scoring import (
    evidence_quality_score, source_diversity_score)
from engine.research.probability import ProbabilityEstimator
from engine.research.schemas import EvidenceItem, GrokProbabilityOutput

_NOW = 1_700_000_000_000


def _item(**kw):
    base = {"source_type": "news", "credibility": 0.6, "relevance": 0.6,
            "freshness": 0.6, "weight": 0.6, "direction": "supports_yes"}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# source diversity
# --------------------------------------------------------------------------- #
def test_diversity_single_source_is_low():
    same = [_item(source_url="https://x.com/a"), _item(source_url="https://x.com/a"),
            _item(source_url="https://x.com/a")]
    assert source_diversity_score(same) < 0.25


def test_diversity_many_distinct_sources_is_high():
    diverse = [_item(source_type="official", source_url="https://bls.gov/cpi"),
               _item(source_type="news", source_url="https://reuters.com/a"),
               _item(source_type="exchange", source_url="https://cme.com/b"),
               _item(source_type="academic", source_url="https://nber.org/c")]
    assert source_diversity_score(diverse) > 0.6


# --------------------------------------------------------------------------- #
# source-type quality weighting at equal raw scores
# --------------------------------------------------------------------------- #
def test_official_outweighs_social_at_equal_scores():
    official = [_item(source_type="official", credibility=0.7, relevance=0.7, freshness=0.7)]
    social = [_item(source_type="social_x", credibility=0.7, relevance=0.7, freshness=0.7)]
    assert evidence_quality_score(official) > evidence_quality_score(social)


# --------------------------------------------------------------------------- #
# estimator surfaces the new scores
# --------------------------------------------------------------------------- #
def test_estimator_populates_evidence_scores_on_bundle():
    out = GrokProbabilityOutput(
        market_id="m1", outcome="YES", fair_probability=0.7, confidence=0.8,
        ambiguity_score=0.1, source_coverage_score=0.6,
        evidence=[EvidenceItem(**_item(source_type="official", credibility=0.9,
                                       relevance=0.9, freshness=0.9)),
                  EvidenceItem(**_item(source_type="news", source_url="https://reuters.com/x"))])
    est = ProbabilityEstimator()
    b = est.estimate(out, p_market=0.5, ts_ms=_NOW)
    assert 0.0 <= b.recency_score <= 1.0
    assert 0.0 <= b.source_diversity_score <= 1.0
    assert 0.0 <= b.contradiction_score <= 1.0
    assert 0.0 <= b.settlement_relevance_score <= 1.0
    assert 0.0 <= b.research_uncertainty <= 1.0


# --------------------------------------------------------------------------- #
# calibration: evidence scoring pulls overconfident llm back to market
# --------------------------------------------------------------------------- #
def _brier(pairs):
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def test_evidence_scoring_improves_calibration_on_weak_evidence():
    ens = ForecastEnsemble()
    # An overconfident LLM says YES=0.95 but the market sits at 0.50, and the
    # outcome is actually NO (0). With WEAK, contradictory, stale evidence the
    # ensemble should discount the LLM far more, landing closer to the market.
    p_market, p_llm, y = 0.50, 0.95, 0.0
    without = ens.combine(p_market=p_market, p_llm=p_llm, p_model=None,
                          confidence=0.9, evidence_score=0.9, ambiguity_score=0.0)
    with_scoring = ens.combine(p_market=p_market, p_llm=p_llm, p_model=None,
                               confidence=0.9, evidence_score=0.2, ambiguity_score=0.0,
                               recency_score=0.2, contradiction_score=0.8,
                               diversity_score=0.1)
    # discounting moves the blend back toward the (correct-side) market price
    assert with_scoring["p_ensemble"] < without["p_ensemble"]
    b_without = _brier([(without["p_ensemble"], y)])
    b_with = _brier([(with_scoring["p_ensemble"], y)])
    assert b_with < b_without


def test_evidence_scoring_defaults_are_backward_compatible():
    ens = ForecastEnsemble()
    a = ens.combine(p_market=0.5, p_llm=0.8, p_model=None, confidence=0.7,
                    evidence_score=0.6, ambiguity_score=0.1)
    b = ens.combine(p_market=0.5, p_llm=0.8, p_model=None, confidence=0.7,
                    evidence_score=0.6, ambiguity_score=0.1,
                    recency_score=1.0, contradiction_score=0.0, diversity_score=1.0)
    assert a["p_ensemble"] == pytest.approx(b["p_ensemble"])

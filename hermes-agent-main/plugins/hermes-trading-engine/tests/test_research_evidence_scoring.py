"""Research evidence scoring (source-quality-weighted, advisory-only).

Quant scope — *Evidence Preprocessing* + *Probabilistic Modeling*: proves the
evidence quality / recency / diversity / contradiction / settlement-rule
relevance scores, the confidence decay when evidence is old / contradictory /
weakly tied to resolution, and the research uncertainty component. Nothing here
sizes, approves, or places a trade.
"""

from __future__ import annotations

import pytest

from engine.research.evidence_scoring import (
    EvidenceScores, confidence_decay, contradiction_score, evidence_quality_score,
    recency_score, research_uncertainty_from, score_evidence,
    settlement_rule_relevance_score)

_NOW = 1_700_000_000_000


def _ev(**kw):
    base = {"source_type": "news", "credibility": 0.6, "relevance": 0.6,
            "freshness": 0.6, "weight": 0.6, "direction": "supports_yes",
            "published_ts_ms": _NOW, "claim": "", "source_url": "https://x.com/a"}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# evidence quality
# --------------------------------------------------------------------------- #
def test_evidence_quality_empty_is_zero():
    assert evidence_quality_score([]) == 0.0


def test_evidence_quality_strong_beats_weak():
    strong = [_ev(source_type="official", credibility=0.95, relevance=0.9, freshness=0.9)]
    weak = [_ev(source_type="social_x", credibility=0.3, relevance=0.3, freshness=0.3)]
    assert evidence_quality_score(strong) > evidence_quality_score(weak)
    assert 0.0 <= evidence_quality_score(weak) <= evidence_quality_score(strong) <= 1.0


# --------------------------------------------------------------------------- #
# recency
# --------------------------------------------------------------------------- #
def test_recency_fresh_beats_old():
    fresh = [_ev(published_ts_ms=_NOW)]
    old = [_ev(published_ts_ms=_NOW - 30 * 86_400_000)]  # 30 days old
    rf = recency_score(fresh, now_ms=_NOW, half_life_s=86_400)
    ro = recency_score(old, now_ms=_NOW, half_life_s=86_400)
    assert rf > ro
    assert rf == pytest.approx(1.0, abs=0.05)
    assert ro < 0.1


def test_recency_no_timestamp_falls_back_to_freshness():
    items = [_ev(published_ts_ms=None, freshness=0.8)]
    assert recency_score(items, now_ms=_NOW) == pytest.approx(0.8, abs=1e-6)


# --------------------------------------------------------------------------- #
# contradiction
# --------------------------------------------------------------------------- #
def test_contradiction_low_when_aligned():
    items = [_ev(direction="supports_yes", weight=0.8),
             _ev(direction="supports_yes", weight=0.7)]
    assert contradiction_score(items) < 0.2


def test_contradiction_high_when_split():
    items = [_ev(direction="supports_yes", weight=0.8),
             _ev(direction="supports_no", weight=0.8)]
    assert contradiction_score(items) > 0.6


def test_contradiction_counts_mixed_and_undermining():
    aligned = [_ev(direction="supports_yes")] * 3
    mixed = [_ev(direction="supports_yes"), _ev(direction="mixed"),
             _ev(direction="undermines_market_assumption")]
    assert contradiction_score(mixed) > contradiction_score(aligned)


# --------------------------------------------------------------------------- #
# settlement-rule relevance
# --------------------------------------------------------------------------- #
def test_settlement_relevance_uses_resolution_source_and_keywords():
    on_topic = [_ev(source_type="market_resolution_source", relevance=0.9,
                    claim="Official CPI release from the BLS on the deadline date")]
    off_topic = [_ev(source_type="social_x", relevance=0.2,
                     claim="unrelated celebrity gossip")]
    rule = {"resolution_source": "BLS CPI release",
            "criteria": ["resolves YES if the BLS CPI release exceeds 3%"]}
    on = settlement_rule_relevance_score(on_topic, rule_summary=rule)
    off = settlement_rule_relevance_score(off_topic, rule_summary=rule)
    assert on > off
    assert 0.0 <= off <= on <= 1.0


# --------------------------------------------------------------------------- #
# aggregate + confidence decay + research uncertainty
# --------------------------------------------------------------------------- #
def test_score_evidence_returns_all_components():
    items = [_ev(source_type="official", credibility=0.9, relevance=0.9, freshness=0.9,
                 direction="supports_yes", source_url="https://bls.gov/cpi"),
             _ev(source_type="news", credibility=0.6, relevance=0.7, freshness=0.6,
                 direction="supports_yes", source_url="https://reuters.com/x")]
    s = score_evidence(items, now_ms=_NOW, source_coverage=0.6)
    assert isinstance(s, EvidenceScores)
    for v in (s.quality, s.recency, s.diversity, s.contradiction,
              s.settlement_relevance, s.composite):
        assert 0.0 <= v <= 1.0
    assert s.n == 2


def test_confidence_decays_on_old_contradictory_weakly_tied_evidence():
    clean = score_evidence([_ev(source_type="official", credibility=0.9, relevance=0.9,
                                freshness=0.9, direction="supports_yes")], now_ms=_NOW)
    old = score_evidence([_ev(published_ts_ms=_NOW - 60 * 86_400_000, relevance=0.9)],
                         now_ms=_NOW, half_life_s=86_400)
    contradictory = score_evidence([_ev(direction="supports_yes", weight=0.9),
                                    _ev(direction="supports_no", weight=0.9)], now_ms=_NOW)
    base = 0.9
    assert confidence_decay(base, clean) > confidence_decay(base, old)
    assert confidence_decay(base, clean) > confidence_decay(base, contradictory)
    assert confidence_decay(base, clean) <= base + 1e-9


def test_research_uncertainty_monotone():
    strong = score_evidence([_ev(source_type="official", credibility=0.95, relevance=0.95,
                                 freshness=0.95)], now_ms=_NOW)
    weak = score_evidence([_ev(source_type="social_x", credibility=0.3, relevance=0.3,
                               freshness=0.3, direction="mixed")], now_ms=_NOW)
    assert research_uncertainty_from(weak) > research_uncertainty_from(strong)
    for s in (strong, weak):
        assert 0.0 <= research_uncertainty_from(s) <= 1.0

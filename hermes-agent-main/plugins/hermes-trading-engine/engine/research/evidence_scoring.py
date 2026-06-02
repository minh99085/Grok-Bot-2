"""Source-quality-weighted evidence scoring (research-only, deterministic).

Turns a set of research evidence items into auditable sub-scores that the
probability estimator + ensemble consume to decide HOW MUCH to trust a research
probability. It never sizes, approves, places, or bypasses risk — it only ever
discounts research confidence.

Quant scope:

* **Evidence Preprocessing** — normalizes heterogeneous evidence (dicts or
  :class:`~engine.research.schemas.EvidenceItem`) into clamped sub-scores.
* **Probabilistic Modeling** — produces an evidence *quality* score (credibility
  / relevance / freshness weighted by source-type reliability), a *recency*
  score (time-decay), a *source-diversity* score (independent sources), a
  *contradiction* score (directional disagreement), and a *settlement-rule
  relevance* score (how tied the evidence is to the market's resolution).
* **Compliance/Security** — :func:`confidence_decay` can only LOWER confidence;
  :func:`research_uncertainty_from` only ever raises uncertainty. There is no
  path here that increases position size or approves a trade.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence
from urllib.parse import urlsplit

# Source-type reliability multiplier (mirrors source_cache._DEFAULT_CRED ordering).
SOURCE_QUALITY = {
    "official": 1.0, "government": 1.0, "market_resolution_source": 1.0,
    "exchange": 0.95, "academic": 0.9, "news": 0.65, "market_page": 0.55,
    "social_x": 0.30, "unknown": 0.30,
}
# Source types whose presence directly ties evidence to market resolution.
_RESOLUTION_SOURCE_TYPES = frozenset(
    {"market_resolution_source", "official", "government", "exchange"})
_SUPPORTS = frozenset({"supports_yes", "supports_no"})
_CONFLICT_DIRECTIONS = frozenset({"mixed", "undermines_market_assumption"})

_DAY_MS = 86_400_000


def _get(item, key, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _clamp01(v) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def _domain(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        net = urlsplit(str(url)).netloc.lower()
        return net[4:] if net.startswith("www.") else net
    except Exception:  # noqa: BLE001
        return ""


def _source_quality(source_type: Optional[str]) -> float:
    return SOURCE_QUALITY.get(str(source_type or "unknown"), 0.30)


# --------------------------------------------------------------------------- #
# individual sub-scores
# --------------------------------------------------------------------------- #
def evidence_quality_score(evidence: Sequence) -> float:
    """Mean source-quality-weighted item quality in ``[0, 1]``.

    Per item: ``(0.45*credibility + 0.35*relevance + 0.20*freshness)`` scaled by
    the item's source-type reliability, then a weighted mean by the item weight.
    """
    items = list(evidence or [])
    if not items:
        return 0.0
    num = 0.0
    den = 0.0
    for e in items:
        raw_q = (0.45 * _clamp01(_get(e, "credibility", 0.0))
                 + 0.35 * _clamp01(_get(e, "relevance", 0.0))
                 + 0.20 * _clamp01(_get(e, "freshness", 0.0)))
        q = raw_q * _source_quality(_get(e, "source_type", "unknown"))
        w = max(0.05, _clamp01(_get(e, "weight", 0.0)))
        num += q * w
        den += w
    return round(_clamp01(num / den) if den else 0.0, 6)


def recency_score(evidence: Sequence, *, now_ms: Optional[int] = None,
                  half_life_s: float = 7 * 86_400.0) -> float:
    """Time-decayed recency in ``[0, 1]`` (exponential half-life).

    Uses ``published_ts_ms`` (falling back to ``retrieved_ts_ms``); items with no
    timestamp fall back to their ``freshness`` attribute. Mean over items.
    """
    items = list(evidence or [])
    if not items:
        return 0.0
    half_life_ms = max(1.0, float(half_life_s) * 1000.0)
    now = now_ms if now_ms is not None else max(
        (_get(e, "retrieved_ts_ms", 0) or 0) for e in items)
    scores = []
    for e in items:
        ts = _get(e, "published_ts_ms", None)
        if ts is None:
            ts = _get(e, "retrieved_ts_ms", None)
        if ts is None:
            scores.append(_clamp01(_get(e, "freshness", 0.0)))
            continue
        age_ms = max(0.0, float(now) - float(ts))
        scores.append(_clamp01(0.5 ** (age_ms / half_life_ms)))
    return round(sum(scores) / len(scores), 6)


def source_diversity_score(evidence: Sequence) -> float:
    """Independent-source diversity in ``[0, 1]``.

    Counts distinct ``(source_type, domain)`` pairs. One repeated source -> ~0;
    four+ independent sources -> 1.0. Rewards corroboration from independent
    sources rather than a single echoed claim.
    """
    items = list(evidence or [])
    if not items:
        return 0.0
    keys = {(str(_get(e, "source_type", "unknown")), _domain(_get(e, "source_url", "")))
            for e in items}
    return round(_clamp01((len(keys) - 1) / 3.0), 6)


def contradiction_score(evidence: Sequence) -> float:
    """Directional disagreement in ``[0, 1]``.

    Combines (a) the balance of ``supports_yes`` vs ``supports_no`` weight (a near
    50/50 split is maximally contradictory) and (b) the weight share of explicitly
    ``mixed`` / ``undermines_market_assumption`` items. Aligned evidence -> ~0.
    """
    items = list(evidence or [])
    if not items:
        return 0.0
    yes = no = conflict = total = 0.0
    for e in items:
        w = max(0.05, _clamp01(_get(e, "weight", 0.0)))
        total += w
        d = str(_get(e, "direction", "neutral"))
        if d == "supports_yes":
            yes += w
        elif d == "supports_no":
            no += w
        elif d in _CONFLICT_DIRECTIONS:
            conflict += w
    directional = yes + no
    balance = (1.0 - abs(yes - no) / directional) if directional > 0 else 0.0
    conflict_frac = (conflict / total) if total > 0 else 0.0
    return round(_clamp01(0.7 * balance + 0.3 * conflict_frac), 6)


def settlement_rule_relevance_score(evidence: Sequence, *,
                                    rule_summary: Optional[object] = None,
                                    resolution_source: Optional[str] = None) -> float:
    """How tied the evidence is to the market's resolution, in ``[0, 1]``.

    Blends (a) each item's ``relevance`` attribute, (b) a source-type boost when
    the item comes from an official/resolution source, and (c) keyword overlap
    between the item's claim and the market's resolution source + criteria.
    """
    items = list(evidence or [])
    if not items:
        return 0.0
    res_src = resolution_source
    criteria: list = []
    if rule_summary is not None:
        res_src = res_src or _get(rule_summary, "resolution_source", None)
        criteria = list(_get(rule_summary, "criteria", []) or [])
    keywords = _keywords(" ".join([str(res_src or "")] + [str(c) for c in criteria]))

    scores = []
    for e in items:
        rel = _clamp01(_get(e, "relevance", 0.0))
        type_boost = 1.0 if str(_get(e, "source_type", "")) in _RESOLUTION_SOURCE_TYPES else 0.0
        kw = 0.0
        if keywords:
            claim_kw = _keywords(str(_get(e, "claim", "") or ""))
            if claim_kw:
                kw = len(keywords & claim_kw) / float(len(keywords))
        scores.append(_clamp01(0.5 * rel + 0.3 * type_boost + 0.2 * kw))
    return round(sum(scores) / len(scores), 6)


_STOPWORDS = frozenset({
    "the", "a", "an", "if", "of", "to", "in", "on", "and", "or", "is", "are",
    "from", "by", "at", "as", "it", "for", "this", "that", "with", "yes", "no",
    "resolves", "release", "date", "than", "exceeds", "above", "below",
})


def _keywords(text: str) -> set:
    toks = [t for t in "".join(c.lower() if c.isalnum() else " " for c in (text or "")).split()
            if len(t) >= 3 and t not in _STOPWORDS]
    return set(toks)


# --------------------------------------------------------------------------- #
# aggregate + decay + uncertainty
# --------------------------------------------------------------------------- #
@dataclass
class EvidenceScores:
    quality: float = 0.0
    recency: float = 0.0
    diversity: float = 0.0
    contradiction: float = 0.0
    settlement_relevance: float = 0.0
    source_coverage: float = 0.0
    composite: float = 0.0
    n: int = 0

    def to_dict(self) -> dict:
        return {"quality": self.quality, "recency": self.recency,
                "diversity": self.diversity, "contradiction": self.contradiction,
                "settlement_relevance": self.settlement_relevance,
                "source_coverage": self.source_coverage, "composite": self.composite,
                "n": self.n}


def score_evidence(evidence: Sequence, *, rule_summary: Optional[object] = None,
                   resolution_source: Optional[str] = None,
                   now_ms: Optional[int] = None, half_life_s: float = 7 * 86_400.0,
                   source_coverage: float = 0.0) -> EvidenceScores:
    """Compute every evidence sub-score + a single composite in ``[0, 1]``.

    The composite rewards high quality, recent, diverse, on-resolution evidence
    and is reduced by contradiction. It is the single trust knob the ensemble +
    estimator use to decide how far to move off the market price.
    """
    items = list(evidence or [])
    quality = evidence_quality_score(items)
    recency = recency_score(items, now_ms=now_ms, half_life_s=half_life_s)
    diversity = source_diversity_score(items)
    contradiction = contradiction_score(items)
    relevance = settlement_rule_relevance_score(
        items, rule_summary=rule_summary, resolution_source=resolution_source)
    composite = _clamp01(
        quality
        * (0.4 + 0.6 * diversity)
        * (0.3 + 0.7 * recency)
        * (1.0 - 0.5 * contradiction)
        * (0.3 + 0.7 * relevance))
    # source coverage (breadth supplied by the model) nudges the composite up.
    composite = _clamp01(0.85 * composite + 0.15 * _clamp01(source_coverage) * quality)
    return EvidenceScores(
        quality=quality, recency=recency, diversity=diversity,
        contradiction=contradiction, settlement_relevance=relevance,
        source_coverage=round(_clamp01(source_coverage), 6),
        composite=round(composite, 6), n=len(items))


def confidence_decay(base_confidence: float, scores: EvidenceScores) -> float:
    """Decay research confidence when evidence is old, contradictory, or weakly
    tied to the market's resolution. Can only LOWER confidence (never raise)."""
    base = _clamp01(base_confidence)
    factor = (
        (0.3 + 0.7 * scores.recency)
        * (1.0 - 0.6 * scores.contradiction)
        * (0.4 + 0.6 * scores.settlement_relevance))
    return round(_clamp01(base * factor), 6)


def research_uncertainty_from(scores: EvidenceScores) -> float:
    """Research-channel uncertainty in ``[0, 1]``: high when the composite is weak
    or the evidence is contradictory. Monotone (more contradiction / weaker
    composite -> more uncertainty)."""
    return round(_clamp01(0.7 * (1.0 - scores.composite) + 0.3 * scores.contradiction), 6)

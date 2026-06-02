"""AmbiguityScorer — deterministic settlement-ambiguity scoring (0..1).

Keyword/heuristic based (no network, no LLM). High ambiguity feeds RiskEngine
rejection so the agent does not trade markets with unclear resolution rules.
"""

from __future__ import annotations

import re

# category -> trigger phrases (lowercase, substring match)
_CATEGORY_TRIGGERS = {
    "subjective_judgment": ["at the discretion", "subjective", "deemed", "in the opinion",
                            "reasonably", "widely considered", "generally accepted", "judgment"],
    "vague_threshold": ["approximately", "around", "significant", "substantial", "major",
                        "roughly", "about ", "near "],
    "missing_deadline": [],  # handled structurally (no close/deadline)
    "unclear_resolution_source": [],  # handled structurally (no resolution source)
    "conflicting_sources": ["conflicting", "disputed", "contested", "multiple sources disagree"],
    "multi_condition_resolution": [" and ", " both ", "all of the following", "as well as",
                                   "in addition to"],
    "social_media_rumor_dependency": ["tweet", "x post", "twitter", "rumor", "rumour",
                                       "social media", "viral"],
    "legal_or_regulatory_interpretation": ["court", "ruling", "regulator", "regulatory",
                                           "lawsuit", "sec ", "legal", "statute", "indictment"],
    "oracle_or_dispute_risk": ["oracle", "dispute", "uma", "challenge period", "appeal"],
    "stale_market_metadata": [],  # handled structurally
}


class AmbiguityScorer:
    def score(self, text: str, meta: dict | None = None) -> tuple[float, list[str]]:
        meta = meta or {}
        t = (text or "").lower()
        categories: list[str] = []
        for cat, triggers in _CATEGORY_TRIGGERS.items():
            if any(trig in t for trig in triggers):
                categories.append(cat)
        # structural signals
        if not meta.get("resolution_source"):
            categories.append("unclear_resolution_source")
        if not (meta.get("close_ts_ms") or meta.get("resolution_deadline_ts_ms")):
            categories.append("missing_deadline")
        if meta.get("stale_metadata"):
            categories.append("stale_market_metadata")
        # multi-condition heuristic: many " and " occurrences
        if t.count(" and ") >= 2 and "multi_condition_resolution" not in categories:
            categories.append("multi_condition_resolution")
        categories = sorted(set(categories))
        # deterministic score: each category contributes, capped at 1.0
        score = min(1.0, 0.18 * len(categories))
        # strong single-source ambiguity boosts
        if "oracle_or_dispute_risk" in categories or "subjective_judgment" in categories:
            score = min(1.0, score + 0.15)
        return round(score, 4), categories


def label_confidence(ambiguity_score: float, *, source_weight: float = 1.0) -> float:
    """Settlement-label confidence in [0,1] from ambiguity + source reliability.

    Used by the Settlement Truth Engine: a clean resolution from a reliable
    source with low ambiguity yields high confidence; high ambiguity or a weak
    source lowers it (and can demote a label to ``ambiguous``)."""
    a = float(ambiguity_score or 0.0)
    return round(max(0.0, min(1.0, float(source_weight) * (1.0 - a))), 4)


def is_settlement_ambiguous(ambiguity_score: float, threshold: float = 0.5) -> bool:
    """True when a market's resolution is too ambiguous to produce a clean label."""
    return float(ambiguity_score or 0.0) >= float(threshold)


def confident_but_ambiguous(confidence: float, ambiguity_score: float, *,
                            high_confidence: float = 0.8,
                            ambiguity_threshold: float = 0.35,
                            confident_frac: float = 0.6) -> bool:
    """True when research is HIGHLY confident yet settlement rules are ambiguous.

    Research confidence must never override settlement ambiguity: when confidence
    is high the market is held to a stricter ambiguity bar
    (``confident_frac * ambiguity_threshold``). This can only make a gate STRICTER
    — it never approves or sizes a trade."""
    c = float(confidence or 0.0)
    a = float(ambiguity_score or 0.0)
    return c >= float(high_confidence) and a >= float(confident_frac) * float(ambiguity_threshold)


def extract_terms(text: str, patterns: list[str]) -> list[str]:
    t = (text or "")
    found = []
    for p in patterns:
        for m in re.finditer(re.escape(p), t, re.IGNORECASE):
            found.append(t[m.start():m.start() + len(p)])
    return sorted(set(found))

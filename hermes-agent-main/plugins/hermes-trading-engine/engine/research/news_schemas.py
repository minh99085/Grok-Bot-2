"""Schemas for the controlled market-news evidence scanner.

These structures are the ONLY thing that ever reaches Grok from the news layer,
and they are bounded, sanitized, timestamped, and read-only. Nothing here can
size, approve, submit, or cancel a trade — news is advisory evidence only.

``NewsEvidenceItem``  — one scored, deduplicated news/evidence record.
``NewsPacket``        — the bounded, ranked packet handed to the prompt builder.
``NewsScanResult``    — scanner output: packet + provider/health/diagnostics.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Optional

# Allowed claim directions. Anything else is coerced to ``unclear`` (fail-safe).
DIRECTIONS = ("supports_yes", "supports_no", "neutral", "unclear")

# Fields that are SAFE to show Grok. Any execution/sizing-like key is never put
# on a news item and never forwarded; the grok view is an explicit allow-list.
_GROK_VIEW_FIELDS = (
    "evidence_id", "title", "source_name", "source_url", "source_type",
    "published_ts", "fetched_ts", "snippet", "direction",
    "credibility_score", "freshness_score", "relevance_score",
    "contradiction_score", "settlement_relevance_score", "ambiguity_score",
)


def _clamp01(x: object, default: float = 0.0) -> float:
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else round(v, 6)


def _norm_direction(d: object) -> str:
    s = str(d or "").strip().lower()
    return s if s in DIRECTIONS else "unclear"


@dataclass
class NewsEvidenceItem:
    """A single scored market-news evidence record (read-only, advisory)."""

    market_id: str
    query: str
    title: str
    snippet: str
    source_name: str = ""
    source_url: str = ""
    source_type: str = "unknown"
    provider: str = "offline_cache"
    published_ts: Optional[int] = None   # epoch ms, may be None
    fetched_ts: Optional[int] = None     # epoch ms, set by the scanner
    direction: str = "unclear"
    credibility_score: float = 0.0
    freshness_score: float = 0.0
    relevance_score: float = 0.0
    contradiction_score: float = 0.0
    settlement_relevance_score: float = 0.0
    ambiguity_score: float = 0.0
    evidence_id: str = ""
    hash: str = ""
    rank_score: float = 0.0

    def __post_init__(self) -> None:
        self.market_id = str(self.market_id or "")
        self.query = str(self.query or "")
        self.title = str(self.title or "")
        self.snippet = str(self.snippet or "")
        self.source_name = str(self.source_name or "")
        self.source_url = str(self.source_url or "")
        self.source_type = str(self.source_type or "unknown")
        self.provider = str(self.provider or "offline_cache")
        self.direction = _norm_direction(self.direction)
        for f in ("credibility_score", "freshness_score", "relevance_score",
                  "contradiction_score", "settlement_relevance_score",
                  "ambiguity_score", "rank_score"):
            setattr(self, f, _clamp01(getattr(self, f)))
        if self.published_ts is not None:
            try:
                self.published_ts = int(self.published_ts)
            except (TypeError, ValueError):
                self.published_ts = None
        if self.fetched_ts is not None:
            try:
                self.fetched_ts = int(self.fetched_ts)
            except (TypeError, ValueError):
                self.fetched_ts = None
        if not self.hash:
            self.hash = self.compute_hash()
        if not self.evidence_id:
            self.evidence_id = "ne_" + self.hash[:16]

    # -- hashing / dedup keys ------------------------------------------- #
    def compute_hash(self) -> str:
        norm = normalized_claim(self.title, self.snippet)
        blob = "|".join([self.market_id, self.source_url.strip().lower(), norm])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    @property
    def url_key(self) -> str:
        return self.source_url.strip().lower()

    @property
    def title_hash(self) -> str:
        return hashlib.sha256(_norm_text(self.title).encode("utf-8")).hexdigest()

    @property
    def snippet_hash(self) -> str:
        return hashlib.sha256(_norm_text(self.snippet).encode("utf-8")).hexdigest()

    @property
    def claim_hash(self) -> str:
        return hashlib.sha256(
            normalized_claim(self.title, self.snippet).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    def grok_view(self) -> dict:
        """Bounded, allow-listed view — the only shape Grok ever sees."""
        return {k: getattr(self, k) for k in _GROK_VIEW_FIELDS}


@dataclass
class NewsPacket:
    """A bounded, ranked, sanitized news packet for one market."""

    market_id: str
    items: list = field(default_factory=list)
    provider_mode: str = "offline_cache"
    queries: list = field(default_factory=list)
    fetched: int = 0
    used: int = 0
    rejected: int = 0
    stale_count: int = 0
    contradiction_count: int = 0
    ambiguity_count: int = 0
    rejected_reasons: dict = field(default_factory=dict)
    max_items: int = 8
    max_snippet_chars: int = 500

    def grok_items(self) -> list:
        return [it.grok_view() for it in self.items]

    def is_empty(self) -> bool:
        return not self.items

    def top_direction(self) -> str:
        if not self.items:
            return "unclear"
        tally: dict[str, float] = {}
        for it in self.items:
            tally[it.direction] = tally.get(it.direction, 0.0) + it.rank_score
        tally.pop("unclear", None)
        tally.pop("neutral", None)
        if not tally:
            return "neutral"
        return max(tally.items(), key=lambda kv: kv[1])[0]

    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "provider_mode": self.provider_mode,
            "queries": list(self.queries),
            "fetched": self.fetched,
            "used": self.used,
            "rejected": self.rejected,
            "stale_count": self.stale_count,
            "contradiction_count": self.contradiction_count,
            "ambiguity_count": self.ambiguity_count,
            "rejected_reasons": dict(self.rejected_reasons),
            "items": [it.to_dict() for it in self.items],
        }


@dataclass
class NewsScanResult:
    """Full scanner output for a single market scan."""

    packet: NewsPacket
    provider_mode: str
    queries: list = field(default_factory=list)
    fetched: int = 0
    used: int = 0
    rejected: int = 0
    stale_count: int = 0
    contradiction_count: int = 0
    ambiguity_count: int = 0
    provider_ok: bool = True
    provider_error: Optional[str] = None
    replay_ts_ms: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "provider_mode": self.provider_mode,
            "queries": list(self.queries),
            "fetched": self.fetched,
            "used": self.used,
            "rejected": self.rejected,
            "stale_count": self.stale_count,
            "contradiction_count": self.contradiction_count,
            "ambiguity_count": self.ambiguity_count,
            "provider_ok": self.provider_ok,
            "provider_error": self.provider_error,
            "replay_ts_ms": self.replay_ts_ms,
            "packet": self.packet.to_dict(),
        }


# -- text normalization helpers (module-level; used for dedup + hashing) -- #
def _norm_text(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def normalized_claim(title: str, snippet: str) -> str:
    """A semantic-ish normalized claim key: lowercased alnum token bag of the
    title + first part of the snippet. Used for near-duplicate detection."""
    import re
    base = f"{title} {snippet}".lower()
    toks = re.findall(r"[a-z0-9]+", base)
    # keep meaningful tokens, drop ultra-common stopwords, cap length
    stop = {"the", "a", "an", "of", "to", "in", "on", "and", "or", "for",
            "is", "are", "was", "were", "be", "by", "at", "as", "it", "that",
            "this", "with", "from", "will", "has", "have", "had"}
    toks = [t for t in toks if t not in stop]
    return " ".join(sorted(set(toks))[:40])

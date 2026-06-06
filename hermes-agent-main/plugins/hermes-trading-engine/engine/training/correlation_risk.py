"""Cluster / correlation risk — the active hard gate + capital allocator.

Pass-7 quant scope — *Risk Management & Portfolio Optimization* + *Compliance*:
ten open trades in the same hidden cluster are NOT ten independent edges; they
are one crowded bet with multiplied risk. This module derives deterministic
correlation keys from local market metadata (no external services), indexes open
paper exposure by every correlation level, and decides whether a new candidate /
bundle adds independent exposure or must be rejected, size-capped, or shadowed.

PAPER ONLY — never sizes for live, signs, or places an order. Pure + deterministic.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

# decisions
ALLOW = "allow"
ALLOW_WITH_SIZE_CAP = "allow_with_size_cap"
SHADOW_ONLY = "shadow_only"
REJECT = "reject"

# collision types
SAME_MARKET = "same_market"
SAME_CONDITION = "same_condition"
SAME_EVENT = "same_event"
SAME_CLUSTER = "same_cluster"
SEMANTIC_DUPLICATE = "semantic_duplicate"
BREGMAN_MARKET_COLLISION = "bregman_market_collision"
BREGMAN_EVENT_COLLISION = "bregman_event_collision"
DIRECTIONAL_CLUSTER_OVEREXPOSURE = "directional_cluster_overexposure"
EXPLORATION_CLUSTER_OVEREXPOSURE = "exploration_cluster_overexposure"
OPPOSITE_SIDE_CONFLICT = "opposite_side_conflict"
DUPLICATE_BUNDLE = "duplicate_bundle"
UNKNOWN_CLUSTER = "unknown_cluster_conservative_block"

# words stripped from a question when deriving the semantic key
_FILLER = {
    "will", "the", "a", "an", "by", "be", "to", "in", "of", "on", "at", "before",
    "after", "is", "are", "reach", "hit", "than", "this", "that", "for", "and",
    "or", "above", "over", "under", "below", "going", "go", "get", "it", "s",
}
# coarse entity aliases so near-identical questions share a semantic key
_ALIASES = {
    "bitcoin": "btc", "ethereum": "eth", "solana": "sol", "dogecoin": "doge",
    "president": "potus", "republican": "gop", "democrat": "dem",
    # month abbreviations (so "June 30" and "Jun 30" cluster together)
    "january": "jan", "february": "feb", "march": "mar", "april": "apr",
    "june": "jun", "july": "jul", "august": "aug", "september": "sep", "sept": "sep",
    "october": "oct", "november": "nov", "december": "dec",
}


def _expand_magnitude(tok: str) -> str:
    """120k -> 120000, 1.5m -> 1500000 (preserve numeric thresholds)."""
    m = re.fullmatch(r"\$?(\d+(?:\.\d+)?)([km])", tok)
    if not m:
        return tok
    val = float(m.group(1)) * (1_000 if m.group(2) == "k" else 1_000_000)
    return str(int(val))


def normalize_question(text: str) -> str:
    """Deterministic near-duplicate normalization. Lowercases, strips punctuation
    (keeps digits/$/%), expands k/m magnitudes, removes thousands commas + filler
    words, applies coarse entity aliases, PRESERVES negation + numeric thresholds,
    and returns a sorted unique token string (order-insensitive)."""
    t = (text or "").lower()
    t = re.sub(r"(\d),(\d)", r"\1\2", t)            # 120,000 -> 120000
    t = re.sub(r"[^a-z0-9\s\.\$%]", " ", t)
    raw_tokens = t.split()
    out: list[str] = []
    for w in raw_tokens:
        w = _expand_magnitude(w)
        w = _ALIASES.get(w, w)
        if w in ("not", "no", "never"):
            out.append("NEG")
            continue
        if w in _FILLER or len(w) == 0:
            continue
        out.append(w)
    return " ".join(sorted(set(out)))


def _sha(s: str, n: int = 12) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


def correlation_keys(rec) -> dict:
    """Multi-level correlation keys for a MarketRecord (deterministic, local)."""
    raw = getattr(rec, "raw", None) or {}
    market_id = str(getattr(rec, "market_id", "") or "")
    event_key = str(getattr(rec, "group_key", "") or f"market:{market_id}")
    cond = (raw.get("conditionId") or raw.get("negRiskMarketID")
            or raw.get("negRiskMarketId") or raw.get("condition_id"))
    condition_key = f"condition:{cond}" if cond else event_key
    nq = normalize_question(getattr(rec, "question", ""))
    semantic_key = f"sem:{_sha(nq)}" if nq else ""
    # cluster: prefer a real event/condition identity; else the semantic group.
    if event_key.startswith("market:") and semantic_key:
        cluster_key = semantic_key            # standalone -> near-duplicate cluster
    else:
        cluster_key = event_key
    tags = raw.get("tags") or []
    tag0 = (str(tags[0]) if isinstance(tags, list) and tags else
            (nq.split()[0] if nq else "na"))
    category = str(getattr(rec, "category", "uncategorized") or "uncategorized")
    correlation_group = f"corr:{category}:{tag0}"
    unknown = (not nq) and event_key.startswith("market:")
    return {
        "market_id": market_id, "market_key": f"market:{market_id}",
        "event_id": event_key, "event_key": event_key,
        "condition_id": condition_key, "condition_key": condition_key,
        "question": getattr(rec, "question", ""), "normalized_question": nq,
        "normalized_event_key": event_key,
        "slug": str(raw.get("slug") or ""), "category": category, "tags": tags,
        "resolution_source": str(getattr(rec, "resolution_source", "") or ""),
        "semantic_cluster_id": semantic_key, "cluster_id": cluster_key,
        "cluster_key": cluster_key, "event_cluster_id": event_key,
        "correlation_group": correlation_group, "unknown_cluster": bool(unknown),
    }


@dataclass
class _Bucket:
    count: int = 0
    notional: float = 0.0


class OpenExposureIndex:
    """Open paper exposure indexed by every correlation level (built per tick)."""

    def __init__(self):
        self.by_market: dict = {}
        self.by_condition: dict = {}
        self.by_event: dict = {}
        self.by_cluster: dict = {}
        self.by_group: dict = {}
        self.bregman_markets: set = set()
        self.bregman_events: set = set()

    @staticmethod
    def _add(d: dict, key: str, notional: float) -> None:
        if not key:
            return
        b = d.setdefault(key, _Bucket())
        b.count += 1
        b.notional = round(b.notional + float(notional or 0.0), 6)

    @classmethod
    def from_positions(cls, positions) -> "OpenExposureIndex":
        idx = cls()
        for p in positions:
            notional = float(getattr(p, "entry_price", 0.0) or 0.0) * float(getattr(p, "qty", 0.0) or 0.0)
            mk = f"market:{getattr(p, 'market_id', '')}"
            idx._add(idx.by_market, mk, notional)
            idx._add(idx.by_condition, getattr(p, "condition_id", "") or mk, notional)
            idx._add(idx.by_event, getattr(p, "group_key", "") or mk, notional)
            idx._add(idx.by_cluster, getattr(p, "cluster_id", "") or getattr(p, "group_key", "") or mk, notional)
            idx._add(idx.by_group, getattr(p, "correlation_group", "") or "", notional)
            if getattr(p, "strategy", "") == "bregman":
                idx.bregman_markets.add(getattr(p, "market_id", ""))
                if getattr(p, "group_key", None):
                    idx.bregman_events.add(p.group_key)
        return idx

    def count(self, level: str, key: str) -> int:
        d = getattr(self, f"by_{level}", {})
        b = d.get(key)
        return b.count if b else 0

    def notional(self, level: str, key: str) -> float:
        d = getattr(self, f"by_{level}", {})
        b = d.get(key)
        return b.notional if b else 0.0

    def summary(self) -> dict:
        top = sorted(self.by_cluster.items(), key=lambda kv: kv[1].notional, reverse=True)[:5]
        return {
            "open_clusters_count": len(self.by_cluster),
            "open_events_count": len(self.by_event),
            "open_correlation_groups_count": len(self.by_group),
            "max_cluster_exposure_usd": round(max((b.notional for b in self.by_cluster.values()),
                                                  default=0.0), 4),
            "max_event_exposure_usd": round(max((b.notional for b in self.by_event.values()),
                                                default=0.0), 4),
            "top_open_clusters": [{"cluster": k, "count": b.count,
                                   "notional": round(b.notional, 4)} for k, b in top],
        }


@dataclass
class CorrelationDecision:
    decision: str
    reason: str = ""
    collision_type: str = ""
    cluster_id: str = ""
    correlation_group: str = ""
    existing_exposure: float = 0.0
    candidate_exposure: float = 0.0
    post_trade_exposure: float = 0.0
    max_allowed_exposure: float = 0.0
    size_cap: Optional[float] = None
    keys: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d.pop("keys", None)
        return d


class CorrelationRiskGate:
    """Active correlation hard gate + size allocator (PAPER ONLY). Strategy-aware:
    directional/exploration reject duplicate market/condition/event/cluster and
    Bregman-bundle collisions; exploration is stricter; unknown clusters become
    shadow-only (or rejected) per ``unknown_cluster_policy``."""

    def __init__(self, cfg):
        self.cfg = cfg

    def _g(self, name, default):
        return getattr(self.cfg, name, default)

    def evaluate(self, keys: dict, *, strategy: str, size_usd: float,
                 index: OpenExposureIndex) -> CorrelationDecision:
        cfg = self.cfg
        cluster = keys.get("cluster_id", "")
        group = keys.get("correlation_group", "")
        base = dict(cluster_id=cluster, correlation_group=group, keys=keys,
                    candidate_exposure=round(float(size_usd or 0.0), 6))

        def D(decision, reason, collision="", **kw) -> CorrelationDecision:
            return CorrelationDecision(decision=decision, reason=reason,
                                       collision_type=collision, **base, **kw)

        if not bool(self._g("correlation_gate_enabled", True)):
            return D(ALLOW, "correlation_gate_disabled")

        # --- unknown cluster metadata: never silently trade as real edge ---
        if keys.get("unknown_cluster") and bool(self._g("require_cluster_metadata", True)):
            policy = str(self._g("unknown_cluster_policy", "shadow")).lower()
            if policy == "reject":
                return D(REJECT, "reject_missing_cluster_metadata", UNKNOWN_CLUSTER)
            return D(SHADOW_ONLY, "shadow_only_unknown_cluster", UNKNOWN_CLUSTER)

        # --- Bregman-bundle collisions (structured exposure protection) ---
        if strategy in ("directional", "exploration"):
            blk_m = ("block_directional_on_bregman_markets" if strategy == "directional"
                     else "block_exploration_on_bregman_markets")
            blk_e = ("block_directional_on_bregman_events" if strategy == "directional"
                     else "block_exploration_on_bregman_events")
            if bool(self._g(blk_m, True)) and keys["market_id"] in index.bregman_markets:
                return D(REJECT, "market_in_open_bregman_bundle", BREGMAN_MARKET_COLLISION)
            if bool(self._g(blk_e, True)) and keys["event_key"] in index.bregman_events:
                return D(REJECT, "event_in_open_bregman_bundle", BREGMAN_EVENT_COLLISION)

        # --- duplicate identity blocks ---
        if (bool(self._g("block_duplicate_market", True))
                and index.count("market", keys["market_key"])
                >= int(self._g("max_open_per_market", 1))):
            return D(REJECT, "duplicate_market_exposure", SAME_MARKET)
        if (bool(self._g("block_duplicate_market", True))
                and keys["condition_key"] != keys["event_key"]
                and index.count("condition", keys["condition_key"])
                >= int(self._g("max_open_per_market", 1))):
            return D(REJECT, "duplicate_condition_exposure", SAME_CONDITION)
        # exploration is stricter (its own per-event/cluster caps)
        if strategy == "exploration":
            max_evt = int(self._g("exploration_max_per_event", 1))
            max_clu = int(self._g("exploration_max_per_cluster", 1))
            collision_evt, collision_clu = EXPLORATION_CLUSTER_OVEREXPOSURE, EXPLORATION_CLUSTER_OVEREXPOSURE
        else:
            max_evt = int(self._g("max_open_per_event", 1))
            max_clu = int(self._g("max_open_per_cluster", 1))
            collision_evt, collision_clu = SAME_EVENT, SAME_CLUSTER
        if bool(self._g("block_duplicate_event", True)) and index.count("event", keys["event_key"]) >= max_evt:
            return D(REJECT, "event_exposure_cap", collision_evt)
        if bool(self._g("block_duplicate_cluster", True)) and index.count("cluster", cluster) >= max_clu:
            return D(REJECT, "cluster_exposure_cap", collision_clu)

        # --- $ exposure caps (size-cap when allowed, else reject) ---
        clu_open = index.notional("cluster", cluster)
        evt_open = index.notional("event", keys["event_key"])
        grp_open = index.notional("group", group)
        max_clu_usd = float(self._g("max_cluster_exposure_usd", 25.0))
        max_evt_usd = float(self._g("max_event_exposure_usd", 25.0))
        max_grp_usd = float(self._g("max_correlation_group_exposure_usd", 50.0))
        worst_open, worst_cap, worst_coll = clu_open, max_clu_usd, DIRECTIONAL_CLUSTER_OVEREXPOSURE
        for open_usd, cap_usd in ((evt_open, max_evt_usd), (grp_open, max_grp_usd)):
            if (cap_usd - open_usd) < (worst_cap - worst_open):
                worst_open, worst_cap = open_usd, cap_usd
        headroom = worst_cap - worst_open
        size = float(size_usd or 0.0)
        if size > headroom + 1e-9:
            if bool(self._g("correlation_allow_size_cap", True)) and headroom > 1e-9:
                return D(ALLOW_WITH_SIZE_CAP, "size_capped_to_cluster_headroom", worst_coll,
                         existing_exposure=round(worst_open, 6),
                         post_trade_exposure=round(worst_open + headroom, 6),
                         max_allowed_exposure=round(worst_cap, 6),
                         size_cap=round(headroom, 6))
            return D(REJECT, "cluster_exposure_would_exceed_cap", worst_coll,
                     existing_exposure=round(worst_open, 6),
                     max_allowed_exposure=round(worst_cap, 6))
        return D(ALLOW, "independent_exposure",
                 existing_exposure=round(worst_open, 6),
                 post_trade_exposure=round(worst_open + size, 6),
                 max_allowed_exposure=round(worst_cap, 6))

"""Targeted market-scan PRIORITIZATION layer (PAPER ONLY, read-only).

Sits ON TOP of the broad scan (never disables it). Uses :mod:`market_quality` to
score every scanned market, classify it into target categories (A–G), allocate extra
EVALUATION budget to high-quality categories, and deprioritize repeated scan waste
(thin / stale / invalid / duplicate / no-token / no-completeness) with a cooldown.

It NEVER trades, sizes, refreshes thresholds, or bypasses the Bregman certifier /
strict paper-realism. A high tier only buys more *attention*, not trade eligibility.
"""

from __future__ import annotations

from typing import Optional

from engine.training.market_quality import (QualityThresholds, score_market,
                                            TIER_GOLD, TIER_SILVER, TIER_BRONZE,
                                            TIER_WATCH, TIER_REJECT)

# target categories (A–G) -> router action names
CATEGORIES = (
    "high_liquidity_binary",            # A
    "complete_yes_no_tight_spread",     # B
    "negative_risk_complete",           # C
    "short_resolution",                 # D
    "btc_eth_chainlink",                # E1
    "fed_macro_reference",              # E2
    "high_volume_news_linked",          # F
    "complete_event_family",            # G
    "thin_depth_deprioritized",
    "stale_book_refresh",
    "broad_exploration",
)
_CATEGORY_ACTION = {c: f"{c}_scan" for c in CATEGORIES}

# tier -> extra evaluation budget weight (prioritization only)
_TIER_BUDGET = {TIER_GOLD: 5, TIER_SILVER: 3, TIER_BRONZE: 1, TIER_WATCH: 1, TIER_REJECT: 0}

_WASTE_REASONS = ("thin_depth", "stale_book", "invalid_simplex",
                  "duplicate_outcome_labels", "token_ids_unavailable",
                  "no_completeness_evidence")


def classify_categories(market, qs: dict, *, news_relevance: float = 0.0) -> list:
    """Return the target categories a market belongs to (read-only, multi-label).

    Negative-risk / complete-event-family categories require PROVEN completeness
    metadata (negRiskComplete / outcomeCount) — NEVER title similarity. Reference
    categories require an external reference signal in the question."""
    import re as _re
    from engine.training.market_quality import _get, _raw
    raw = _raw(market)
    cats: list = []
    sc = qs
    is_binary = bool(sc.get("is_binary"))
    tight = 0.0 < sc["spread"] <= 0.05
    fresh = sc["freshness_score"] >= 0.5
    deep = sc["side_specific_depth_score"] >= 0.3
    proven_metadata = bool(sc.get("proven_completeness_metadata"))
    binary_pair = sc["completeness_score"] == 1.0 and not proven_metadata

    if is_binary and deep and fresh and tight:
        cats.append("high_liquidity_binary")
    if binary_pair and tight and fresh:
        cats.append("complete_yes_no_tight_spread")
    if sc["completeness_score"] >= 0.9 and proven_metadata:
        cats.append("negative_risk_complete")
        cats.append("complete_event_family")
    if sc.get("resolution_days") is not None and sc["resolution_days"] <= 30.0:
        cats.append("short_resolution")
    if sc["has_external_reference"]:
        q = (raw.get("question") or _get(market, "question", "") or "")
        if _re.search(r"\b(btc|bitcoin|eth|ether|ethereum)\b", q, _re.I):
            cats.append("btc_eth_chainlink")
        else:
            cats.append("fed_macro_reference")
    if news_relevance >= 0.4 and (deep or sc["activity_score"] >= 0.3):
        cats.append("high_volume_news_linked")
    if not cats:
        cats.append("broad_exploration")
    return cats


class TargetedMarketScanner:
    """Scores + categorizes scanned markets to prioritize evaluation budget.

    Stateful only for the scan-waste COOLDOWN (down-prioritization). Has no order /
    size / gate surface — it returns telemetry + a priority-ordered evaluation plan."""

    def __init__(self, *, enabled: bool = True, cfg=None, cooldown_ticks: int = 20,
                 broad_exploration_budget: int = 25):
        self.enabled = bool(enabled)
        self.thresholds = QualityThresholds.from_cfg(cfg)
        self.cooldown_ticks = int(cooldown_ticks)
        self.broad_exploration_budget = int(broad_exploration_budget)
        self._cooldown: dict = {}          # market_id -> ticks remaining
        self._waste_streak: dict = {}      # market_id -> consecutive waste count

    def _waste_reasons(self, qs: dict, near_miss: Optional[dict]) -> list:
        out = []
        failures = qs.get("structural_failures", []) or []
        if qs.get("side_specific_depth_score", 1.0) < 0.2:
            out.append("thin_depth")
        if qs.get("freshness_score", 1.0) <= 0.0 or "book_timestamp_unparseable" in failures:
            out.append("stale_book")
        for f in ("duplicate_outcome_labels", "token_ids_unavailable"):
            if f in failures:
                out.append(f)
        if not qs.get("structural_ok", True) and qs.get("structural_failures"):
            if any(f in failures for f in ("non_numeric_bid_ask",
                                           "bid_ask_not_ordered_in_unit_interval")):
                out.append("invalid_simplex")
        if near_miss:
            r = near_miss.get("reject_reason")
            if r == "invalid_simplex":
                out.append("invalid_simplex")
            elif r == "stale_book":
                out.append("stale_book")
            elif r == "depth_too_thin":
                out.append("thin_depth")
        return sorted(set(out))

    def scan(self, records: list, *, news_by_market: Optional[dict] = None,
             near_miss_by_market: Optional[dict] = None, now: Optional[float] = None) -> dict:
        """Score + categorize records; return targeted-scan telemetry + a priority plan.

        Read-only. Broad exploration always keeps a reserved budget so targeting never
        disables broad scan."""
        news_by_market = news_by_market or {}
        near_miss_by_market = near_miss_by_market or {}
        if not self.enabled:
            return {"targeted_market_scan_enabled": False,
                    "targeted_markets_scanned_total": 0}
        # decrement cooldowns each scan
        for k in list(self._cooldown):
            self._cooldown[k] -= 1
            if self._cooldown[k] <= 0:
                del self._cooldown[k]

        tier_counts = {t: 0 for t in (TIER_GOLD, TIER_SILVER, TIER_BRONZE,
                                      TIER_WATCH, TIER_REJECT)}
        budget_by_cat: dict = {c: 0 for c in CATEGORIES}
        hits_by_cat: dict = {c: 0 for c in CATEGORIES}
        cat_markets: dict = {c: 0 for c in CATEGORIES}
        score_buckets = {"0.8+": 0, "0.6-0.8": 0, "0.4-0.6": 0, "0.2-0.4": 0, "<0.2": 0}
        waste_counts: dict = {r: 0 for r in _WASTE_REASONS}
        deprioritized = 0
        deprioritized_by_reason: dict = {}
        exploration_used = 0
        scored: list = []

        for rec in (records or []):
            mid = str((rec.get("market_id") if isinstance(rec, dict)
                       else getattr(rec, "market_id", "")) or "")
            nrel = float(news_by_market.get(mid, 0.0) or 0.0)
            qs = score_market(rec, thresholds=self.thresholds, news_relevance=nrel, now=now)
            tier = qs["market_quality_tier"]
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            s = qs["market_quality_score"]
            score_buckets["0.8+" if s >= 0.8 else "0.6-0.8" if s >= 0.6 else
                          "0.4-0.6" if s >= 0.4 else "0.2-0.4" if s >= 0.2 else "<0.2"] += 1
            cats = classify_categories(rec, qs, news_relevance=nrel)
            for c in cats:
                cat_markets[c] = cat_markets.get(c, 0) + 1
            # scan-waste cooldown (down-prioritize; keep small exploration)
            wreasons = self._waste_reasons(qs, near_miss_by_market.get(mid))
            for r in wreasons:
                waste_counts[r] = waste_counts.get(r, 0) + 1
            on_cooldown = mid in self._cooldown
            if wreasons:
                self._waste_streak[mid] = self._waste_streak.get(mid, 0) + 1
                if self._waste_streak[mid] >= 3 and not on_cooldown:
                    self._cooldown[mid] = self.cooldown_ticks
                    deprioritized += 1
                    for r in wreasons:
                        deprioritized_by_reason[r] = deprioritized_by_reason.get(r, 0) + 1
            else:
                self._waste_streak.pop(mid, None)
            # budget allocation (prioritization only)
            base = _TIER_BUDGET.get(tier, 0)
            if on_cooldown:
                base = min(base, 1)            # tiny exploration while cooled down
                exploration_used += 1
            for c in cats:
                budget_by_cat[c] = budget_by_cat.get(c, 0) + base
                if base > 0:
                    hits_by_cat[c] = hits_by_cat.get(c, 0) + 1
            scored.append({"market_id": mid, "tier": tier, "score": s,
                           "categories": cats, "depth_usd": qs["depth_usd"],
                           "spread": qs["spread"], "on_cooldown": on_cooldown,
                           "waste_reasons": wreasons})

        # reserve broad-exploration budget (targeting NEVER disables broad scan)
        budget_by_cat["broad_exploration"] = max(
            budget_by_cat.get("broad_exploration", 0), self.broad_exploration_budget)
        best = sorted(scored, key=lambda x: x["score"], reverse=True)[:10]
        noop = {c: f"no_markets_matched_{c}" for c in CATEGORIES
                if cat_markets.get(c, 0) == 0}
        return {
            "targeted_market_scan_enabled": True,
            "targeted_markets_scanned_total": len(scored),
            "targeted_scan_budget_by_category": {k: v for k, v in budget_by_cat.items() if v},
            "targeted_scan_hits_by_category": {k: v for k, v in hits_by_cat.items() if v},
            "targeted_scan_markets_by_category": {k: v for k, v in cat_markets.items() if v},
            "market_quality_tier_counts": tier_counts,
            "market_quality_score_distribution": score_buckets,
            "high_liquidity_binary_markets_scanned": cat_markets.get("high_liquidity_binary", 0),
            "complete_yes_no_tight_spread_markets_scanned":
                cat_markets.get("complete_yes_no_tight_spread", 0),
            "negative_risk_complete_events_scanned": cat_markets.get("negative_risk_complete", 0),
            "short_resolution_markets_scanned": cat_markets.get("short_resolution", 0),
            "btc_eth_chainlink_markets_scanned": cat_markets.get("btc_eth_chainlink", 0),
            "fed_macro_reference_markets_scanned": cat_markets.get("fed_macro_reference", 0),
            "high_volume_news_linked_markets_scanned":
                cat_markets.get("high_volume_news_linked", 0),
            "complete_event_families_scanned": cat_markets.get("complete_event_family", 0),
            "thin_depth_scan_waste_count": waste_counts.get("thin_depth", 0),
            "stale_book_scan_waste_count": waste_counts.get("stale_book", 0),
            "invalid_simplex_scan_waste_count": waste_counts.get("invalid_simplex", 0),
            "scan_deprioritized_groups": deprioritized,
            "scan_deprioritized_by_reason": deprioritized_by_reason,
            "scan_cooldown_active_groups": len(self._cooldown),
            "scan_exploration_budget_used": exploration_used,
            "targeted_scan_best_markets": best,
            "targeted_scan_noop_reasons": noop,
            "targeted_scan_can_execute": False, "targeted_scan_can_size": False,
        }

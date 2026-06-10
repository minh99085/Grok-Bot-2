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
    # a MISSING timestamp is UNKNOWN, not stale -> it must not disqualify a category.
    fresh = (not sc.get("freshness_known")) or sc["freshness_score"] >= 0.5
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
        """KNOWN-bad data only (never MISSING data). Missing timestamp != stale,
        missing depth != thin (those are reported separately as missing_data)."""
        out = []
        failures = qs.get("structural_failures", []) or []
        # KNOWN-thin: depth is KNOWN and below the (priority) thin floor.
        if qs.get("depth_known") and qs.get("side_specific_depth_score", 1.0) < 0.2:
            out.append("thin_depth")
        # KNOWN-stale: book age is KNOWN and beyond freshness (missing ts is NOT stale).
        if qs.get("freshness_known") and qs.get("freshness_score", 1.0) <= 0.0:
            out.append("stale_book")
        for f in ("duplicate_outcome_labels", "token_ids_unavailable"):
            if f in failures:
                out.append(f)
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

    @staticmethod
    def _missing_reasons(qs: dict) -> list:
        """Fields that are UNKNOWN (absent) — reported separately from waste so
        missing data is never miscounted as stale/thin/low-activity."""
        out = []
        if qs.get("book_timestamp_status") in ("missing", "unparseable"):
            out.append("missing_book_timestamp")
        if not qs.get("depth_known"):
            out.append("missing_depth")
        if not qs.get("activity_known"):
            out.append("missing_volume")
        return out

    def scan(self, records: list, *, news_by_market: Optional[dict] = None,
             near_miss_by_market: Optional[dict] = None,
             bregman_groups: Optional[list] = None, now: Optional[float] = None) -> dict:
        """Score + categorize records; return targeted-scan telemetry + a priority plan.

        Consumes Bregman NORMALIZED groups/near-misses (``bregman_groups``) as a
        first-class input so binary/YES-NO detection reflects ACTUAL Bregman binary
        groups (group_type/single_market_binary/outcome_labels/token_ids), not
        category-hit counts. Read-only; broad exploration keeps a reserved budget so
        targeting never disables broad scan."""
        news_by_market = news_by_market or {}
        near_miss_by_market = near_miss_by_market or {}
        bregman_groups = bregman_groups or []
        if not self.enabled:
            return {"targeted_market_scan_enabled": False,
                    "targeted_markets_scanned_total": 0}
        # --- count REAL Bregman normalized binary groups (NOT category hits) ---
        breg_binary_groups = 0
        breg_yes_no_pairs = 0
        breg_market_ids: set = set()
        breg_binary_market_ids: set = set()
        for g in bregman_groups:
            gtype = g.get("group_type") or ""
            is_binary = (gtype == "binary_yes_no") or bool(g.get("single_market_binary"))
            labels = [str(x).strip().upper() for x in (g.get("outcome_labels") or [])]
            tokens = [t for t in (g.get("token_ids") or []) if t]
            mids = [str(m) for m in (g.get("market_ids")
                                     or g.get("raw_market_ids") or []) if m]
            for m in mids:
                breg_market_ids.add(m)
            if is_binary and len(tokens) >= 2:
                breg_binary_groups += 1
                for m in mids:
                    breg_binary_market_ids.add(m)
            if labels[:2] == ["YES", "NO"] and len(tokens) >= 2:
                breg_yes_no_pairs += 1
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
        missing_counts: dict = {"missing_book_timestamp": 0, "missing_depth": 0,
                                "missing_volume": 0}
        deprioritized = 0
        deprioritized_by_reason: dict = {}
        cooldown_reason_counts: dict = {}
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
            # MISSING data (reported separately; never miscounted as waste)
            for r in self._missing_reasons(qs):
                missing_counts[r] = missing_counts.get(r, 0) + 1
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
                        cooldown_reason_counts[r] = cooldown_reason_counts.get(r, 0) + 1
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
        n = len(scored)
        # match raw scanned markets to Bregman normalized groups (by market id)
        scanned_ids = {x["market_id"] for x in scored}
        raw_market_matches = len(scanned_ids & breg_market_ids)
        binary_group_matches = len(scanned_ids & breg_binary_market_ids)
        field_source = ("bregman_normalized_groups+raw_records" if bregman_groups
                        else "raw_records_only")
        # "binaries seen" = REAL Bregman binary groups (never a category-hit count).
        binaries = breg_binary_groups
        noop: dict = {}
        for c in CATEGORIES:
            if c in ("broad_exploration",) or cat_markets.get(c, 0) > 0:
                continue
            if c == "negative_risk_complete" or c == "complete_event_family":
                noop[c] = (f"0/{n} markets carried negRiskComplete/outcomeCount metadata "
                           f"proving a complete event family (completeness is never "
                           f"inferred from titles)")
            elif c in ("btc_eth_chainlink", "fed_macro_reference"):
                noop[c] = f"0/{n} scanned questions referenced BTC/ETH or Fed/macro terms"
            elif c == "high_volume_news_linked":
                noop[c] = f"0/{n} markets had news relevance >= 0.4 this scan"
            elif c == "short_resolution":
                noop[c] = f"0/{n} markets had a parseable end date within 30 days"
            else:
                noop[c] = f"0/{n} markets matched {c} (binaries seen={binaries})"
        return {
            "targeted_market_scan_enabled": True,
            "targeted_markets_scanned_total": len(scored),
            # Bregman-normalized contract counts (real binary groups, not category hits)
            "targeted_scan_bregman_groups_seen": len(bregman_groups),
            "targeted_scan_binary_groups_seen": breg_binary_groups,
            "targeted_scan_yes_no_pairs_seen": breg_yes_no_pairs,
            "targeted_scan_binary_group_matches": binary_group_matches,
            "targeted_scan_raw_market_matches": raw_market_matches,
            "targeted_scan_field_source": field_source,
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
            # MISSING data is reported SEPARATELY from waste (missing != stale/thin)
            "targeted_scan_missing_data_counts": missing_counts,
            "missing_book_timestamp_count": missing_counts.get("missing_book_timestamp", 0),
            "missing_depth_count": missing_counts.get("missing_depth", 0),
            "missing_volume_count": missing_counts.get("missing_volume", 0),
            "scan_deprioritized_groups": deprioritized,
            "scan_deprioritized_by_reason": deprioritized_by_reason,
            "scan_cooldown_active_groups": len(self._cooldown),
            "scan_cooldown_reason_counts": cooldown_reason_counts,
            "scan_exploration_budget_used": exploration_used,
            "targeted_scan_best_markets": best,
            "targeted_scan_noop_reasons": noop,
            "targeted_scan_can_execute": False, "targeted_scan_can_size": False,
        }

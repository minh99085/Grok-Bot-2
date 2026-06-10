"""Robust tiered market-quality scoring for TARGETED SCAN PRIORITIZATION (PAPER).

Scores a market/group's *quality* purely to PRIORITIZE where the bot spends scan,
book-refresh, Grok, shadow-label, and candidate-evaluation budget. It is NOT a trade
gate: a high tier never implies trade eligibility, and a low tier never bypasses the
Bregman certifier or strict paper-realism (which decide trades). Pure + deterministic.

Hard structural checks are pass/fail (token ids, YES/NO labels, numeric & ordered
bid<ask in (0,1), parseable book timestamp, no duplicate outcomes). Everything else
is SOFT, tiered priority scoring — a market is never rejected solely for low
volume/depth; it is just down-prioritized (watch / shadow-only / cooldown).

Side-specific depth: buy-side prioritizes ASK depth (never bid+ask summed, never the
midpoint as an executable price).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from engine.arbitrage.price_parsing import parse_price

TIER_GOLD = "gold"
TIER_SILVER = "silver"
TIER_BRONZE = "bronze"
TIER_WATCH = "watch"
TIER_REJECT = "reject_or_diagnostic"

_BTC_ETH_RE = re.compile(r"\b(btc|bitcoin|eth|ether|ethereum)\b", re.I)
_MACRO_RE = re.compile(r"\b(fed|fomc|rate|rates|cpi|inflation|interest|recession|gdp|"
                       r"jobs|unemployment|treasury|powell)\b", re.I)


@dataclass
class QualityThresholds:
    """PRIORITIZATION thresholds (NOT trade gates — never affect certification).

    Defaults are tiers for *budget allocation*; they are intentionally distinct from
    the strict execution gates (min_depth_at_price, max_spread, freshness) which are
    unchanged and enforced only by the certifier / paper-realism layer."""
    gold_depth_usd: float = 250.0
    silver_depth_usd: float = 75.0
    gold_spread: float = 0.02
    silver_spread: float = 0.05
    gold_book_age_s: float = 10.0
    silver_book_age_s: float = 30.0
    gold_liquidity_usd: float = 25_000.0
    silver_liquidity_usd: float = 5_000.0
    gold_volume_24h_usd: float = 10_000.0
    short_resolution_days: float = 7.0
    gold_score: float = 0.78
    silver_score: float = 0.58
    bronze_score: float = 0.40
    watch_score: float = 0.22

    @classmethod
    def from_cfg(cls, cfg) -> "QualityThresholds":
        if cfg is None:
            return cls()
        g = lambda n, d: float(getattr(cfg, n, d) or d)  # noqa: E731
        return cls(
            gold_depth_usd=g("targeted_scan_gold_depth_usd", 250.0),
            silver_depth_usd=g("targeted_scan_silver_depth_usd", 75.0),
            gold_spread=g("targeted_scan_gold_spread", 0.02),
            silver_spread=g("targeted_scan_silver_spread", 0.05),
            gold_book_age_s=g("targeted_scan_gold_book_age_s", 10.0),
            silver_book_age_s=g("targeted_scan_silver_book_age_s", 30.0))


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _raw(market) -> dict:
    """Raw gamma dict for a market. A MarketRecord nests it under ``.raw``; a flat
    gamma/test dict IS its own raw (so both shapes score identically)."""
    if isinstance(market, dict):
        nested = market.get("raw")
        return nested if isinstance(nested, dict) and nested else market
    return getattr(market, "raw", {}) or {}


def _clamp01(x) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


_BOOK_TS_FIELDS = ("bookUpdatedTs", "orderBookTs", "book_updated_ts",
                   "updatedAt", "updated_at", "lastTradeTime")


def _book_ts_raw(market):
    raw = _raw(market)
    for k in _BOOK_TS_FIELDS:
        v = raw.get(k)
        if v not in (None, ""):
            return v
    return None


def parse_book_timestamp(market):
    """Parse a book timestamp -> epoch seconds, or None (sec/ms/ISO/missing).

    Delegates to the ONE canonical parser shared with ``MarketRecord.book_age_s`` so
    freshness never diverges. A MISSING timestamp returns None (unknown, NOT stale)."""
    from engine.arbitrage.price_parsing import parse_epoch_seconds
    return parse_epoch_seconds(_book_ts_raw(market))


def book_timestamp_present(market) -> bool:
    """True iff a book-timestamp field is present (regardless of parseability)."""
    return _book_ts_raw(market) is not None


def structural_checks(market) -> dict:
    """Hard pass/fail structural checks (no soft scoring). Returns ``ok`` + a list of
    explicit ``failures``. Binary markets require YES/NO labels + token ids; bid/ask
    must be numeric and ordered ``0 < bid < ask < 1``; book ts must parse; outcome
    labels must not duplicate. The midpoint is NEVER used as an executable price."""
    raw = _raw(market)
    failures: list = []
    from engine.arbitrage.constraint_graph import parse_list_field
    tokens = parse_list_field(raw.get("clobTokenIds")) or list(
        _get(market, "clob_token_ids", []) or [])
    labels = parse_list_field(raw.get("outcomes"))
    bid = parse_price(raw.get("bestBid"))
    ask = parse_price(raw.get("bestAsk"))
    n_outcomes = max(len(labels), len(parse_list_field(raw.get("outcomePrices"))))
    is_binary = (n_outcomes == 2) or (len(tokens) == 2) or (
        _get(market, "group_key", "") and n_outcomes <= 2)

    if not tokens:
        failures.append("token_ids_unavailable")
    if is_binary and labels and len(labels) >= 2:
        lab = [str(x).strip().upper() for x in labels[:2]]
        if not ({"YES", "NO"} <= set(lab)) and not all(lab):
            failures.append("binary_labels_missing")
    if labels:
        norm = [str(x).strip().lower() for x in labels if str(x).strip()]
        if len(norm) != len(set(norm)):
            failures.append("duplicate_outcome_labels")
    if bid is None or ask is None:
        failures.append("non_numeric_bid_ask")
    else:
        if not (0.0 < bid < ask < 1.0):
            failures.append("bid_ask_not_ordered_in_unit_interval")
    # Book-timestamp is a SOFT freshness signal, NOT a hard structural failure.
    # Distinguish MISSING (field absent -> unknown) from UNPARSEABLE (present but bad).
    ts_present = book_timestamp_present(market)
    ts_parsed = parse_book_timestamp(market)
    book_timestamp_status = ("ok" if ts_parsed is not None else
                             "unparseable" if ts_present else "missing")
    # a "critical" failure forces reject_or_diagnostic tier (never tradeable anyway).
    # A missing/unparseable timestamp is NEVER critical (it is unknown, not bad).
    critical = bool(set(failures) & {"non_numeric_bid_ask",
                                     "bid_ask_not_ordered_in_unit_interval",
                                     "duplicate_outcome_labels"})
    return {"ok": not failures, "failures": failures, "critical": critical,
            "is_binary": bool(is_binary), "n_outcomes": n_outcomes,
            "token_ids_available": bool(tokens), "best_bid": bid, "best_ask": ask,
            "book_timestamp_status": book_timestamp_status,
            "book_timestamp_present": bool(ts_present)}


def side_specific_depth(legs, *, side: str = "buy") -> dict:
    """Per-leg executable depth (NEVER bid+ask summed). Buy prioritizes ASK-side
    visible depth; sell prioritizes BID-side. Returns min/median/worst leg depth +
    executable notional at the touch."""
    import statistics
    side = (side or "buy").lower()
    depths = []
    for leg in (legs or []):
        if side == "sell":
            d = _get(leg, "visible_bid_depth_usd", None)
        else:
            d = _get(leg, "visible_ask_depth_usd", None)
        if d is None:
            d = _get(leg, "depth_usd", None)
        if d is None:
            d = _get(leg, "top_depth_usd", 0.0)
        depths.append(float(d or 0.0))
    if not depths:
        return {"min_leg_depth_usd": 0.0, "median_leg_depth_usd": 0.0,
                "worst_leg_depth_usd": 0.0, "executable_notional_usd": 0.0,
                "n_legs": 0, "side": side}
    return {
        "min_leg_depth_usd": round(min(depths), 4),
        "median_leg_depth_usd": round(statistics.median(depths), 4),
        "worst_leg_depth_usd": round(min(depths), 4),
        "executable_notional_usd": round(sum(depths), 4),  # context only, NOT a gate
        "n_legs": len(depths), "side": side,
    }


def _resolution_days(market, now: Optional[float] = None):
    import time as _t
    end = _get(market, "end_ts", None)
    if end is None:
        raw = _raw(market)
        for k in ("endDate", "end_date", "endDateIso"):
            v = raw.get(k)
            if v:
                m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v))
                if m:
                    import datetime as _dt
                    try:
                        end = _dt.datetime(int(m.group(1)), int(m.group(2)),
                                           int(m.group(3))).timestamp()
                    except ValueError:
                        end = None
                break
    if not end:
        return None
    now = now or _t.time()
    return max(0.0, (float(end) - now) / 86400.0)


def completeness_score(market) -> float:
    """Metadata-PROVEN completeness only (negRiskComplete / outcomeCount). Title
    similarity is NEVER used. Binary single markets are inherently complete."""
    raw = _raw(market)
    if raw.get("negRiskComplete") or raw.get("complete_set") or raw.get("exhaustive"):
        return 1.0
    # a single binary market is a complete YES/NO pair by construction
    from engine.arbitrage.constraint_graph import parse_list_field
    n = max(len(parse_list_field(raw.get("outcomes"))),
            len(parse_list_field(raw.get("outcomePrices"))))
    if n == 2:
        return 1.0
    oc = raw.get("outcomeCount") or raw.get("outcome_count")
    try:
        if oc is not None and int(oc) == n and n >= 2:
            return 0.9
    except (TypeError, ValueError):
        pass
    return 0.3 if n >= 2 else 0.0


def score_market(market, *, thresholds: Optional[QualityThresholds] = None,
                 news_relevance: float = 0.0, now: Optional[float] = None) -> dict:
    """Compute the tiered market-quality score + all sub-scores (PRIORITIZATION ONLY).

    Returns ``market_quality_score`` in [0,1], a ``market_quality_tier``
    (gold/silver/bronze/watch/reject_or_diagnostic), the structural-check result, and
    every sub-score. NEVER a trade gate."""
    th = thresholds or QualityThresholds()
    sc = structural_checks(market)
    raw = _raw(market)
    bid, ask = sc["best_bid"], sc["best_ask"]
    spread = (ask - bid) if (bid is not None and ask is not None) else \
        float(_get(market, "spread", 0.0) or 0.0)

    # --- DEPTH: KNOWN only with a REAL top-of-book depth field (missing depth !=
    # thin). Liquidity is NOT top-of-book depth -> a liquidity-only estimate is used
    # for ranking but marked UNKNOWN so it is never penalized as thin. ---
    _real_depth = None
    for _k in ("topDepthUsd", "top_depth_usd", "orderMinSize"):
        v = raw.get(_k)
        if v not in (None, ""):
            _real_depth = parse_price(v)
            break
    _rec_depth = _get(market, "top_depth_usd", None)   # may be a liquidity-derived est
    depth_known = _real_depth is not None
    depth_usd = float(_real_depth if _real_depth is not None else (_rec_depth or 0.0))
    liq = float(_get(market, "liquidity_usd", 0.0) or parse_price(raw.get("liquidityNum")) or 0.0)
    vol24 = float(_get(market, "volume_24h_usd", 0.0) or 0.0)
    activity_known = (vol24 > 0) or (raw.get("volume24hr") not in (None, "")) \
        or (raw.get("volumeNum") not in (None, ""))
    # --- FRESHNESS: separate KNOWN age from MISSING timestamp (missing != stale) ---
    book_age = _get(market, "book_age_s", None)
    if book_age is None:
        _bts = parse_book_timestamp(market)
        if _bts is not None:
            import time as _t
            book_age = max(0.0, (now or _t.time()) - _bts)
    freshness_known = book_age is not None
    res_days = _resolution_days(market, now=now)

    # --- soft sub-scores in [0,1] (saturating; never hard pass/fail) ---
    # MISSING data -> NEUTRAL priority (not penalized as thin/stale/low-activity).
    side_depth_score = (_clamp01(depth_usd / max(1e-9, th.gold_depth_usd))
                        if depth_known else 0.4)
    worst_leg_depth_score = side_depth_score          # single-market = its own depth
    liquidity_score = _clamp01(liq / max(1e-9, th.gold_liquidity_usd)) if liq else (
        0.4 if not activity_known else 0.0)
    activity_score = _clamp01(vol24 / max(1e-9, th.gold_volume_24h_usd)) \
        if activity_known else 0.4
    spread_score = _clamp01(1.0 - (max(0.0, spread) / max(1e-9, th.silver_spread)))
    if not freshness_known:
        freshness_score = 0.5                          # unknown age = NEUTRAL (not stale)
    else:
        freshness_score = _clamp01(1.0 - (float(book_age) / max(1e-9, th.silver_book_age_s)))
    if res_days is None:
        resolution_horizon_score = 0.4
    else:
        resolution_horizon_score = _clamp01(1.0 - (res_days / 60.0))  # shorter = higher
    comp_score = completeness_score(market)
    q = (_get(market, "question", "") or raw.get("question") or "")
    is_ref = bool(_BTC_ETH_RE.search(q) or _MACRO_RE.search(q))
    external_reference_score = 0.8 if is_ref else 0.0
    news_rel = _clamp01(news_relevance)
    # scan-waste risk: only from KNOWN-bad data (structural break / KNOWN-thin /
    # KNOWN-stale) — never from missing/unknown fields.
    waste = 0.0
    if sc["critical"]:
        waste += 0.6
    if depth_known and depth_usd < th.silver_depth_usd:
        waste += 0.2
    if freshness_known and float(book_age) > th.silver_book_age_s:
        waste += 0.2
    scan_waste_risk_score = _clamp01(waste)

    score = round(
        0.22 * side_depth_score + 0.15 * spread_score + 0.15 * freshness_score
        + 0.12 * liquidity_score + 0.10 * activity_score + 0.10 * comp_score
        + 0.06 * resolution_horizon_score + 0.05 * external_reference_score
        + 0.05 * news_rel, 6)
    score = round(_clamp01(score - 0.15 * scan_waste_risk_score), 6)

    # tier: a CRITICAL structural failure is reject_or_diagnostic regardless of score.
    if sc["critical"]:
        tier = TIER_REJECT
    elif (score >= th.gold_score and depth_usd >= th.gold_depth_usd
          and spread <= th.gold_spread):
        tier = TIER_GOLD
    elif score >= th.silver_score:
        tier = TIER_SILVER
    elif score >= th.bronze_score:
        tier = TIER_BRONZE
    elif score >= th.watch_score:
        tier = TIER_WATCH
    else:
        tier = TIER_REJECT
    return {
        "market_id": str(_get(market, "market_id", "") or ""),
        "market_quality_score": score,
        "market_quality_tier": tier,
        "structural_ok": sc["ok"],
        "structural_failures": sc["failures"],
        "liquidity_score": round(liquidity_score, 4),
        "side_specific_depth_score": round(side_depth_score, 4),
        "worst_leg_depth_score": round(worst_leg_depth_score, 4),
        "spread_score": round(spread_score, 4),
        "freshness_score": round(freshness_score, 4),
        "activity_score": round(activity_score, 4),
        "resolution_horizon_score": round(resolution_horizon_score, 4),
        "completeness_score": round(comp_score, 4),
        "external_reference_score": round(external_reference_score, 4),
        "news_relevance_score": round(news_rel, 4),
        "scan_waste_risk_score": round(scan_waste_risk_score, 4),
        "resolution_days": res_days,
        "depth_usd": round(depth_usd, 4),
        "spread": round(spread, 6),
        "has_external_reference": is_ref,
        "is_binary": bool(sc["is_binary"]),
        "proven_completeness_metadata": bool(
            raw.get("negRiskComplete") or raw.get("complete_set") or raw.get("outcomeCount")),
        # MISSING vs KNOWN flags (so callers never count missing data as bad data)
        "depth_known": bool(depth_known),
        "freshness_known": bool(freshness_known),
        "activity_known": bool(activity_known),
        "book_timestamp_status": sc.get("book_timestamp_status"),
        "book_age_s": (round(float(book_age), 3) if freshness_known else None),
        # hard invariant — quality NEVER implies executability
        "trade_eligible": False,
    }

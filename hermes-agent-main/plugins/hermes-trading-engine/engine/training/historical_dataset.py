"""Tier-1 historical dataset: resolved Polymarket markets -> point-in-time (no-look-ahead)
``(observed_probability, settled_outcome)`` observations for backtesting, walk-forward
validation, and learner warm-start.

POINT-IN-TIME SAFETY (no look-ahead): the FEATURE is the YES price observed a fixed LEAD
before resolution — reconstructed from Gamma's trailing price-change fields
(``price_at_lead = last_price - price_change_over_lead``). The LABEL is the settled outcome,
which is only knowable at/after resolution (strictly in the future relative to the feature).
A model trained on these can never peek at the resolution when forming the feature.

Only CLEANLY resolved markets are used (settled YES/NO, not void/ambiguous/unresolved).
Network access is isolated to :func:`fetch_resolved_markets` (injectable for offline tests).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from engine.markets import universe_manager as um

logger = logging.getLogger("hte.training.historical_dataset")

# Gamma trailing price-change field -> (lead label, lead seconds). Used to reconstruct the
# YES price `lead` before resolution: price_at_lead = last_price - change_over_lead.
LEAD_WINDOWS = {
    "1h": ("oneHourPriceChange", 3600.0),
    "1d": ("oneDayPriceChange", 86400.0),
    "1w": ("oneWeekPriceChange", 604800.0),
    "1mo": ("oneMonthPriceChange", 2592000.0),
}

_RESOLVED_OK = ("resolved", "")          # umaResolutionStatus values we accept as settled


@dataclass
class ResolvedObservation:
    """One point-in-time observation from a resolved market."""
    market_id: str
    category: str
    lead_label: str
    observed_prob: float        # YES price `lead` before resolution (the feature)
    outcome: int                # settled YES=1 / NO=0 (the label, known only at resolution)
    resolved_ts: float
    observed_ts: float          # resolved_ts - lead_seconds (feature timestamp)

    def as_pair(self) -> "tuple[float, int]":
        return (float(self.observed_prob), int(self.outcome))


def _clamp(p: float, lo: float = 0.02, hi: float = 0.98) -> float:
    return max(lo, min(hi, float(p)))


def market_outcome(raw: dict) -> Optional[int]:
    """Settled YES(1)/NO(0) for a CLEANLY resolved market, else None (skip).

    Requires the market be closed and (when present) ``umaResolutionStatus`` to be a
    settled value, and the settled YES price to be unambiguous (near 0 or near 1)."""
    if not raw.get("closed"):
        return None
    status = str(raw.get("umaResolutionStatus") or "").strip().lower()
    if status not in _RESOLVED_OK:
        return None
    prices = um._parse_list(raw.get("outcomePrices"))
    y = um._as_float(prices[0], None) if prices else None
    if y is None:
        return None
    if y >= 0.95:
        return 1
    if y <= 0.05:
        return 0
    return None                  # mid -> not cleanly settled; never fabricate a label


def _resolved_ts(raw: dict) -> Optional[float]:
    from engine.arbitrage.price_parsing import parse_epoch_seconds
    for k in ("closedTime", "closed_time", "endDate", "endDateIso", "updatedAt"):
        v = raw.get(k)
        if v not in (None, ""):
            ts = parse_epoch_seconds(v)
            if ts is not None:
                return ts
    return None


def _last_price(raw: dict, outcome: int) -> float:
    """The market's final YES price (≈ resolution). Prefer the real last trade; fall back
    to the settled price for the outcome."""
    lp = um._as_float(raw.get("lastTradePrice"), None)
    if lp is not None and 0.0 <= lp <= 1.0:
        return lp
    prices = um._parse_list(raw.get("outcomePrices"))
    y = um._as_float(prices[0], None) if prices else None
    return y if y is not None else float(outcome)


def build_observations(resolved_markets: list, *, leads=("1d", "1w", "1mo"),
                       min_lead_move: float = 0.0) -> list[ResolvedObservation]:
    """Build point-in-time observations from cleanly-resolved markets.

    For each market and each requested ``lead`` window with a trailing price-change field,
    reconstruct the YES price that far before resolution and pair it with the settled
    outcome. ``min_lead_move`` optionally drops observations whose price barely moved (the
    reconstructed past price ≈ the settled price → low information)."""
    out: list[ResolvedObservation] = []
    for raw in (resolved_markets or []):
        if not isinstance(raw, dict):
            continue
        oc = market_outcome(raw)
        if oc is None:
            continue
        rts = _resolved_ts(raw)
        if rts is None:
            continue
        last = _last_price(raw, oc)
        cat = str(raw.get("category") or raw.get("categorySlug") or "uncategorized")
        mid = str(raw.get("id") or raw.get("slug") or "")
        for lead in leads:
            spec = LEAD_WINDOWS.get(lead)
            if spec is None:
                continue
            field, secs = spec
            ch = um._as_float(raw.get(field), None)
            if ch is None:
                continue
            if abs(float(ch)) < float(min_lead_move):
                continue
            p_lead = _clamp(last - float(ch))
            out.append(ResolvedObservation(
                market_id=mid, category=cat, lead_label=lead, observed_prob=p_lead,
                outcome=oc, resolved_ts=float(rts), observed_ts=float(rts) - secs))
    out.sort(key=lambda o: o.observed_ts)        # chronological for walk-forward splitting
    logger.debug("built %d resolved observations from %d markets", len(out),
                 len(resolved_markets or []))
    return out


_GAMMA = "https://gamma-api.polymarket.com"


def fetch_resolved_markets(*, limit: int = 2000, client=None,
                           order: str = "volume24hr") -> list:
    """Fetch up to ``limit`` CLOSED (resolved) markets from the public Gamma API. The ONLY
    network function here; injectable ``client`` keeps the builder offline-testable. Pulls
    the trailing price-change fields used for point-in-time reconstruction."""
    import httpx

    own = client is None
    client = client or httpx.Client(timeout=20.0)
    out: list = []
    try:
        offset = 0
        page = 100
        while len(out) < limit:
            want = min(page, limit - len(out))
            try:
                r = client.get(f"{_GAMMA}/markets",
                               params={"closed": "true", "archived": "false",
                                       "limit": want, "offset": offset,
                                       "order": order, "ascending": "false"})
            except Exception:  # noqa: BLE001 — network hiccup -> stop with what we have
                break
            # Gamma caps the offset (HTTP 422 beyond the window); stop gracefully and keep
            # the markets fetched so far rather than failing the whole validation run.
            if getattr(r, "status_code", 200) != 200:
                break
            try:
                batch = r.json()
            except ValueError:
                break
            if not isinstance(batch, list) or not batch:
                break
            out.extend(batch)
            if len(batch) < want:
                break
            offset += len(batch)
    finally:
        if own:
            client.close()
    return out[:limit]

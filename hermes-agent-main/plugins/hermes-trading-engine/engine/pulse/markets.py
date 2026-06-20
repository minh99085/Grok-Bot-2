"""Ingestion of the Polymarket ``btc-up-or-down-5m`` rolling windows (READ-ONLY).

Each event is a single binary market ("Up"/"Down") over a fixed 5-minute window. The
window OPEN is encoded in the event slug (``btc-updown-5m-<open_unix_ts>``) and the
CLOSE is the market ``endDate``. Resolution (per the market description) is::

    Up  iff  Chainlink_BTC_close >= Chainlink_BTC_open    (ties -> Up)

This module fetches the current/upcoming windows + their Up/Down CLOB token ids and the
live order book. It never trades; it only reads public Gamma + CLOB endpoints.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("hte.pulse.markets")

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
SERIES_SLUG_5M = "btc-up-or-down-5m"
WINDOW_SECONDS = 300

_SLUG_TS_RE = re.compile(r"-(\d{9,11})$")


def _iso_to_unix(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


@dataclass
class OrderBook:
    """Top-of-book snapshot for one CLOB token (read-only)."""
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    bid_depth_usd: float = 0.0
    ask_depth_usd: float = 0.0
    ts: float = 0.0

    @property
    def mid(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return round((self.best_bid + self.best_ask) / 2.0, 6)
        return self.best_bid if self.best_bid is not None else self.best_ask

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return round(self.best_ask - self.best_bid, 6)
        return None


@dataclass
class PulseWindow:
    """One BTC 5-minute up/down window."""
    event_id: str
    market_id: str
    slug: str
    title: str
    open_ts: float
    close_ts: float
    up_token_id: str
    down_token_id: str
    tick_size: float = 0.01
    up_book: Optional[OrderBook] = None
    down_book: Optional[OrderBook] = None

    def seconds_to_close(self, now: Optional[float] = None) -> float:
        return self.close_ts - float(now if now is not None else time.time())

    def seconds_since_open(self, now: Optional[float] = None) -> float:
        return float(now if now is not None else time.time()) - self.open_ts

    def is_open(self, now: Optional[float] = None) -> bool:
        n = float(now if now is not None else time.time())
        return self.open_ts <= n < self.close_ts

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "market_id": self.market_id, "slug": self.slug,
                "title": self.title, "open_ts": self.open_ts, "close_ts": self.close_ts,
                "up_token_id": self.up_token_id, "down_token_id": self.down_token_id,
                "tick_size": self.tick_size,
                "up_mid": self.up_book.mid if self.up_book else None,
                "up_spread": self.up_book.spread if self.up_book else None}


class PulseMarketFeed:
    """Read-only client for the btc-up-or-down-5m series + CLOB books."""

    def __init__(self, *, timeout_s: float = 8.0, series_slug: str = SERIES_SLUG_5M,
                 http_get=None):
        self.timeout_s = float(timeout_s)
        self.series_slug = series_slug
        self._get = http_get          # injectable for tests: (url, params) -> (status, json)
        self._client = None

    def _http(self, url: str, params: dict) -> "tuple[int, object]":
        if self._get is not None:
            return self._get(url, params)
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=self.timeout_s,
                                        headers={"User-Agent": "hermes-btc-pulse/1.0"})
        try:
            r = self._client.get(url, params=params)
            return r.status_code, (r.json() if r.status_code == 200 else None)
        except Exception as exc:  # noqa: BLE001 — a read never raises into the loop
            logger.debug("pulse http error %s", exc)
            return 0, None

    @staticmethod
    def parse_window(event: dict) -> Optional[PulseWindow]:
        """Build a :class:`PulseWindow` from a Gamma event dict (or None if malformed)."""
        try:
            markets = event.get("markets") or []
            if not markets:
                return None
            m = markets[0]
            toks = m.get("clobTokenIds")
            if isinstance(toks, str):
                toks = json.loads(toks or "[]")
            outs = m.get("outcomes")
            if isinstance(outs, str):
                outs = json.loads(outs or "[]")
            if not toks or len(toks) < 2 or len(outs) < 2:
                return None
            # map outcome name -> token (robust to ordering)
            up_tok = down_tok = None
            for name, tok in zip(outs, toks):
                if str(name).strip().lower() == "up":
                    up_tok = str(tok)
                elif str(name).strip().lower() == "down":
                    down_tok = str(tok)
            if up_tok is None or down_tok is None:
                up_tok, down_tok = str(toks[0]), str(toks[1])
            close_ts = _iso_to_unix(m.get("endDate") or event.get("endDate"))
            slug = str(event.get("slug") or "")
            open_ts = None
            mt = _SLUG_TS_RE.search(slug)
            if mt:
                open_ts = float(mt.group(1))
            if close_ts is None and open_ts is not None:
                close_ts = open_ts + WINDOW_SECONDS
            if open_ts is None and close_ts is not None:
                open_ts = close_ts - WINDOW_SECONDS
            if open_ts is None or close_ts is None:
                return None
            tick = float(m.get("orderPriceMinTickSize") or 0.01)
            return PulseWindow(
                event_id=str(event.get("id") or ""), market_id=str(m.get("id") or ""),
                slug=slug, title=str(event.get("title") or m.get("question") or ""),
                open_ts=float(open_ts), close_ts=float(close_ts),
                up_token_id=up_tok, down_token_id=down_tok, tick_size=tick)
        except Exception as exc:  # noqa: BLE001
            logger.debug("parse_window failed: %s", exc)
            return None

    def fetch_windows(self, *, limit: int = 60) -> list:
        """Current + upcoming windows for the series, ascending by close time."""
        status, data = self._http(f"{GAMMA}/events",
                                   {"series_slug": self.series_slug, "closed": "false",
                                    "order": "endDate", "ascending": "true",
                                    "limit": int(limit)})
        if status != 200 or not isinstance(data, list):
            return []
        out = []
        for ev in data:
            w = self.parse_window(ev)
            if w is not None:
                out.append(w)
        out.sort(key=lambda w: w.close_ts)
        return out

    def active_windows(self, *, now: Optional[float] = None, lookahead_s: float = 330.0,
                       limit: int = 60) -> list:
        """Windows that are open now or open within ``lookahead_s`` (so we can snapshot the
        open price the moment they begin)."""
        n = float(now if now is not None else time.time())
        out = []
        for w in self.fetch_windows(limit=limit):
            if w.close_ts <= n:
                continue                       # already closed
            if w.open_ts <= n + lookahead_s:   # open now or about to open
                out.append(w)
        return out

    def fetch_book(self, token_id: str) -> Optional[OrderBook]:
        """Top-of-book + shallow depth for one token (read-only)."""
        status, data = self._http(f"{CLOB}/book", {"token_id": token_id})
        if status != 200 or not isinstance(data, dict):
            return None
        bids = data.get("bids") or []
        asks = data.get("asks") or []

        def _lvls(side):
            out = []
            for x in side:
                try:
                    out.append((float(x["price"]), float(x["size"])))
                except (KeyError, TypeError, ValueError):
                    continue
            return out
        bids = _lvls(bids)
        asks = _lvls(asks)
        # CLOB returns bids ascending and asks ascending; best bid = highest, best ask = lowest
        best_bid = max((p for p, _ in bids), default=None)
        best_ask = min((p for p, _ in asks), default=None)
        return OrderBook(
            best_bid=best_bid, best_ask=best_ask,
            bid_depth_usd=round(sum(p * s for p, s in bids), 2),
            ask_depth_usd=round(sum(p * s for p, s in asks), 2),
            ts=time.time())

    def hydrate_books(self, window: PulseWindow) -> PulseWindow:
        """Attach live Up/Down books to a window (read-only)."""
        window.up_book = self.fetch_book(window.up_token_id)
        window.down_book = self.fetch_book(window.down_token_id)
        return window

    def fetch_resolution(self, market_id: str) -> Optional[bool]:
        """Authoritative Polymarket resolution for a CLOSED market: returns True if it
        resolved ``Up``, False if ``Down``, or None if not yet resolved. Read-only."""
        status, m = self._http(f"{GAMMA}/markets/{market_id}", {})
        if status != 200 or not isinstance(m, dict):
            return None
        # only trust a genuinely resolved market
        if not (m.get("closed") or m.get("umaResolutionStatus") == "resolved"):
            # outcomePrices may still pin to 0/1 once resolved even if 'closed' lags
            pass
        outs = m.get("outcomes")
        prices = m.get("outcomePrices")
        if isinstance(outs, str):
            outs = json.loads(outs or "[]")
        if isinstance(prices, str):
            prices = json.loads(prices or "[]")
        if not outs or not prices or len(outs) != len(prices):
            return None
        try:
            mapping = {str(o).strip().lower(): float(p) for o, p in zip(outs, prices)}
        except (TypeError, ValueError):
            return None
        up = mapping.get("up")
        down = mapping.get("down")
        if up is None or down is None:
            return None
        # resolved markets pin to (1.0, 0.0); require a decisive split
        if up >= 0.99 and down <= 0.01:
            return True
        if down >= 0.99 and up <= 0.01:
            return False
        return None

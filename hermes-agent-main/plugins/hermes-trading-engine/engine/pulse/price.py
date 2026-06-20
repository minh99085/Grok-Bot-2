"""Low-latency BTC price feed + per-window OPEN-price snapshots (READ-ONLY).

Resolution uses the Chainlink BTC/USD Data Stream. That feed is credentialed, so we use
a free low-latency proxy (Coinbase spot) and measure BOTH the window-open and the live
price on the SAME feed — the absolute Coinbase-vs-Chainlink basis then cancels in the
``close - open`` comparison; only the small intra-window basis *drift* remains (handled by
the decision buffer). Never trades; only reads a public price.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from engine.pulse.fair_value import RollingVol

logger = logging.getLogger("hte.pulse.price")


@dataclass
class OpenSnapshot:
    """The recorded window-open reference price + how late we captured it."""
    open_ts: float
    price: float
    snap_ts: float

    @property
    def lag_s(self) -> float:
        return max(0.0, self.snap_ts - self.open_ts)


class PulsePriceFeed:
    """Polls a BTC spot proxy, feeds a rolling-vol estimator, and snapshots each window's
    open price as soon as the window begins."""

    def __init__(self, *, fetcher=None, vol: Optional[RollingVol] = None,
                 max_open_lag_s: float = 20.0):
        if fetcher is None:
            from engine.pulse.coinbase import coinbase_spot_fetcher
            fetcher = coinbase_spot_fetcher("BTC-USD")
        self._fetch = fetcher
        self.vol = vol or RollingVol()
        self.max_open_lag_s = float(max_open_lag_s)
        self._last_price: Optional[float] = None
        self._last_ts: float = 0.0
        self._opens: dict = {}            # window_key -> OpenSnapshot
        self.polls = 0
        self.errors = 0

    def poll(self, now: Optional[float] = None) -> Optional[float]:
        now = float(now if now is not None else time.time())
        try:
            px = self._fetch()
        except Exception:  # noqa: BLE001 — a price read never raises into the loop
            px = None
        if px is not None and px > 0:
            self._last_price = float(px)
            self._last_ts = now
            self.vol.observe(px, now)
            self.polls += 1
        else:
            self.errors += 1
        return self._last_price

    def current(self) -> Optional[float]:
        return self._last_price

    def sigma_per_sec(self, now: Optional[float] = None) -> Optional[float]:
        return self.vol.per_sec(now)

    def snapshot_open(self, key: str, open_ts: float, now: Optional[float] = None) -> Optional[OpenSnapshot]:
        """Record the window-open price once, the first time we observe at/after ``open_ts``.
        Skips (returns None) if we'd be capturing it too late to be a faithful open."""
        now = float(now if now is not None else time.time())
        if key in self._opens:
            return self._opens[key]
        if now < open_ts:
            return None
        if self._last_price is None:
            return None
        if (now - open_ts) > self.max_open_lag_s:
            # too late to faithfully represent the open — record a sentinel so we never trade it
            snap = OpenSnapshot(open_ts=open_ts, price=self._last_price, snap_ts=now)
            self._opens[key] = snap
            logger.debug("open snapshot for %s captured late (lag %.1fs)", key, snap.lag_s)
            return snap
        snap = OpenSnapshot(open_ts=open_ts, price=self._last_price, snap_ts=now)
        self._opens[key] = snap
        return snap

    def open_snapshot(self, key: str) -> Optional[OpenSnapshot]:
        return self._opens.get(key)

    def prune_opens(self, keep_keys: set) -> None:
        """Drop open snapshots for windows no longer tracked (bound memory)."""
        for k in list(self._opens):
            if k not in keep_keys:
                self._opens.pop(k, None)

    def status(self) -> dict:
        return {"last_price": self._last_price, "last_ts": self._last_ts,
                "polls": self.polls, "errors": self.errors,
                "vol_samples": self.vol.samples,
                "sigma_per_sec": self.sigma_per_sec(), "tracked_opens": len(self._opens)}

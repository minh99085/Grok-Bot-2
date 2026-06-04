"""Chainlink BTC/USD oracle wrapper — operational, auditable, PAPER ONLY.

Wraps an existing :class:`~engine.feeds.chainlink.ChainlinkSource` and exposes a
single, fully-validated BTC/USD reading with freshness/staleness, consecutive
failure tracking, and structured logs so Docker logs + status endpoints can
prove Chainlink is really running.

Read-only: it only *reads* an on-chain aggregator value. It never trades, never
signs, never touches a wallet. Deterministic for tests via an injected source +
clock.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import asdict, dataclass
from typing import Callable, Optional

logger = logging.getLogger("hte.chainlink.oracle")

DEFAULT_FEED_KEY = "BTC/USD"

# BTC Pulse oracle blocker reasons (stable strings used by the gate + status).
BLOCKER_DISABLED = "chainlink_disabled"
BLOCKER_NOT_INITIALIZED = "chainlink_not_initialized"
BLOCKER_MISSING_PRICE = "chainlink_missing_price"
BLOCKER_INVALID_PRICE = "chainlink_invalid_price"
BLOCKER_MISSING_TIMESTAMP = "chainlink_missing_timestamp"
BLOCKER_STALE = "chainlink_stale"
BLOCKER_PROVIDER_ERROR = "chainlink_provider_error"


@dataclass
class ChainlinkOracleStatus:
    """Fully-validated snapshot of the BTC/USD oracle (auditable)."""

    enabled: bool
    initialized: bool
    symbol: str = DEFAULT_FEED_KEY
    source: str = "chainlink"
    price: Optional[float] = None
    updated_at: Optional[float] = None      # on-chain updatedAt (unix seconds)
    observed_at: float = 0.0                 # when we read it (unix seconds)
    age_seconds: Optional[float] = None
    heartbeat_seconds: int = 120
    max_age_seconds: int = 180
    stale: bool = True
    valid: bool = False
    error: Optional[str] = None
    consecutive_failures: int = 0
    last_success_at: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def oracle_blocker(status: ChainlinkOracleStatus) -> Optional[str]:
    """Map an oracle status to the BTC Pulse blocker reason, or None if usable."""
    if not status.enabled:
        return BLOCKER_DISABLED
    if not status.initialized:
        return BLOCKER_NOT_INITIALIZED
    if status.error and status.error.startswith("provider_error"):
        return BLOCKER_PROVIDER_ERROR
    if status.price is None:
        return BLOCKER_MISSING_PRICE
    if status.error == "invalid_price":
        return BLOCKER_INVALID_PRICE
    if status.error == "missing_timestamp":
        return BLOCKER_MISSING_TIMESTAMP
    if status.stale or not status.valid:
        return BLOCKER_STALE
    return None


class ChainlinkBtcUsdOracle:
    """Validated, auditable BTC/USD Chainlink reader (read-only, PAPER ONLY)."""

    def __init__(self, source=None, *, enabled: bool = True,
                 feed_key: str = DEFAULT_FEED_KEY, heartbeat_seconds: int = 120,
                 max_age_seconds: int = 180, registry: Optional[dict] = None,
                 clock: Optional[Callable[[], float]] = None,
                 debug_log: bool = False):
        self.enabled = bool(enabled)
        self.source = source
        self.feed_key = feed_key
        self.heartbeat_seconds = max(1, int(heartbeat_seconds))
        self.max_age_seconds = max(1, int(max_age_seconds))
        self._clock = clock or time.time
        self.debug_log = bool(debug_log)
        self.consecutive_failures = 0
        self.last_success_at: Optional[float] = None
        self._last: Optional[ChainlinkOracleStatus] = None
        self.initialized = bool(self.enabled and source is not None)
        # resolve the public BTC/USD feed spec (metadata only; no secrets)
        self.spec = None
        try:
            reg = registry
            if reg is None and self.enabled:
                from engine.feeds.chainlink_registry import load_registry
                reg = load_registry()
            self.spec = (reg or {}).get(feed_key)
        except Exception:  # noqa: BLE001 — registry must never break startup
            self.spec = None
        if self.initialized:
            logger.info("ChainlinkFeedProvider initialized symbol=%s heartbeat_seconds=%d "
                        "max_age_seconds=%d", feed_key, self.heartbeat_seconds,
                        self.max_age_seconds)

    # -- reading -------------------------------------------------------- #
    def read(self, now: Optional[float] = None) -> ChainlinkOracleStatus:
        now = float(now) if now is not None else float(self._clock())
        st = ChainlinkOracleStatus(
            enabled=self.enabled, initialized=self.initialized, symbol=self.feed_key,
            observed_at=now, heartbeat_seconds=self.heartbeat_seconds,
            max_age_seconds=self.max_age_seconds)
        if not self.enabled:
            self._last = st
            return st
        if self.source is None:
            st.initialized = False
            st.error = "not_initialized"
            self.consecutive_failures += 1
            st.consecutive_failures = self.consecutive_failures
            self._last = st
            return st

        reading = None
        try:
            # Prefer the THROTTLED/CACHED history path (shared with the Chainlink
            # scanner) so we don't hammer the RPC every tick and get rate-limited;
            # fall back to a direct read only when no cached reading exists.
            if hasattr(self.source, "history"):
                hist = self.source.history(self.feed_key, now=now, limit=1)
                reading = hist[-1] if hist else None
            if reading is None and self.spec is not None:
                reading = self.source.read(self.spec, now)
        except Exception as exc:  # noqa: BLE001 — never raise from a read
            self.consecutive_failures += 1
            st.error = f"provider_error:{type(exc).__name__}"
            st.consecutive_failures = self.consecutive_failures
            st.last_success_at = self.last_success_at
            self._last = st
            logger.warning("Chainlink BTC/USD provider error: %s", st.error)
            return st

        if reading is None:
            self.consecutive_failures += 1
            st.error = "missing_price"
            st.consecutive_failures = self.consecutive_failures
            st.last_success_at = self.last_success_at
            self._last = st
            return st

        price = float(getattr(reading, "value", float("nan")))
        updated_at = getattr(reading, "updated_at", None)
        st.price = price if math.isfinite(price) else None
        st.updated_at = float(updated_at) if updated_at else None

        if not math.isfinite(price) or price <= 0.0:
            self.consecutive_failures += 1
            st.error = "invalid_price"
            st.valid = False
        elif not st.updated_at:
            self.consecutive_failures += 1
            st.error = "missing_timestamp"
            st.valid = False
        else:
            age = max(0.0, now - st.updated_at)
            st.age_seconds = round(age, 3)
            st.stale = age > self.max_age_seconds
            st.valid = not st.stale
            if st.valid:
                self.consecutive_failures = 0
                self.last_success_at = now
            else:
                self.consecutive_failures += 1
                st.error = "stale"

        st.consecutive_failures = self.consecutive_failures
        st.last_success_at = self.last_success_at
        self._last = st
        if self.debug_log:
            logger.info("Chainlink BTC/USD latest price=%s", st.price)
            logger.info("Chainlink BTC/USD freshness age_seconds=%s stale=%s valid=%s",
                        st.age_seconds, st.stale, st.valid)
        return st

    def last_status(self) -> ChainlinkOracleStatus:
        """Return the most recent read without hitting the source again."""
        if self._last is not None:
            return self._last
        return ChainlinkOracleStatus(
            enabled=self.enabled, initialized=self.initialized, symbol=self.feed_key,
            observed_at=float(self._clock()), heartbeat_seconds=self.heartbeat_seconds,
            max_age_seconds=self.max_age_seconds)

    def status(self, *, refresh: bool = False, now: Optional[float] = None) -> dict:
        st = self.read(now) if refresh else self.last_status()
        return st.to_dict()

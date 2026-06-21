"""Polymarket Real-Time Data Socket (RTDS) client — the CANONICAL oracle proxy.

Polymarket publishes, on one no-auth WebSocket (``wss://ws-live-data.polymarket.com``):
  * ``crypto_prices_chainlink`` (symbol ``btc/usd``) — the **Chainlink Data Streams reference
    price Polymarket resolves Up/Down on**. This is our canonical oracle for open/close.
  * ``crypto_prices`` (symbol ``btcusdt``) — Binance, a fast LEAD predictor (feature only).

This client streams both on a background daemon, sends a PING every 5s, reconnects on drop,
and exposes the latest (price, ts) per (topic, symbol). READ-ONLY: it never trades. Fail-open:
if it cannot connect, latest prices are None and the engine falls back to its proxy feed.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger("hte.pulse.rtds")

RTDS_URL = "wss://ws-live-data.polymarket.com"
TOPIC_CHAINLINK = "crypto_prices_chainlink"
TOPIC_BINANCE = "crypto_prices"
PING_INTERVAL_S = 5.0


def _sub_msg(subs: list) -> str:
    # RTDS requires the per-subscription ``filters`` to be COMPACT JSON (no spaces) — a spaced
    # filter string silently matches nothing and no updates are delivered.
    return json.dumps({"action": "subscribe", "subscriptions": [
        {"topic": t, "type": "*", "filters": json.dumps({"symbol": s}, separators=(",", ":"))}
        for t, s in subs]})


class RTDSClient:
    """Streams Chainlink (oracle) + Binance (lead) prices from Polymarket RTDS."""

    def __init__(self, *, subscriptions: Optional[list] = None, url: str = RTDS_URL,
                 reconnect_delay_s: float = 3.0, spike_filter: float = 0.10):
        # subscriptions: list of (topic, symbol)
        self.subscriptions = subscriptions or [(TOPIC_CHAINLINK, "btc/usd"),
                                               (TOPIC_BINANCE, "btcusdt")]
        self.url = url
        self.reconnect_delay_s = float(reconnect_delay_s)
        self.spike_filter = float(spike_filter)
        self._latest: dict = {}            # (topic, symbol) -> (price, ts_ms, observed_ts)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.messages = 0
        self.reconnects = 0
        self.connected = False

    # -- public read -------------------------------------------------------- #
    def latest_price(self, topic: str, symbol: str) -> Optional[float]:
        with self._lock:
            v = self._latest.get((topic, symbol.lower()))
        return v[0] if v else None

    def latest(self, topic: str, symbol: str) -> Optional[tuple]:
        with self._lock:
            return self._latest.get((topic, symbol.lower()))

    def oracle_price(self) -> Optional[float]:
        return self.latest_price(TOPIC_CHAINLINK, "btc/usd")

    def _record(self, topic: str, symbol: str, value: float, ts_ms: Optional[float]) -> None:
        key = (topic, symbol.lower())
        now = time.time()
        with self._lock:
            prev = self._latest.get(key)
            if prev and prev[0] > 0 and abs(value - prev[0]) / prev[0] > self.spike_filter:
                return                     # reject >10% spike (bad tick guard)
            self._latest[key] = (value, ts_ms, now)
        self.messages += 1

    @staticmethod
    def _parse_update(msg: str) -> Optional[tuple]:
        """Parse an RTDS 'update' frame -> (topic, symbol, value, ts_ms) or None.
        Skips empty heartbeats + initial history dumps (no topic/symbol)."""
        if not msg or not msg.strip():
            return None
        try:
            d = json.loads(msg)
        except (ValueError, TypeError):
            return None
        topic = d.get("topic")
        payload = d.get("payload") or {}
        if not topic or not isinstance(payload, dict):
            return None
        symbol = payload.get("symbol")
        value = payload.get("value")
        if symbol is None or value is None:
            return None
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        if v <= 0:
            return None
        return topic, str(symbol), v, payload.get("timestamp")

    def _run(self) -> None:
        from websockets.sync.client import connect
        sub = _sub_msg(self.subscriptions)
        while not self._stop.is_set():
            try:
                with connect(self.url, open_timeout=10, ping_interval=None) as ws:
                    ws.send(sub)
                    self.connected = True
                    last_ping = time.time()
                    while not self._stop.is_set():
                        now = time.time()
                        if now - last_ping >= PING_INTERVAL_S:
                            try:
                                ws.send("PING")
                            except Exception:  # noqa: BLE001
                                break
                            last_ping = now
                        try:
                            msg = ws.recv(timeout=2.0)
                        except TimeoutError:
                            continue
                        except Exception:  # noqa: BLE001 — connection issue -> reconnect
                            break
                        parsed = self._parse_update(msg)
                        if parsed:
                            self._record(*parsed)
            except Exception:  # noqa: BLE001 — never let the stream thread die
                logger.debug("RTDS connect failed", exc_info=True)
            self.connected = False
            if self._stop.is_set():
                break
            self.reconnects += 1
            self._stop.wait(self.reconnect_delay_s)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="rtds-client", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict:
        with self._lock:
            latest = {f"{t}:{s}": (round(v[0], 2) if v else None)
                      for (t, s), v in self._latest.items()}
        return {"url": self.url, "connected": self.connected, "messages": self.messages,
                "reconnects": self.reconnects, "latest": latest,
                "running": bool(self._thread is not None and self._thread.is_alive())}

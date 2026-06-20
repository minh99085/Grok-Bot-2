"""Local BTC technical / fair-value signal (PAPER / RESEARCH ONLY, read-only).

The bot already ingests a live BTC spot price (Coinbase fast feed, cross-checked vs the
Chainlink anchor). This module turns that price *series* into a directional probability +
confidence for BTC/ETH Polymarket markets — the one lane where the bot has a genuine,
independent signal (most markets just echo the mid). It is the in-house equivalent of a
TradingView indicator panel, computed on the price the engine already has (no external
account, no network here).

Two market kinds:
* STRIKE markets ("Will BTC be above $X at T") -> a realized-volatility FAIR-VALUE model:
  zero-drift lognormal P(S_T > K) from the live price S, strike K, horizon tau, and the
  rolling realized vol. This is a genuine *pricing* edge (Tier 1).
* DIRECTIONAL markets ("Bitcoin Up or Down") -> a small momentum / EMA-trend / RSI ensemble
  (Tier 2/3), bounded to a small deviation from 0.5 (short-horizon BTC is near-efficient).

Strict-safety invariants: pure math + a bounded in-memory price ring; never trades, sizes,
or places an order; never loosens a gate. The output is advisory — it feeds the probability
stack's model channel + evidence score, and the credible after-cost gate still decides.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("hte.training.btc_signal")

_COINBASE_SPOT = "https://api.coinbase.com/v2/prices/{sym}/spot"
_ASSET_SYMBOLS = {"BTC": "BTC-USD", "ETH": "ETH-USD"}

_BTC_ETH_RE = re.compile(r"\b(btc|bitcoin|eth|ether|ethereum)\b", re.I)
# "$66,000" / "66000" / "$72.5k" strike extraction
_STRIKE_RE = re.compile(r"\$?\s*([0-9][0-9,\.]*)\s*(k)?", re.I)
_ABOVE_RE = re.compile(r"\b(above|over|reach|hit|exceed|greater|\bup\b to|>=?)\b", re.I)
_BELOW_RE = re.compile(r"\b(below|under|dip|less|drop to|fall to|<=?)\b", re.I)
_UPDOWN_RE = re.compile(r"\bup or down\b|\bup/down\b|\bhigher or lower\b", re.I)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via erf (stdlib)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass
class BtcSignal:
    """Advisory directional probability for a BTC/ETH market's YES outcome."""

    p_up: float                       # P(YES) — fair value (strike) or directional (up/down)
    confidence: float                 # [0,1] data-sufficiency x signal sharpness/agreement
    kind: str                         # "fair_value_strike" | "directional" | "none"
    components: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"p_up": round(self.p_up, 4), "confidence": round(self.confidence, 4),
                "kind": self.kind, "components": self.components}


def realized_vol_per_sec(samples: list) -> Optional[float]:
    """Per-SECOND volatility (sqrt of time-normalized variance of log returns) from a list of
    (ts, price). None when there is too little data. Robust to irregular spacing."""
    pts = [(float(t), float(p)) for t, p in samples if p and float(p) > 0]
    if len(pts) < 12:
        return None
    num = 0.0
    dt_tot = 0.0
    for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        r = math.log(p1 / p0)
        num += r * r
        dt_tot += dt
    if dt_tot <= 0 or num <= 0:
        return None
    return math.sqrt(num / dt_tot)


def _ema(values: list, period: int) -> Optional[float]:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    e = values[0]
    for v in values[1:]:
        e = alpha * v + (1 - alpha) * e
    return e


def rsi(values: list, period: int = 14) -> Optional[float]:
    if len(values) < period + 1:
        return None
    gains = losses = 0.0
    for a, b in zip(values[-period - 1:], values[-period:]):
        d = b - a
        gains += max(0.0, d)
        losses += max(0.0, -d)
    if (gains + losses) <= 0:
        return 50.0
    rs = gains / losses if losses > 0 else float("inf")
    return 100.0 - (100.0 / (1.0 + rs))


def fair_value_above(spot: float, strike: float, vol_per_sec: float,
                     tau_seconds: float) -> Optional[float]:
    """Zero-drift lognormal P(S_T > K). Conservative (no drift assumption)."""
    if spot <= 0 or strike <= 0 or vol_per_sec <= 0 or tau_seconds <= 0:
        return None
    sigma_h = vol_per_sec * math.sqrt(tau_seconds)         # vol over the horizon
    if sigma_h <= 1e-9:
        return 1.0 if spot >= strike else 0.0
    d2 = (math.log(spot / strike) - 0.5 * sigma_h * sigma_h) / sigma_h
    return max(0.0, min(1.0, _norm_cdf(d2)))


def directional_fair_value(mu_per_sec: float, vol_per_sec: float, tau_seconds: float,
                           *, max_dev: float = 0.20) -> Optional[float]:
    """P(price is UP over the next ``tau`` seconds) for an 'Up or Down at T' market, under a
    drifting log-normal: ln(S_T/S_t) ~ N((mu-0.5*sig^2)*tau, sig^2*tau), so
    P(up) = Phi((mu-0.5*sig^2)*sqrt(tau)/sig). The drift ``mu`` is the recent per-second
    momentum estimate. Bounded to +/- ``max_dev`` from 0.5 because short-horizon crypto
    direction is near-efficient (we never claim a large directional edge)."""
    if vol_per_sec <= 0 or tau_seconds <= 0:
        return None
    sig_h = vol_per_sec * math.sqrt(tau_seconds)
    if sig_h <= 1e-9:
        return None
    z = (mu_per_sec - 0.5 * vol_per_sec * vol_per_sec) * tau_seconds / sig_h
    p = _norm_cdf(z)
    return max(0.5 - max_dev, min(0.5 + max_dev, p))


def parse_btc_market(question: str) -> dict:
    """Parse a BTC/ETH market question into {kind, strike, direction}. Read-only/best-effort."""
    q = str(question or "")
    if not _BTC_ETH_RE.search(q):
        return {"kind": "none"}
    if _UPDOWN_RE.search(q):
        return {"kind": "directional", "direction": "up"}
    below = bool(_BELOW_RE.search(q))
    above = bool(_ABOVE_RE.search(q))
    m = _STRIKE_RE.search(q.replace(",", "") if "," in q else q)
    strike = None
    # search on the comma-stripped string for a clean number
    ms = re.search(r"\$?\s*([0-9][0-9\.]{2,})\s*(k)?", q.replace(",", ""), re.I)
    if ms:
        try:
            val = float(ms.group(1))
            if ms.group(2):                      # "72.5k"
                val *= 1000.0
            strike = val
        except (TypeError, ValueError):
            strike = None
    if strike is not None and (above or below):
        return {"kind": "strike", "strike": strike,
                "direction": "below" if below else "above"}
    # references BTC/ETH but no clean strike/up-down -> treat as weak directional
    return {"kind": "directional", "direction": "up"}


class BtcSignalEngine:
    """Maintains a bounded BTC price ring (fed each tick) and produces advisory BTC signals.

    PAPER/RESEARCH ONLY: pure computation over the price the engine already ingests; never
    trades, sizes, places orders, or loosens a gate."""

    def __init__(self, *, max_samples: int = 4000, min_samples: int = 15,
                 directional_max_dev: float = 0.12, ema_fast: int = 9, ema_slow: int = 21,
                 rsi_period: int = 14, momentum_window_s: float = 300.0):
        self._buf: deque = deque(maxlen=int(max_samples))
        self.min_samples = int(min_samples)
        self.directional_max_dev = float(directional_max_dev)
        self.ema_fast = int(ema_fast)
        self.ema_slow = int(ema_slow)
        self.rsi_period = int(rsi_period)
        self.momentum_window_s = float(momentum_window_s)
        self.observations = 0

    def observe(self, price: Optional[float], now: Optional[float] = None) -> None:
        if price is None:
            return
        try:
            p = float(price)
        except (TypeError, ValueError):
            return
        if p <= 0:
            return
        self._buf.append((float(now if now is not None else time.time()), p))
        self.observations += 1

    @property
    def ready(self) -> bool:
        return len(self._buf) >= self.min_samples

    def indicators(self) -> dict:
        # snapshot the ring ONCE (the sampler thread appends concurrently; iterating a live
        # deque while it mutates raises — a single list() copy is atomic enough under the GIL).
        snap = list(self._buf)
        prices = [p for _, p in snap]
        vps = realized_vol_per_sec(snap)
        out = {"n": len(prices), "spot": prices[-1] if prices else None,
               "vol_per_sec": vps, "ema_fast": _ema(prices, self.ema_fast),
               "ema_slow": _ema(prices, self.ema_slow), "rsi": rsi(prices, self.rsi_period)}
        # short-horizon momentum (total log return) + per-SECOND drift over the window
        mom = drift = None
        if snap:
            now_ts = snap[-1][0]
            past = [(t, p) for t, p in snap if now_ts - t <= self.momentum_window_s]
            if len(past) >= 2 and past[0][1] > 0:
                mom = math.log(prices[-1] / past[0][1])
                span = now_ts - past[0][0]
                drift = (mom / span) if span > 0 else None
        out["momentum"] = mom
        out["drift_per_sec"] = drift
        return out

    def _directional_p_up(self, ind: dict) -> "tuple[float, float, dict]":
        """Bounded directional P(up) from momentum + EMA trend + RSI (short-horizon BTC is
        near-efficient, so the deviation from 0.5 is small). Returns (p_up, agreement, comps)."""
        votes = []
        comps = {}
        mom = ind.get("momentum")
        if mom is not None:
            v = math.tanh(mom / 0.01)            # ~+/-1 around a 1% move
            votes.append(v)
            comps["momentum_vote"] = round(v, 3)
        ef, es = ind.get("ema_fast"), ind.get("ema_slow")
        if ef is not None and es is not None and es > 0:
            v = math.tanh((ef - es) / es / 0.005)
            votes.append(v)
            comps["ema_trend_vote"] = round(v, 3)
        r = ind.get("rsi")
        if r is not None:
            v = (50.0 - r) / 50.0                # RSI mean-reversion: high RSI -> down vote
            votes.append(max(-1.0, min(1.0, v)))
            comps["rsi_vote"] = round(v, 3)
        if not votes:
            return 0.5, 0.0, comps
        avg = sum(votes) / len(votes)
        p_up = max(0.0, min(1.0, 0.5 + self.directional_max_dev * avg))
        # agreement: 1 when votes align in sign, lower when they conflict
        same = sum(1 for v in votes if (v >= 0) == (avg >= 0))
        agreement = same / len(votes)
        return p_up, agreement, comps

    def signal_for_market(self, question: str, *, end_ts: Optional[float],
                          now: Optional[float] = None) -> Optional[BtcSignal]:
        """Advisory BTC signal for a market, or None when not a BTC market / not enough data."""
        parsed = parse_btc_market(question)
        if parsed.get("kind") == "none" or not self.ready:
            return None
        ind = self.indicators()
        spot = ind.get("spot")
        vps = ind.get("vol_per_sec")
        now = float(now if now is not None else (self._buf[-1][0] if self._buf else time.time()))
        if parsed["kind"] == "strike" and spot and vps and end_ts:
            tau = float(end_ts) - now
            if tau <= 0:
                return None
            p_above = fair_value_above(spot, float(parsed["strike"]), vps, tau)
            if p_above is None:
                return None
            p_up = p_above if parsed.get("direction") == "above" else (1.0 - p_above)
            # confidence: sharper (far from 0.5) + enough data + not absurdly long horizon
            sharp = abs(p_up - 0.5) * 2.0
            data_ok = min(1.0, ind["n"] / max(1, self.min_samples * 4))
            conf = max(0.0, min(1.0, 0.4 * data_ok + 0.6 * sharp))
            return BtcSignal(p_up=p_up, confidence=conf, kind="fair_value_strike",
                             components={"spot": round(spot, 2), "strike": parsed["strike"],
                                         "tau_s": round(tau, 1),
                                         "vol_per_sec": round(vps, 8)})
        # directional ("Up or Down at T"). PREFER the principled drift/vol fair value when we
        # have a horizon + a vol estimate (P(up over tau) under a drifting log-normal); fall
        # back to the bounded momentum/EMA/RSI ensemble otherwise. Confidence stays MODEST —
        # short-horizon crypto direction is near-efficient, so we never claim a big edge.
        drift = ind.get("drift_per_sec")
        if vps and end_ts and drift is not None:
            tau = float(end_ts) - now
            if tau > 0:
                p_up = directional_fair_value(drift, vps, tau,
                                              max_dev=self.directional_max_dev)
                if p_up is not None:
                    data_ok = min(1.0, ind["n"] / max(1, self.min_samples * 4))
                    sharp = abs(p_up - 0.5) / max(1e-9, self.directional_max_dev)
                    # cap directional confidence below the strike model's (momentum is weak)
                    conf = max(0.0, min(0.7, 0.5 * data_ok + 0.5 * sharp * data_ok))
                    return BtcSignal(p_up=p_up, confidence=conf, kind="directional_drift",
                                     components={"drift_per_sec": round(drift, 10),
                                                 "vol_per_sec": round(vps, 8),
                                                 "tau_s": round(tau, 1)})
        p_up, agreement, comps = self._directional_p_up(ind)
        data_ok = min(1.0, ind["n"] / max(1, self.min_samples * 4))
        sharp = abs(p_up - 0.5) / max(1e-9, self.directional_max_dev)   # 0..1 of max dev
        conf = max(0.0, min(0.7, 0.5 * data_ok * agreement + 0.5 * sharp * agreement))
        return BtcSignal(p_up=p_up, confidence=conf, kind="directional", components=comps)

    def status(self) -> dict:
        return {"observations": self.observations, "buffered": len(self._buf),
                "ready": self.ready, "indicators": self.indicators() if self.ready else {}}


def coinbase_spot_fetcher(symbol: str, *, timeout_s: float = 4.0):
    """Build a READ-ONLY Coinbase spot-price fetcher for ``symbol`` (e.g. 'BTC-USD').
    Returns a callable ``() -> float | None``; never raises, never trades."""
    url = _COINBASE_SPOT.format(sym=symbol)
    box: dict = {}

    def _client():
        c = box.get("c")
        if c is None:
            import httpx
            c = httpx.Client(timeout=timeout_s, headers={"User-Agent": "hermes-btc-sampler/1.0"})
            box["c"] = c
        return c

    def _fetch() -> Optional[float]:
        try:
            r = _client().get(url)
            if r.status_code != 200:
                return None
            amt = (((r.json() or {}).get("data") or {}).get("amount"))
            p = float(amt)
            return p if p > 0 else None
        except Exception:  # noqa: BLE001 — a price fetch never raises into the loop
            return None
    return _fetch


class CryptoPriceSampler:
    """Background daemon that samples BTC/ETH spot every ``interval_s`` and feeds the per-asset
    :class:`BtcSignalEngine`s — DECOUPLED from the heavy ~3-min training tick so the signal
    warms up in minutes and has real intraday granularity. PAPER/RESEARCH ONLY: read-only
    public price reads; never trades, sizes, or places an order; never raises into the loop."""

    def __init__(self, engines: dict, *, interval_s: float = 12.0,
                 fetchers: Optional[dict] = None):
        self.engines = dict(engines or {})
        self.interval_s = max(2.0, float(interval_s))
        self._fetchers = dict(fetchers or {})
        for asset in self.engines:
            if asset not in self._fetchers and asset in _ASSET_SYMBOLS:
                self._fetchers[asset] = coinbase_spot_fetcher(_ASSET_SYMBOLS[asset])
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.samples = {a: 0 for a in self.engines}
        self.errors = {a: 0 for a in self.engines}

    def sample_once(self, now: Optional[float] = None) -> dict:
        """One sampling pass over all assets (used by the loop + directly in tests)."""
        now = float(now if now is not None else time.time())
        got = {}
        for asset, eng in self.engines.items():
            fetch = self._fetchers.get(asset)
            if fetch is None:
                continue
            try:
                px = fetch()
            except Exception:  # noqa: BLE001
                px = None
            if px is not None and px > 0:
                eng.observe(px, now=now)
                self.samples[asset] += 1
                got[asset] = px
            else:
                self.errors[asset] += 1
        return got

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sample_once()
            except Exception:  # noqa: BLE001 — never let the sampler thread die silently
                logger.debug("crypto price sampler pass failed", exc_info=True)
            self._stop.wait(self.interval_s)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="crypto-price-sampler",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict:
        return {"interval_s": self.interval_s, "running": bool(
            self._thread is not None and self._thread.is_alive()),
            "samples": dict(self.samples), "errors": dict(self.errors)}

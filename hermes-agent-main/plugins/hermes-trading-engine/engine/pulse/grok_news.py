"""Periodic BTC news/sentiment digest for CEX-lead and context gates (observe-only)."""

from __future__ import annotations

import threading
import time
from typing import Optional

from engine.pulse.grok_intel import GrokBudget, _grok_responses, _parse_json


def _clamp01(v, default: Optional[float] = None) -> Optional[float]:
    try:
        x = float(v)
        return max(0.0, min(1.0, x))
    except (TypeError, ValueError):
        return default


def make_news_fn(*, model: str = "grok-4.3", timeout_s: float = 35.0, responses=_grok_responses):
    """Build ``news_fn() -> digest|None`` via xAI web/X search (periodic, budget-gated)."""
    box: dict = {}
    tools = [{"type": "web_search"}, {"type": "x_search"}]

    def _news() -> Optional[dict]:
        prompt = (
            "Search the latest web + X for BREAKING Bitcoin news and sentiment in the last ~30 "
            "minutes that could move BTC over the NEXT 5 MINUTES (macro prints, ETF flows, "
            "exchange/regulatory headlines, large liquidations, prominent X posts). Summarize for a "
            "short-horizon trader. Reply with STRICT JSON only: {\"sentiment\":\"bullish|bearish|"
            "neutral\",\"confidence\":<0-1>,\"headlines\":[\"...\"],\"event_risk\":\"low|medium|"
            "high\"}.")
        d = _parse_json(responses(prompt, model=model, timeout_s=timeout_s, box=box, tools=tools))
        if not d:
            return None
        return {"sentiment": str(d.get("sentiment", "neutral"))[:20],
                "confidence": _clamp01(d.get("confidence"), 0.0),
                "headlines": [str(x)[:200] for x in (d.get("headlines") or [])][:6],
                "event_risk": str(d.get("event_risk", "low"))[:12]}
    return _news


class GrokNewsDigest:
    """Periodic BTC news digest — cached context for CEX-lead; does not decide trades."""

    def __init__(self, *, news_fn=None, budget: Optional[GrokBudget] = None,
                 interval_s: float = 300.0, max_age_s: float = 600.0,
                 model: str = "grok-4.3", timeout_s: float = 35.0):
        self._fn = news_fn if news_fn is not None else make_news_fn(model=model, timeout_s=timeout_s)
        self._budget = budget
        self.interval_s = max(60.0, float(interval_s))
        self.max_age_s = float(max_age_s)
        self._lock = threading.Lock()
        self._digest: Optional[dict] = None
        self._ts = 0.0
        self.calls = 0
        self.errors = 0
        self.skipped_budget = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def refresh(self) -> Optional[dict]:
        if self._budget is not None and not self._budget.try_spend("news"):
            self.skipped_budget += 1
            return None
        d = None
        try:
            d = self._fn()
        except Exception:  # noqa: BLE001
            d = None
        if d is None:
            self.errors += 1
        else:
            self.calls += 1
            with self._lock:
                self._digest, self._ts = d, time.time()
        return d

    def latest(self) -> Optional[dict]:
        with self._lock:
            if not self._digest or (time.time() - self._ts) > self.max_age_s:
                return None
            return {**self._digest, "age_s": round(time.time() - self._ts, 1)}

    def _worker(self) -> None:
        self._stop.wait(min(self.interval_s, 15.0))
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(self.interval_s)

    def start(self) -> "GrokNewsDigest":
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._worker, name="grok-news-digest",
                                            daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def report(self) -> dict:
        with self._lock:
            return {"enabled": True, "interval_s": self.interval_s, "calls": self.calls,
                    "errors": self.errors, "skipped_budget": self.skipped_budget,
                    "latest": (dict(self._digest) if self._digest else None),
                    "age_s": (round(time.time() - self._ts, 1) if self._digest else None)}

    def to_state(self) -> dict:
        with self._lock:
            return {"calls": self.calls, "errors": self.errors,
                    "skipped_budget": self.skipped_budget, "digest": self._digest, "ts": self._ts}

    def load_state(self, data: dict) -> None:
        if not data:
            return
        with self._lock:
            self.calls = int(data.get("calls", 0) or 0)
            self.errors = int(data.get("errors", 0) or 0)
            self.skipped_budget = int(data.get("skipped_budget", 0) or 0)
            self._digest = data.get("digest")
            self._ts = float(data.get("ts", 0.0) or 0.0)
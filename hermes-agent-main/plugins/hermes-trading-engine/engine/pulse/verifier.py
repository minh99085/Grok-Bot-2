"""#1 Maker-checker VERIFIER (independent model) for the BTC pulse loop (PAPER ONLY).

The agent that proposes a trade is the worst judge of whether it's real edge. This is an INDEPENDENT
verifier — a different model (Claude) with different instructions and no exposure to how the maker
(Grok) reasoned — that reviews each proposed paper trade and returns APPROVE / VETO + an optional
size cap. It can ONLY veto or shrink a trade; it can never create, force, or enlarge one. Runs on a
background worker, fail-open (no key / error / timeout -> approve, recorded), budget-gated.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Optional

from engine.pulse.grok_intel import _parse_json, GrokBudget
from engine.pulse.claude_client import claude_chat, anthropic_key


def normalize_verdict(d) -> Optional[dict]:
    if not isinstance(d, dict):
        return None
    raw = d.get("approve")
    if isinstance(raw, str):
        approve = raw.strip().lower() in ("true", "yes", "approve", "1", "ok")
    else:
        approve = bool(raw)
    try:
        msf = max(0.0, min(1.0, float(d.get("max_size_fraction", 1.0))))
    except (TypeError, ValueError):
        msf = 1.0
    try:
        conf = max(0.0, min(1.0, float(d.get("confidence", 0.5))))
    except (TypeError, ValueError):
        conf = 0.5
    return {"approve": approve, "max_size_fraction": round(msf, 4), "confidence": round(conf, 4),
            "reason": str(d.get("reason") or "")[:400]}


def make_verifier_fn(*, model: Optional[str] = None, timeout_s: float = 20.0, chat=claude_chat):
    box: dict = {}
    system = ("You are an INDEPENDENT risk verifier (maker-checker) for a PAPER BTC 5-minute "
              "up/down prediction-market bot. A SEPARATE model proposed a trade; you did not see its "
              "reasoning. Your only job is to APPROVE or VETO and optionally cap size. Veto when: the "
              "payoff/breakeven is poor, the entry context is proven-losing or matches a LESSON to "
              "avoid, the directional view is weak/uncalibrated, or risk is elevated. You can ONLY "
              "veto or shrink — never enlarge or force a trade. Be skeptical; when unsure, veto.")

    def _verify(payload: dict) -> Optional[dict]:
        prompt = ("Review this proposed PAPER trade and respond with STRICT JSON ONLY: "
                  "{\"approve\":true|false,\"max_size_fraction\":<0-1>,\"confidence\":<0-1>,"
                  "\"reason\":\"<short>\"}.\nPROPOSAL+CONTEXT: " + json.dumps(payload, default=str)[:8000])
        return normalize_verdict(_parse_json(chat(prompt, model=model, timeout_s=timeout_s,
                                                  box=box, system=system, max_tokens=512)))
    return _verify


class ClaudeVerifier:
    """Independent maker-checker. ``request`` a verdict per decision, read it fail-open at act time."""

    def __init__(self, *, verify_fn=None, budget: Optional[GrokBudget] = None, enabled: bool = True,
                 fail_open: bool = True, max_pending: int = 200, max_results: int = 5000):
        self._fn = verify_fn if verify_fn is not None else make_verifier_fn()
        self._budget = budget
        self.enabled = bool(enabled)
        self.fail_open = bool(fail_open)
        self._lock = threading.Lock()
        self._queue: deque = deque(maxlen=int(max_pending))
        self._results: dict = {}
        self._order: deque = deque(maxlen=int(max_results))
        self._seen: set = set()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.requested = 0
        self.verified = 0
        self.approvals = 0
        self.vetoes = 0
        self.errors = 0
        self.skipped_budget = 0
        self.latency_sum = 0.0
        # outcome tracking: did the verifier's APPROVE / VETO calls help?
        self.approved_settled = {"n": 0, "wins": 0, "pnl": 0.0}
        self.vetoed_would_have = {"n": 0, "wins": 0, "pnl": 0.0}   # graded counterfactually

    def request(self, decision_id: str, payload: dict) -> None:
        if not decision_id or not self.enabled:
            return
        with self._lock:
            if decision_id in self._seen:
                return
            self._seen.add(decision_id)
            self._queue.append((decision_id, payload))
            self.requested += 1

    def get(self, decision_id: str) -> Optional[dict]:
        with self._lock:
            r = self._results.get(decision_id)
            return dict(r) if r else None

    def verdict_or_failopen(self, decision_id: str) -> dict:
        """Verdict to act on: the stored verdict, else fail-open APPROVE (or VETO if fail-closed)."""
        v = self.get(decision_id)
        if v is not None:
            return v
        return {"approve": bool(self.fail_open), "max_size_fraction": 1.0, "confidence": 0.0,
                "reason": ("fail_open_no_verdict" if self.fail_open else "fail_closed_no_verdict"),
                "pending": True}

    def _process_one(self) -> bool:
        with self._lock:
            if not self._queue:
                return False
            decision_id, payload = self._queue.popleft()
        if self._budget is not None and not self._budget.try_spend("verifier"):
            with self._lock:
                self.skipped_budget += 1
            return True
        t0 = time.time()
        verdict = None
        try:
            verdict = self._fn(payload)
        except Exception:  # noqa: BLE001
            verdict = None
        with self._lock:
            if verdict is None:
                self.errors += 1
            else:
                verdict["ts"] = time.time()
                verdict["latency_s"] = round(time.time() - t0, 3)
                self.verified += 1
                self.latency_sum += (time.time() - t0)
                self.approvals += int(bool(verdict.get("approve")))
                self.vetoes += int(not verdict.get("approve"))
                self._results[decision_id] = verdict
                self._order.append(decision_id)
                if len(self._results) > self._order.maxlen:
                    self._results.pop(self._order.popleft(), None)
        return True

    def grade(self, decision_id: str, *, won: bool, pnl: float, acted: bool) -> None:
        """Grade a verdict vs the realized window: approved-and-acted trades feed approved_settled;
        vetoed setups are graded counterfactually (would the vetoed trade have won?)."""
        with self._lock:
            v = self._results.get(decision_id)
            if not v:
                return
            bucket = self.approved_settled if (v.get("approve") and acted) else self.vetoed_would_have
            bucket["n"] += 1
            bucket["wins"] += int(bool(won))
            bucket["pnl"] = round(bucket["pnl"] + float(pnl or 0.0), 6)

    def _worker(self) -> None:
        while not self._stop.is_set():
            worked = False
            try:
                worked = self._process_one()
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(0.2 if worked else 1.0)

    def start(self) -> "ClaudeVerifier":
        if self.enabled and (self._thread is None or not self._thread.is_alive()):
            self._stop.clear()
            self._thread = threading.Thread(target=self._worker, name="claude-verifier", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def report(self) -> dict:
        with self._lock:
            avg_lat = round(self.latency_sum / self.verified, 3) if self.verified else None

            def wr(b):
                return {"n": b["n"], "win_rate": (round(b["wins"] / b["n"], 4) if b["n"] else None),
                        "pnl_usd": round(b["pnl"], 4)}
            return {"enabled": self.enabled, "model": "claude", "maker_checker": True,
                    "can_force_trade": False, "fail_open": self.fail_open, "paper_only": True,
                    "requested": self.requested, "verified": self.verified,
                    "approvals": self.approvals, "vetoes": self.vetoes, "errors": self.errors,
                    "skipped_budget": self.skipped_budget, "pending": len(self._queue),
                    "avg_latency_s": avg_lat,
                    "approve_rate": (round(self.approvals / self.verified, 4) if self.verified else None),
                    "approved_acted_settled": wr(self.approved_settled),
                    "vetoed_would_have_settled": wr(self.vetoed_would_have),
                    "note": ("independent Claude maker-checker; can only veto/shrink a Grok-proposed "
                             "paper trade, never force one; fail-open; PAPER ONLY.")}

    def to_state(self) -> dict:
        with self._lock:
            return {"requested": self.requested, "verified": self.verified,
                    "approvals": self.approvals, "vetoes": self.vetoes, "errors": self.errors,
                    "skipped_budget": self.skipped_budget, "latency_sum": round(self.latency_sum, 3),
                    "approved_settled": dict(self.approved_settled),
                    "vetoed_would_have": dict(self.vetoed_would_have)}

    def load_state(self, data: dict) -> None:
        if not data:
            return
        with self._lock:
            self.requested = int(data.get("requested", 0) or 0)
            self.verified = int(data.get("verified", 0) or 0)
            self.approvals = int(data.get("approvals", 0) or 0)
            self.vetoes = int(data.get("vetoes", 0) or 0)
            self.errors = int(data.get("errors", 0) or 0)
            self.skipped_budget = int(data.get("skipped_budget", 0) or 0)
            self.latency_sum = float(data.get("latency_sum", 0.0) or 0.0)
            for k, src in (("approved_settled", "approved_settled"),
                           ("vetoed_would_have", "vetoed_would_have")):
                s = data.get(src) or {}
                getattr(self, k).update({"n": int(s.get("n", 0) or 0), "wins": int(s.get("wins", 0) or 0),
                                         "pnl": float(s.get("pnl", 0.0) or 0.0)})

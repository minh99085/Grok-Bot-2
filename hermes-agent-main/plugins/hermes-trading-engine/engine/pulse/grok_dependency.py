"""Grok advisory dependency screener (Bible DeepSeek pattern).

Grok proposes candidate constraints from market titles; deterministic LCMM code validates before
any paper trade. Grok never authorizes execution. PAPER ONLY.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from engine.pulse.dependency_arb import DependencyViolation, validate_violation


_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}|\[[\s\S]*\]")


def parse_grok_dependency_response(raw: str) -> list[dict]:
    """Extract structured dependency proposals from Grok JSON (fail-open → [])."""
    if not raw or not str(raw).strip():
        return []
    text = str(raw).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("proposals") or data.get("dependencies") or [data]
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict)]
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        if isinstance(data, dict):
            data = data.get("proposals") or data.get("dependencies") or [data]
        return [p for p in (data or []) if isinstance(p, dict)]
    except json.JSONDecodeError:
        return []


def proposal_to_violation(proposal: dict, *, windows_by_id: dict) -> Optional[DependencyViolation]:
    """Convert one Grok proposal into a DependencyViolation if windows exist."""
    ctype = str(proposal.get("constraint_type") or proposal.get("type") or "")
    if ctype not in ("nested_implication",):
        return None
    pid = str(proposal.get("parent_window_key") or proposal.get("parent_id") or "")
    cids = proposal.get("child_window_keys") or proposal.get("child_ids") or []
    if not pid or not cids:
        return None
    parent = windows_by_id.get(pid)
    child = windows_by_id.get(str(cids[0]))
    if parent is None or child is None:
        return None
    p_mid = getattr(getattr(parent, "up_book", None), "mid", None)
    c_mid = getattr(getattr(child, "up_book", None), "mid", None)
    if p_mid is None or c_mid is None:
        return None
    mag = float(c_mid) - float(p_mid)
    return DependencyViolation(
        constraint_type="nested_implication",
        parent_window_key=pid,
        child_window_keys=[str(cids[0])],
        description=str(proposal.get("description") or "grok_proposed_nested_implication"),
        parent_up_mid=round(float(p_mid), 6),
        child_up_mids=[round(float(c_mid), 6)],
        implied_bound=round(float(c_mid), 6),
        violation_magnitude=round(mag, 6),
        actionable=False,
        reason="grok_proposal_unvalidated",
    )


def validate_grok_proposals(
    proposals: list[dict],
    *,
    windows_by_id: dict,
) -> dict:
    """Validate Grok proposals deterministically; return accepted/rejected lists."""
    accepted, rejected = [], []
    for p in proposals or []:
        v = proposal_to_violation(p, windows_by_id=windows_by_id)
        if v is None:
            rejected.append({"proposal": p, "reason": "unmapped_or_unsupported"})
            continue
        ok, reason = validate_violation(v)
        if ok:
            accepted.append(v.to_dict())
        else:
            rejected.append({"proposal": p, "reason": reason, "violation": v.to_dict()})
    return {
        "dependency_proposals": len(proposals or []),
        "deterministic_validated_dependencies": len(accepted),
        "rejected_dependencies": rejected,
        "accepted_dependencies": accepted,
    }


GROK_DEPENDENCY_PROMPT = """You are a Polymarket dependency screener (ADVISORY ONLY).
Given BTC/ETH up/down window titles and ids, propose ONLY machine-checkable linear constraints.
Output JSON: {"proposals": [{"constraint_type": "nested_implication", "parent_window_key": "...",
"child_window_keys": ["..."], "description": "..."}]}
Rules: nested_implication only when a shorter window is logically nested inside a longer window.
Do NOT propose trades. Do NOT invent window ids not in the input list."""


def _build_dependency_prompt(windows: list) -> str:
    rows = []
    for w in windows or []:
        eid = str(getattr(w, "event_id", "") or "")
        if not eid:
            continue
        rows.append({
            "event_id": eid,
            "title": str(getattr(w, "title", "") or "")[:120],
            "series_label": str(getattr(w, "series_label", "") or ""),
            "window_seconds": int(getattr(w, "window_seconds", 0) or 0),
            "open_ts": float(getattr(w, "open_ts", 0) or 0),
            "close_ts": float(getattr(w, "close_ts", 0) or 0),
        })
    if not rows:
        return ""
    import json as _json
    return GROK_DEPENDENCY_PROMPT + "\n\nWindows:\n" + _json.dumps(rows, indent=1)


def make_dependency_screen_fn(*, model: str = "grok-4.3", timeout_s: float = 20.0):
    """Build a callable ``(windows) -> list[dict]`` for the dependency screener."""
    from engine.pulse.grok_intel import _grok_chat
    box: dict = {}

    def _screen(windows: list) -> list:
        prompt = _build_dependency_prompt(windows)
        if not prompt:
            return []
        raw = _grok_chat(prompt, model=model, timeout_s=timeout_s, box=box)
        return parse_grok_dependency_response(raw)
    return _screen


class GrokDependencyScreener:
    """Periodic Grok dependency proposal worker (ADVISORY ONLY — never authorizes trades)."""

    def __init__(self, *, windows_fn, screen_fn=None, budget=None, interval_s: float = 180.0,
                 max_age_s: float = 600.0):
        self._windows_fn = windows_fn
        self._fn = screen_fn if screen_fn is not None else make_dependency_screen_fn()
        self._budget = budget
        self.interval_s = max(60.0, float(interval_s))
        self.max_age_s = float(max_age_s)
        self._lock = __import__("threading").Lock()
        self._proposals: list = []
        self._ts = 0.0
        self.calls = 0
        self.errors = 0
        self.skipped_budget = 0
        self._stop = __import__("threading").Event()
        self._thread = None

    def refresh(self) -> list:
        if self._budget is not None and not self._budget.try_spend("dependency"):
            self.skipped_budget += 1
            return []
        windows = []
        try:
            windows = list(self._windows_fn() or [])
        except Exception:  # noqa: BLE001
            windows = []
        props = []
        try:
            props = list(self._fn(windows) or [])
        except Exception:  # noqa: BLE001
            props = []
        if not props:
            self.errors += 1
        else:
            self.calls += 1
            with self._lock:
                self._proposals, self._ts = props, __import__("time").time()
        return props

    def latest_proposals(self) -> list:
        with self._lock:
            if not self._proposals or (__import__("time").time() - self._ts) > self.max_age_s:
                return []
            return list(self._proposals)

    def _worker(self) -> None:
        self._stop.wait(min(self.interval_s, 15.0))
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(self.interval_s)

    def start(self) -> "GrokDependencyScreener":
        import threading
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._worker, name="grok-dependency-screener", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def report(self) -> dict:
        with self._lock:
            age = round(__import__("time").time() - self._ts, 1) if self._ts else None
            n = len(self._proposals)
        return {
            "enabled": True, "observe_only": True, "affects_trading": False,
            "calls": self.calls, "errors": self.errors, "skipped_budget": self.skipped_budget,
            "proposals_cached": n, "age_s": age, "interval_s": self.interval_s,
        }
"""#3 Loop registry + LoopAgent base — formalize the bot's sub-loops (PAPER ONLY).

Loop engineering says every working loop has: an automation (trigger/cadence), a skill, a state, a
verifier, and a verifiable stop-condition. The bot already runs several sub-loops as background
workers; this registry makes them FIRST-CLASS and uniformly observable: each loop declares its
trigger, cadence, skill reference, and a live status provider. ``LoopRegistry.report()`` then gives
one consolidated view of every loop for the dashboard / full report.
"""

from __future__ import annotations

from typing import Callable, Optional


class LoopRegistry:
    """Lightweight registry of the system's sub-loops for uniform observability."""

    def __init__(self):
        self._loops: dict = {}     # name -> metadata + status provider

    def register(self, name: str, *, role: str, trigger: str, interval_s: Optional[float] = None,
                 skill: Optional[str] = None, verifier: Optional[str] = None,
                 stop_condition: Optional[str] = None,
                 status_fn: Optional[Callable[[], dict]] = None) -> None:
        self._loops[name] = {"role": role, "trigger": trigger, "interval_s": interval_s,
                             "skill": skill, "verifier": verifier, "stop_condition": stop_condition,
                             "status_fn": status_fn}

    def names(self) -> list:
        return list(self._loops.keys())

    def report(self) -> dict:
        out = {}
        for name, m in self._loops.items():
            entry = {"role": m["role"], "trigger": m["trigger"], "interval_s": m["interval_s"],
                     "skill": m["skill"], "verifier": m["verifier"],
                     "stop_condition": m["stop_condition"]}
            fn = m.get("status_fn")
            if fn is not None:
                try:
                    st = fn() or {}
                    # keep it compact: pull a few common health fields if present
                    entry["status"] = {k: st.get(k) for k in
                                       ("enabled", "mode", "calls", "decided", "verified", "errors",
                                        "requested", "tripped") if k in st} or {"reported": True}
                except Exception:  # noqa: BLE001 — status never breaks the report
                    entry["status"] = {"error": True}
            out[name] = entry
        return {"loops": out, "count": len(out),
                "note": ("formalized sub-loops (data/signal/verify/execute/risk/research/news/"
                         "lessons); each has a trigger + skill + verifier + verifiable stop. "
                         "PAPER ONLY.")}

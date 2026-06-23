"""#2 Compounding LESSONS book for the BTC pulse self-improving loop (PAPER ONLY).

Every notable event (a bucket proven losing, a context becoming a real edge, a breaker trip, a large
single loss) appends a deduped, timestamped LESSON -> RULE. Lessons survive restarts, are fed back
into the maker (Grok) + checker (Claude) prompts each cycle, and are written to a human-readable
LESSONS.md. This is the mechanism that turns losses into rules so the system compounds knowledge.
"""

from __future__ import annotations

import time
from typing import Optional


class LessonsBook:
    def __init__(self, *, max_lessons: int = 300):
        self.max_lessons = int(max_lessons)
        self.lessons: list = []          # [{ts, kind, key, rule}]
        self._keys: set = set()          # dedupe by (kind,key)

    def add(self, *, kind: str, key: str, rule: str, ts: Optional[float] = None) -> bool:
        """Append a lesson if its (kind,key) hasn't been recorded. Returns True if added."""
        k = (str(kind), str(key))
        if k in self._keys:
            return False
        self._keys.add(k)
        self.lessons.append({"ts": round(float(ts if ts is not None else time.time()), 1),
                             "kind": str(kind), "key": str(key), "rule": str(rule)[:300]})
        if len(self.lessons) > self.max_lessons:
            drop = self.lessons.pop(0)
            self._keys.discard((drop.get("kind"), drop.get("key")))
        return True

    def recent(self, n: int = 12) -> list:
        return self.lessons[-int(n):]

    def report(self) -> dict:
        return {"count": len(self.lessons), "recent": self.recent(12)}

    def to_markdown(self) -> str:
        out = ["# Hermes BTC Pulse — LESSONS (auto-generated, compounding)\n",
               "_Every loss/regime event becomes a rule the maker + checker read each cycle. "
               "PAPER ONLY._\n"]
        for ln in reversed(self.lessons[-100:]):
            import datetime
            t = datetime.datetime.fromtimestamp(ln["ts"], datetime.UTC).strftime("%Y-%m-%d %H:%M")
            out.append("- **%s** [`%s`]: %s" % (t, ln["kind"], ln["rule"]))
        return "\n".join(out) + "\n"

    def to_state(self) -> dict:
        return {"lessons": list(self.lessons)}

    def load_state(self, data: dict) -> None:
        if not data:
            return
        self.lessons = list(data.get("lessons") or [])[-self.max_lessons:]
        self._keys = {(l.get("kind"), l.get("key")) for l in self.lessons}

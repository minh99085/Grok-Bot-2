"""TradingView 1m+5m MTF conflict gate (restrict-only, PAPER ONLY).

When both Binance BTCUSDT 1m and 5m alerts are fresh but disagree, block the paper trade.
``confirmed_up`` / ``confirmed_down`` / ``single_tf`` / ``none`` always pass — only
``conflict`` is blocked (soft gate: never requires confirmation to trade).
"""

from __future__ import annotations

import random
from typing import Optional


class TradingViewMtfConflictGate:
    """Restrict-only gate. ``evaluate`` returns ``{decision, reasons}``."""

    def __init__(self, *, enabled: bool = True, exploration_rate: float = 0.02,
                 seed: Optional[int] = None):
        self.enabled = bool(enabled)
        self.exploration_rate = max(0.0, min(0.05, float(exploration_rate)))
        self.passed = 0
        self.blocked = 0
        self.explored = 0
        self.block_reasons: dict = {}
        self.explore_reasons: dict = {}
        self._rng = random.Random(seed)

    def violations(self, *, tf_confirm=None) -> list[str]:
        if str(tf_confirm or "").strip().lower() == "conflict":
            return ["tv_mtf_1m_5m_conflict"]
        return []

    def evaluate(self, *, tf_confirm=None) -> dict:
        if not self.enabled:
            return {"decision": "pass", "reasons": [], "active": False}
        reasons = self.violations(tf_confirm=tf_confirm)
        if not reasons:
            self.passed += 1
            return {"decision": "pass", "reasons": [], "active": True}
        if self.exploration_rate > 0 and self._rng.random() < self.exploration_rate:
            self.explored += 1
            for r in reasons:
                self.explore_reasons[r] = self.explore_reasons.get(r, 0) + 1
            return {"decision": "explore", "reasons": reasons, "active": True}
        self.blocked += 1
        for r in reasons:
            self.block_reasons[r] = self.block_reasons.get(r, 0) + 1
        return {"decision": "block", "reasons": reasons, "active": True}

    def report(self) -> dict:
        return {
            "enabled": self.enabled,
            "mode": "restrict_only_mtf_conflict",
            "affects_trading": self.enabled,
            "can_force_trade": False,
            "execution_gate_still_authoritative": True,
            "blocks": ["conflict"],
            "passes": ["confirmed_up", "confirmed_down", "single_tf", "none"],
            "exploration_rate": self.exploration_rate,
            "passed": self.passed,
            "blocked": self.blocked,
            "explored": self.explored,
            "block_reasons": dict(self.block_reasons),
            "explore_reasons": dict(self.explore_reasons),
            "note": ("blocks only when fresh 1m and 5m TradingView signals disagree; "
                     "never requires MTF agreement to trade. Restrict-only."),
        }

    def to_state(self) -> dict:
        return {"passed": self.passed, "blocked": self.blocked, "explored": self.explored,
                "block_reasons": dict(self.block_reasons),
                "explore_reasons": dict(self.explore_reasons)}

    def load_state(self, data: dict) -> None:
        if not data:
            return
        self.passed = int(data.get("passed", 0) or 0)
        self.blocked = int(data.get("blocked", 0) or 0)
        self.explored = int(data.get("explored", 0) or 0)
        self.block_reasons = {k: int(v or 0) for k, v in (data.get("block_reasons") or {}).items()}
        self.explore_reasons = {k: int(v or 0)
                                for k, v in (data.get("explore_reasons") or {}).items()}
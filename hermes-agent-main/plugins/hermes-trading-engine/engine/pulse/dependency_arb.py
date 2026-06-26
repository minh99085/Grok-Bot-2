"""Cross-window dependency arbitrage (LCMM layer, log-only by default).

Detects logical price inconsistencies between nested BTC up/down windows (5m inside 15m)
using executable VWAP/mid prices. Bregman/Frank-Wolfe belongs here for multi-leg groups;
this module ships Layer-1 linear constraints first (subset/implication, complete-set).

PAPER ONLY — default mode is detect/log; no trades until explicitly enabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DependencyViolation:
    """A detected LCMM constraint violation (may or may not be executable)."""
    constraint_type: str
    parent_window_key: str
    child_window_keys: list
    description: str
    parent_up_mid: Optional[float] = None
    child_up_mids: list = field(default_factory=list)
    implied_bound: Optional[float] = None
    violation_magnitude: float = 0.0
    actionable: bool = False
    reason: str = "log_only"

    def to_dict(self) -> dict:
        return {"constraint_type": self.constraint_type,
                "parent_window_key": self.parent_window_key,
                "child_window_keys": list(self.child_window_keys),
                "description": self.description,
                "parent_up_mid": self.parent_up_mid,
                "child_up_mids": list(self.child_up_mids),
                "implied_bound": self.implied_bound,
                "violation_magnitude": round(self.violation_magnitude, 6),
                "actionable": self.actionable, "reason": self.reason}


def _up_mid(window) -> Optional[float]:
    book = getattr(window, "up_book", None)
    if book is None:
        return None
    return getattr(book, "mid", None)


def group_nested_windows(windows: list) -> list:
    """Group 5m windows whose open_ts falls inside a 15m parent's [open, close)."""
    parents = [w for w in windows if int(getattr(w, "window_seconds", 0) or 0) >= 900]
    children = [w for w in windows if int(getattr(w, "window_seconds", 0) or 0) < 900]
    groups = []
    for p in parents:
        nested = [c for c in children
                  if float(p.open_ts) <= float(c.open_ts) < float(p.close_ts)]
        if nested:
            groups.append((p, sorted(nested, key=lambda x: x.open_ts)))
    return groups


def scan_nested_implication(parent, children: list, *, epsilon: float = 0.02) -> list:
    """LCMM: P(up over 15m) >= max P(up over constituent 5m windows) on mids.

    If parent up-mid is materially below a child up-mid, prices are inconsistent
    (the longer window cannot be less likely up than a sub-window fully inside it).
    """
    out = []
    p_mid = _up_mid(parent)
    if p_mid is None:
        return out
    for c in children:
        c_mid = _up_mid(c)
        if c_mid is None:
            continue
        if float(c_mid) > float(p_mid) + float(epsilon):
            out.append(DependencyViolation(
                constraint_type="nested_implication",
                parent_window_key=str(parent.event_id),
                child_window_keys=[str(c.event_id)],
                description=("15m up-mid below nested 5m up-mid: "
                             "P(up_15m) cannot be < P(up_5m) for overlapping window"),
                parent_up_mid=round(float(p_mid), 6),
                child_up_mids=[round(float(c_mid), 6)],
                implied_bound=round(float(c_mid), 6),
                violation_magnitude=round(float(c_mid) - float(p_mid), 6),
                actionable=False,
                reason="log_only",
            ))
    return out


def scan_windows(windows: list, *, epsilon: float = 0.02) -> list:
    """Run all LCMM dependency scans; returns violations (log-only)."""
    violations = []
    for parent, children in group_nested_windows(windows):
        violations.extend(scan_nested_implication(parent, children, epsilon=epsilon))
    return violations


class DependencyArbLedger:
    """Separate ledger for dependency-arb (never blended with dutch-book or directional)."""

    def __init__(self):
        self.scans = 0
        self.violations_detected = 0
        self.executed = 0
        self.realized_profit_usd = 0.0
        self.last_violations: list = []

    def record_scan(self, violations: list) -> None:
        self.scans += 1
        self.last_violations = [v.to_dict() if hasattr(v, "to_dict") else dict(v)
                              for v in (violations or [])]
        self.violations_detected += len(self.last_violations)

    def report(self) -> dict:
        return {"strategy": "dependency_arbitrage", "paper_only": True, "enabled": False,
                "mode": "log_only", "scans": self.scans,
                "violations_detected": self.violations_detected,
                "executed": self.executed, "realized_profit_usd": round(self.realized_profit_usd, 4),
                "last_violations": self.last_violations[-20:],
                "segregated_from_directional": True,
                "note": "LCMM nested-window scanner; Bregman/IP gated for later phases."}

    def to_state(self) -> dict:
        return {"scans": self.scans, "violations_detected": self.violations_detected,
                "executed": self.executed, "realized_profit_usd": self.realized_profit_usd,
                "last_violations": self.last_violations}

    def load_state(self, data: dict) -> None:
        if not data:
            return
        self.scans = int(data.get("scans", 0) or 0)
        self.violations_detected = int(data.get("violations_detected", 0) or 0)
        self.executed = int(data.get("executed", 0) or 0)
        self.realized_profit_usd = float(data.get("realized_profit_usd", 0.0) or 0.0)
        self.last_violations = list(data.get("last_violations") or [])
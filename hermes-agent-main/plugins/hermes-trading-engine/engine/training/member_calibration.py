"""Per-member calibration for ensemble stacking (PAPER ONLY; advisory-only).

Generalizes the Grok calibration idea (engine.training.grok_calibration) to the OTHER
ensemble members — the statistical ``model`` and the ``market`` (mid) — so each source
earns its ensemble weight from its OWN measured accuracy (rolling Brier of its
directional probability vs realized outcomes). The research/Grok member keeps its own
tracker (GrokCalibration); this covers model + market.

Pure + deterministic; persists to a small JSON so weights survive restarts. Never
places, sizes, or gates a trade — it only sets how much each member moves p_raw.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Optional

UNINFORMATIVE_BRIER = 0.25          # Brier of always predicting 0.5


def _clamp01(x) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


class MemberCalibration:
    """Rolling Brier per ensemble member -> a clamped calibration weight."""

    def __init__(self, path: Optional[str] = None, *,
                 members=("model", "market"), window: int = 200,
                 min_samples: int = 20, weight_min: float = 0.05,
                 weight_default: float = 1.0, enabled: bool = True):
        self.path = Path(path) if path else None
        self.members = tuple(members)
        self.window = max(10, int(window))
        self.min_samples = max(1, int(min_samples))
        self.weight_min = _clamp01(weight_min)
        self.weight_default = _clamp01(weight_default)
        self.enabled = bool(enabled)
        self._rec: dict = {m: deque(maxlen=self.window) for m in self.members}
        self._load()

    @staticmethod
    def directional_prob(p_yes: float, side: str) -> float:
        p = _clamp01(p_yes)
        return p if str(side or "YES").upper() == "YES" else (1.0 - p)

    # -- recording ------------------------------------------------------ #
    def record(self, member: str, *, predicted_prob: float, won: bool) -> None:
        if member not in self._rec:
            self._rec[member] = deque(maxlen=self.window)
        self._rec[member].append({"p": _clamp01(predicted_prob), "won": 1 if won else 0})
        self._save()

    def record_position(self, member: str, *, p_yes: float, side: str, won: bool) -> None:
        self.record(member, predicted_prob=self.directional_prob(p_yes, side), won=won)

    # -- metrics -------------------------------------------------------- #
    @staticmethod
    def _brier(recs: list) -> Optional[float]:
        if not recs:
            return None
        return round(sum((r["p"] - r["won"]) ** 2 for r in recs) / len(recs), 6)

    def sample_count(self, member: str) -> int:
        return len(self._rec.get(member, ()))

    def brier(self, member: str) -> Optional[float]:
        return self._brier(list(self._rec.get(member, ())))

    def weight(self, member: str, category=None) -> float:
        """Calibration weight in [weight_min, 1.0]; ``weight_default`` until min_samples."""
        if not self.enabled:
            return 1.0
        recs = list(self._rec.get(member, ()))
        if len(recs) < self.min_samples:
            return round(self.weight_default, 4)
        b = self._brier(recs)
        if b is None:
            return round(self.weight_default, 4)
        skill = _clamp01((UNINFORMATIVE_BRIER - b) / UNINFORMATIVE_BRIER)
        return round(self.weight_min + (1.0 - self.weight_min) * skill, 4)

    def metrics(self) -> dict:
        out = {"enabled": self.enabled, "min_samples": self.min_samples,
               "weight_min": self.weight_min, "members": {}}
        for m in self._rec:
            out["members"][m] = {"samples": self.sample_count(m),
                                 "brier": self.brier(m), "weight": self.weight(m),
                                 "measured": self.sample_count(m) >= self.min_samples}
        return out

    # -- persistence ---------------------------------------------------- #
    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for m, recs in (data.get("members", {}) or {}).items():
                dq = deque(maxlen=self.window)
                for r in (recs or [])[-self.window:]:
                    dq.append({"p": _clamp01(r.get("p", 0.5)), "won": 1 if r.get("won") else 0})
                self._rec[m] = dq
        except Exception:  # noqa: BLE001 — calibration must never break startup
            pass

    def _save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"members": {m: list(dq) for m, dq in self._rec.items()}}
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:  # noqa: BLE001 — persistence must never break a close
            pass

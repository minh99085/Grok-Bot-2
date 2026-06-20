"""Window settlement + model calibration for the BTC 5-min pulse (PAPER).

Resolution truth, in priority order:
1. the AUTHORITATIVE Polymarket resolution (Gamma ``outcomePrices`` pinned to 0/1 once the
   market settles on the Chainlink Data Stream) — this is what a real position would pay;
2. fallback PROXY: our own ``s_close >= s_open`` on the same Coinbase feed (used only to
   resolve paper P&L promptly when Gamma hasn't published yet; reconciled later).

Calibration scores the digital model's entry probability against realized outcomes (Brier /
log-loss) so we learn whether the fair value is trustworthy before sizing up.
"""

from __future__ import annotations

import math
from typing import Optional


class PulseCalibration:
    """Brier / log-loss of the model's P(up) vs realized Up outcomes."""

    def __init__(self):
        self._sq = 0.0
        self._ll = 0.0
        self.n = 0
        self.up_outcomes = 0

    def observe(self, p_up_pred: float, outcome_up: bool) -> None:
        p = max(1e-6, min(1.0 - 1e-6, float(p_up_pred)))
        y = 1.0 if outcome_up else 0.0
        self._sq += (p - y) ** 2
        self._ll += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        self.n += 1
        self.up_outcomes += int(bool(outcome_up))

    @property
    def brier(self) -> Optional[float]:
        return round(self._sq / self.n, 6) if self.n else None

    @property
    def log_loss(self) -> Optional[float]:
        return round(self._ll / self.n, 6) if self.n else None

    @property
    def base_rate_up(self) -> Optional[float]:
        return round(self.up_outcomes / self.n, 4) if self.n else None

    def to_dict(self) -> dict:
        return {"samples": self.n, "brier": self.brier, "log_loss": self.log_loss,
                "base_rate_up": self.base_rate_up,
                "baseline_brier_0_5": 0.25}


def resolve_outcome(market_id: str, *, gamma_feed=None, s_open: Optional[float] = None,
                    s_close: Optional[float] = None,
                    allow_proxy: bool = True) -> "tuple[Optional[bool], str]":
    """Return ``(outcome_up, source)``. Prefers the authoritative Polymarket resolution;
    falls back to the Coinbase ``s_close >= s_open`` proxy only when ``allow_proxy``.
    ``outcome_up`` is None if not yet resolvable."""
    if gamma_feed is not None and market_id:
        try:
            res = gamma_feed.fetch_resolution(market_id)
        except Exception:  # noqa: BLE001
            res = None
        if res is not None:
            return bool(res), "polymarket"
    if allow_proxy and s_open is not None and s_close is not None:
        return (s_close >= s_open), "proxy_coinbase"
    return None, "unresolved"

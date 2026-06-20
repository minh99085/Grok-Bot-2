"""Loosened decision model for the BTC 5-min pulse (PAPER ONLY).

Given the digital fair value ``P(up)`` and the live Up/Down books, pick the side with the
larger positive after-cost edge and decide whether to take a PAPER position. The quality
gates here are intentionally LOOSE (small min-edge, shallow depth) per the operator
directive — they only affect which *paper* trades are taken; nothing here can place a real
order. The HARD safety limits that remain: never trade a closed window, never trade without
a live ask, never trade after the open snapshot is missing/late, never pay above a price cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PulseDecision:
    trade: bool
    side: Optional[str] = None          # "up" | "down"
    token_id: Optional[str] = None
    price: Optional[float] = None       # marketable ask we'd pay (paper)
    fair_p_up: Optional[float] = None
    edge: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return {"trade": self.trade, "side": self.side, "price": self.price,
                "fair_p_up": (round(self.fair_p_up, 4) if self.fair_p_up is not None else None),
                "edge": round(self.edge, 4), "reason": self.reason}


def decide(window, fair_p_up: Optional[float], now: float, *,
           min_edge: float = 0.03, min_seconds_to_close: float = 4.0,
           min_depth_usd: float = 1.0, edge_buffer: float = 0.01,
           max_price: float = 0.97) -> PulseDecision:
    """Return the (loosened) PAPER trade decision for ``window`` at time ``now``."""
    if fair_p_up is None:
        return PulseDecision(False, reason="no_fair_value")
    ttc = window.seconds_to_close(now)
    if ttc <= min_seconds_to_close:
        return PulseDecision(False, fair_p_up=fair_p_up, reason="too_close_to_settlement")
    up_b, dn_b = window.up_book, window.down_book
    up_ask = up_b.best_ask if up_b else None
    dn_ask = dn_b.best_ask if dn_b else None
    up_depth = up_b.ask_depth_usd if up_b else 0.0
    dn_depth = dn_b.ask_depth_usd if dn_b else 0.0
    # after-cost edge for each side: P(outcome) - ask_paid - buffer (basis-drift/open-lag)
    cand = []
    if up_ask is not None and up_ask <= max_price and up_depth >= min_depth_usd:
        cand.append(("up", window.up_token_id, float(up_ask),
                     fair_p_up - float(up_ask) - edge_buffer))
    if dn_ask is not None and dn_ask <= max_price and dn_depth >= min_depth_usd:
        cand.append(("down", window.down_token_id, float(dn_ask),
                     (1.0 - fair_p_up) - float(dn_ask) - edge_buffer))
    if not cand:
        return PulseDecision(False, fair_p_up=fair_p_up, reason="no_tradeable_ask")
    side, token, price, edge = max(cand, key=lambda c: c[3])
    if edge < min_edge:
        return PulseDecision(False, side=side, token_id=token, price=price,
                             fair_p_up=fair_p_up, edge=edge, reason="edge_below_min")
    return PulseDecision(True, side=side, token_id=token, price=price,
                         fair_p_up=fair_p_up, edge=edge, reason="trade")

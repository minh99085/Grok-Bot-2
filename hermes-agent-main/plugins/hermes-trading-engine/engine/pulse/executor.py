"""Paper executor + ledger for BTC 5-min pulse positions.

HARD SAFETY INVARIANT: every fill here is SIMULATED. This module holds NO order client,
NO wallet, NO signing — it can only record hypothetical positions and resolve them for
paper P&L. There is intentionally no code path that contacts an exchange to place an order.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

PAPER_ONLY = True          # structural assertion: this engine never places a real order


@dataclass
class PulsePosition:
    window_key: str
    market_id: str
    title: str
    side: str                       # "up" | "down"
    token_id: str
    entry_price: float
    size_usd: float
    shares: float
    fair_at_entry: float
    edge_at_entry: float
    open_ts: float
    close_ts: float
    entry_ts: float
    status: str = "open"            # "open" | "settled"
    outcome_up: Optional[bool] = None
    won: Optional[bool] = None
    pnl_usd: Optional[float] = None
    s_open: Optional[float] = None
    s_close: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in (
            "window_key", "market_id", "title", "side", "token_id", "entry_price",
            "size_usd", "shares", "fair_at_entry", "edge_at_entry", "open_ts", "close_ts",
            "entry_ts", "status", "outcome_up", "won", "pnl_usd", "s_open", "s_close")}


class PulseLedger:
    """In-memory paper ledger (persisted as JSON by the engine). One position per window."""

    def __init__(self):
        self.positions: dict = {}            # window_key -> PulsePosition
        self.realized_pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0
        self.settled: int = 0

    def has_position(self, window_key: str) -> bool:
        return window_key in self.positions

    def open_position(self, window, decision, now: float, *, size_usd: float,
                      s_open: Optional[float] = None) -> Optional[PulsePosition]:
        """Record a SIMULATED paper fill at the decision's marketable ask. Never real."""
        if not decision.trade or decision.token_id is None or not decision.price:
            return None
        if self.has_position(window.event_id):
            return None
        price = float(decision.price)
        if price <= 0 or price >= 1:
            return None
        shares = round(float(size_usd) / price, 6)
        pos = PulsePosition(
            window_key=window.event_id, market_id=window.market_id, title=window.title,
            side=decision.side, token_id=decision.token_id, entry_price=price,
            size_usd=float(size_usd), shares=shares,
            fair_at_entry=float(decision.fair_p_up or 0.0),
            edge_at_entry=float(decision.edge), open_ts=window.open_ts,
            close_ts=window.close_ts, entry_ts=float(now), s_open=s_open)
        self.positions[window.event_id] = pos
        self.trades += 1
        return pos

    def settle(self, window_key: str, outcome_up: bool, *,
               s_open: Optional[float] = None, s_close: Optional[float] = None) -> Optional[PulsePosition]:
        pos = self.positions.get(window_key)
        if pos is None or pos.status == "settled":
            return None
        won = (pos.side == "up" and outcome_up) or (pos.side == "down" and not outcome_up)
        payoff = pos.shares if won else 0.0
        pos.pnl_usd = round(payoff - pos.size_usd, 6)
        pos.won = bool(won)
        pos.outcome_up = bool(outcome_up)
        pos.status = "settled"
        if s_open is not None:
            pos.s_open = s_open
        if s_close is not None:
            pos.s_close = s_close
        self.realized_pnl = round(self.realized_pnl + pos.pnl_usd, 6)
        self.settled += 1
        if won:
            self.wins += 1
        return pos

    def open_positions(self) -> list:
        return [p for p in self.positions.values() if p.status == "open"]

    def stats(self) -> dict:
        win_rate = (self.wins / self.settled) if self.settled else None
        return {"trades": self.trades, "settled": self.settled, "wins": self.wins,
                "win_rate": (round(win_rate, 4) if win_rate is not None else None),
                "realized_pnl_usd": round(self.realized_pnl, 4),
                "open_positions": len(self.open_positions())}

    def to_dict(self, *, max_positions: int = 200) -> dict:
        recent = sorted(self.positions.values(), key=lambda p: p.entry_ts, reverse=True)
        return {"paper_only": True, "stats": self.stats(),
                "positions": [p.to_dict() for p in recent[:max_positions]]}

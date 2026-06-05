"""After-cost execution-simulation fill model (PAPER ONLY, pure, deterministic).

Models a marketable order against a replayed order book so paper PnL reflects
what the live venue could actually have done:

* **order-book depth** walking (best level first),
* **partial fills** when depth is insufficient,
* **latency** (order arrives ``latency_ms`` after the decision),
* **stale-book rejection** (refuse to fill against a book older than the budget),
* **fees** (taker bps + per-share), and
* **Bregman multi-leg execution feasibility** (all-or-nothing: an arbitrage is
  only executable if EVERY leg fully fills against fresh depth).

No network, no Grok, no live orders — this is the simulation mirror of CLOB v2
execution realism.

Quant responsibilities
----------------------
* **Quant researcher** — sets latency/freshness/fee assumptions; validates them
  against observed live fills.
* **Quant developer** — owns this pure model + the rejection contract (tested).
* **Backtesting / robustness** — uses after-cost, depth-aware, latency-aware
  fills so paper metrics are not optimistic.
* **Trader / CLOB v2 execution** — the live path must honor the same depth,
  latency and staleness limits; multi-leg arbs are placed all-or-nothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from engine.fill_realism import walk_book

logger = logging.getLogger("hte.simulation.fill_model")


def _f(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


@dataclass
class BookLevel:
    price: float
    size: float


@dataclass
class OrderBook:
    """A replayed order-book snapshot. ``ts_ms`` is when it was captured."""

    ts_ms: int = 0
    bids: list = field(default_factory=list)   # BookLevel, descending price
    asks: list = field(default_factory=list)   # BookLevel, ascending price

    def best_ask(self) -> Optional[float]:
        return _f(self.asks[0].price) if self.asks else None

    def best_bid(self) -> Optional[float]:
        return _f(self.bids[0].price) if self.bids else None

    def _levels(self, side: str) -> list:
        book = self.asks if side == "buy" else self.bids
        return [(_f(l.price), _f(l.size)) for l in book]


@dataclass
class LatencyModel:
    """Order latency + book-freshness budget (ms)."""

    latency_ms: int = 250
    max_book_age_ms: int = 2000


@dataclass
class ReplayFeeModel:
    taker_fee_bps: float = 60.0
    per_share_fee: float = 0.0

    def fee(self, notional: float, shares: float) -> float:
        return notional * (self.taker_fee_bps / 10_000.0) + self.per_share_fee * shares


@dataclass
class FillOutcome:
    """Result of simulating one order fill against a replayed book."""

    side: str
    requested: float
    filled: float
    avg_price: float
    fees: float
    notional: float
    slippage_frac: float
    book_age_ms: int
    partial: bool
    rejected: bool
    reason: str = ""

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def simulate_fill(*, side: str, size: float, book: OrderBook, decision_ts_ms: int,
                  fee_model: Optional[ReplayFeeModel] = None,
                  latency: Optional[LatencyModel] = None) -> FillOutcome:
    """Simulate a marketable ``side`` order for ``size`` shares against ``book``.

    The order arrives ``latency.latency_ms`` after ``decision_ts_ms``; if the book
    is older than ``latency.max_book_age_ms`` at arrival it is rejected
    (``reason="stale_book"``). Otherwise it walks displayed depth (partial fill
    when depth is short) and charges fees. Deterministic + pure.
    """
    fee_model = fee_model or ReplayFeeModel()
    latency = latency or LatencyModel()
    s = side if side in ("buy", "sell") else "buy"
    req = max(0.0, _f(size))

    arrival = int(decision_ts_ms) + int(latency.latency_ms)
    age = max(0, arrival - int(book.ts_ms))
    if age > int(latency.max_book_age_ms):
        return FillOutcome(s, req, 0.0, 0.0, 0.0, 0.0, 0.0, age, False, True,
                           reason=f"stale_book(age={age}ms>{latency.max_book_age_ms}ms)")

    levels = book._levels(s)
    best = (levels[0][0] if levels else 0.0)
    if req <= 0 or not levels or best <= 0:
        return FillOutcome(s, req, 0.0, 0.0, 0.0, 0.0, 0.0, age, False, True,
                           reason="no_liquidity" if best <= 0 else "non_positive_size")

    filled, avg = walk_book(req, levels)
    notional = round(avg * filled, 10)
    fees = round(fee_model.fee(notional, filled), 10)
    if s == "buy":
        slip = (avg - best) / best if best > 0 else 0.0
    else:
        slip = (best - avg) / best if best > 0 else 0.0
    partial = filled + 1e-12 < req
    outcome = FillOutcome(
        side=s, requested=round(req, 10), filled=filled, avg_price=avg,
        fees=fees, notional=notional, slippage_frac=round(max(0.0, slip), 8),
        book_age_ms=age, partial=partial, rejected=False,
        reason="partial_fill" if partial else "filled")
    if partial:
        logger.debug("partial fill: %s req=%.2f filled=%.2f", s, req, filled)
    return outcome


@dataclass
class LegSpec:
    """One leg of a Bregman multi-leg arbitrage (buy ``size`` shares)."""

    id: str
    book: OrderBook
    side: str = "buy"
    size: float = 1.0


@dataclass
class MultiLegFill:
    """All-or-nothing feasibility of a multi-leg arbitrage execution."""

    feasible: bool
    legs: list
    total_cost: float
    total_fees: float
    worst_case_payoff: float
    after_cost_edge: float
    reason: str = ""

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["legs"] = [l.to_dict() for l in self.legs]
        return d


def simulate_bregman_execution(legs: Sequence[LegSpec], *, decision_ts_ms: int,
                               sets: float = 1.0, worst_case_payoff_per_set: float = 1.0,
                               fee_model: Optional[ReplayFeeModel] = None,
                               latency: Optional[LatencyModel] = None) -> MultiLegFill:
    """Simulate executing a Bregman arbitrage **all-or-nothing**.

    Each leg must FULLY fill ``sets`` shares against fresh depth; if any leg is
    stale, illiquid, or only partially fillable, the whole arbitrage is infeasible
    (you cannot hold a half-hedged "risk-free" position). When feasible, the
    after-cost edge is ``worst_case_payoff - total_cost - total_fees`` for the
    requested ``sets``. Pure + deterministic.
    """
    fee_model = fee_model or ReplayFeeModel()
    latency = latency or LatencyModel()
    n_sets = max(0.0, _f(sets))
    outcomes: list[FillOutcome] = []
    feasible = n_sets > 0 and len(legs) > 0
    reason = "feasible" if feasible else ("no_sets" if n_sets <= 0 else "no_legs")
    total_cost = 0.0
    total_fees = 0.0
    for leg in legs:
        oc = simulate_fill(side=leg.side, size=n_sets, book=leg.book,
                           decision_ts_ms=decision_ts_ms, fee_model=fee_model,
                           latency=latency)
        outcomes.append(oc)
        total_cost += oc.notional
        total_fees += oc.fees
        if oc.rejected or oc.partial or oc.filled + 1e-12 < n_sets:
            feasible = False
            if reason == "feasible":
                reason = f"leg_{leg.id}_{oc.reason}"
    worst_case_payoff = round(worst_case_payoff_per_set * n_sets, 10) if feasible else 0.0
    after_cost_edge = round(worst_case_payoff - total_cost - total_fees, 10) if feasible else 0.0
    result = MultiLegFill(
        feasible=bool(feasible), legs=outcomes, total_cost=round(total_cost, 10),
        total_fees=round(total_fees, 10), worst_case_payoff=worst_case_payoff,
        after_cost_edge=after_cost_edge, reason=reason)
    logger.info("bregman execution feasible=%s legs=%d sets=%.2f after_cost_edge=%.4f reason=%s",
                result.feasible, len(legs), n_sets, result.after_cost_edge, reason)
    return result

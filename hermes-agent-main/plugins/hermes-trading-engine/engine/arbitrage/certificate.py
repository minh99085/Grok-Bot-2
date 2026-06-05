"""Cost/depth-aware arbitrage certification (PAPER ONLY, pure, deterministic).

Given a group of outcomes with an *exactly-one-true* relationship (complement /
MECE / range, or a cross-market pair reduced to such), the canonical coherence
arbitrage is to BUY one share of each leg: in every feasible world state exactly
one share pays $1, so the worst-case payoff is $1 per "set". The set is profitable
iff ``1 - sum(ask) - fees > 0``.

This module certifies that with a **worst-case (min over feasible atoms)** check
of a constructed, depth-bounded portfolio — a sound certificate equivalent to the
LP that maximizes the guaranteed (worst-case) after-fee profit subject to depth.
A non-certified group is never tradeable ("no certified proof means no trade").

Soundness: the certificate's ``after_fee_profit_per_set`` is the *minimum* profit
over ALL enumerated feasible states, so a positive value guarantees nonnegative
(indeed positive) payoff in every admissible resolution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from .constraint_graph import Constraint, ConstraintGraph, Outcome

logger = logging.getLogger("hte.arbitrage.certificate")


@dataclass
class FeeModel:
    """Conservative taker fee model (paper). Fees only ever *reduce* certified
    profit, so the certificate stays sound."""

    taker_fee_bps: float = 0.0     # bps on traded notional (sum of buy prices)
    per_share_fee: float = 0.0     # flat fee per share bought

    def set_fee(self, buy_prices: Sequence[float]) -> float:
        notional = sum(float(p) for p in buy_prices)
        return notional * (self.taker_fee_bps / 10_000.0) + self.per_share_fee * len(buy_prices)


@dataclass
class Certificate:
    """A deterministic worst-case arbitrage certificate."""

    certified: bool
    relation: str
    outcome_ids: list[str]
    worst_case_payoff_per_set: float = 0.0
    cost_per_set: float = 0.0
    fee_per_set: float = 0.0
    after_fee_profit_per_set: float = 0.0
    size: float = 0.0                       # certifiable set count (depth-bounded)
    total_after_fee_profit: float = 0.0
    portfolio: dict = field(default_factory=dict)   # outcome_id -> shares to BUY
    atoms_checked: int = 0
    fill_feasible: bool = False
    deterministic: bool = True
    reason: str = ""

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        return d


def _worst_case_payoff(portfolio: Mapping[str, float],
                       atoms: Sequence[Mapping[str, int]]) -> float:
    """Minimum gross payoff of a long portfolio over feasible world states."""
    worst = None
    for atom in atoms:
        payoff = sum(qty * float(atom.get(oid, 0)) for oid, qty in portfolio.items())
        worst = payoff if worst is None else min(worst, payoff)
    return float(worst if worst is not None else 0.0)


def certify_group(graph: ConstraintGraph, constraint: Constraint, *,
                  fee_model: Optional[FeeModel] = None, profit_floor: float = 0.005,
                  max_size: float = 1e9) -> Certificate:
    """Certify (or reject) a buy-set arbitrage for one constraint.

    ``profit_floor`` is the minimum required after-fee profit per set. ``max_size``
    caps the certified set count; the depth-feasible size is the min ask depth
    across legs. Deterministic + sound (worst-case over feasible atoms).
    """
    fee_model = fee_model or FeeModel()
    ids = list(constraint.outcome_ids)
    outcomes: list[Outcome] = [graph.get(i) for i in ids]  # type: ignore[misc]
    if any(o is None for o in outcomes):
        return Certificate(False, constraint.type.value, ids, reason="missing_outcome")

    atoms = graph.feasible_atoms(constraint)
    if not atoms:
        return Certificate(False, constraint.type.value, ids,
                           reason="no_enumerable_atoms")

    buy_prices = [o.buy_price() for o in outcomes]
    portfolio = {o.id: 1.0 for o in outcomes}        # buy one share of each leg
    worst_payoff = _worst_case_payoff(portfolio, atoms)
    cost = sum(buy_prices)
    fee = fee_model.set_fee(buy_prices)
    profit_per_set = worst_payoff - cost - fee

    # depth-feasible size = min ask depth across legs (shares), capped.
    depth = min((float(o.ask_depth) for o in outcomes), default=0.0)
    size = max(0.0, min(depth, float(max_size)))
    certified = profit_per_set > profit_floor and size > 0
    fill_feasible = size > 0

    cert = Certificate(
        certified=bool(certified), relation=constraint.type.value, outcome_ids=ids,
        worst_case_payoff_per_set=round(worst_payoff, 6),
        cost_per_set=round(cost, 6), fee_per_set=round(fee, 6),
        after_fee_profit_per_set=round(profit_per_set, 6),
        size=round(size, 6),
        total_after_fee_profit=round(profit_per_set * size, 6) if certified else 0.0,
        portfolio=portfolio, atoms_checked=len(atoms), fill_feasible=fill_feasible,
        reason="certified" if certified else (
            "no_depth" if (profit_per_set > profit_floor and size <= 0)
            else "no_positive_worst_case_profit"))
    if cert.certified:
        logger.info("bregman certificate: %s legs=%s profit/set=%.4f size=%.2f total=%.4f",
                    cert.relation, ids, cert.after_fee_profit_per_set, cert.size,
                    cert.total_after_fee_profit)
    else:
        logger.debug("bregman not certified: %s legs=%s reason=%s profit/set=%.4f",
                     cert.relation, ids, cert.reason, cert.after_fee_profit_per_set)
    return cert

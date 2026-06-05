"""Bregman coherence arbitrage strategy (PRIMARY strategy, PAPER ONLY, pure).

Pipeline:

1. Compile the :class:`ConstraintGraph` to projection primitives.
2. KL/Bregman-project the market-implied probabilities onto the coherent set.
3. Flag groups whose local incoherence exceeds a threshold (candidates).
4. Certify each candidate with a cost/depth-aware worst-case certificate.
5. Emit ONLY certified, fill-feasible opportunities as tradeable. A candidate
   that is incoherent but fails certification is a *false positive*.

Tracks: candidates, certified count, certified profit, false positives, fill
feasibility, and opportunity decay (edge decays with age). Calibrated
probabilities (from the modeling layer) may *rank* opportunities, but a trade
requires the deterministic certificate ("no certified proof means no trade").

Quant responsibilities
----------------------
* **Quant analyst** — curates the constraint universe / relationships.
* **Quant researcher** — sets incoherence/edge thresholds, validates certificates.
* **Quant developer** — owns this module + graph/projection/certificate code.
* **Trader** — executes only ``tradeable()`` (certified + fill-feasible) output;
  monitors opportunity decay; never trades an uncertified candidate.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from ..arbitrage.bregman_projection import (ProjectionResult, bregman_project,
                                            incoherence, local_incoherence)
from ..arbitrage.certificate import Certificate, FeeModel, certify_group
from ..arbitrage.constraint_graph import Constraint, ConstraintGraph

logger = logging.getLogger("hte.strategies.bregman")


@dataclass
class BregmanOpportunity:
    """A candidate coherence-arbitrage opportunity (certified or not)."""

    relation: str
    outcome_ids: list[str]
    local_incoherence: float
    certificate: Certificate
    created_ts: float
    edge: float = 0.0           # after-fee profit per set (0 if not certified)

    @property
    def tradeable(self) -> bool:
        """Tradeable iff certified AND fill-feasible (no cert => no trade)."""
        return bool(self.certificate.certified) and bool(self.certificate.fill_feasible)

    def decayed_edge(self, now: Optional[float] = None, half_life_s: float = 300.0) -> float:
        """Edge decayed by age (opportunity decay): edge * 0.5**(age/half_life)."""
        if half_life_s <= 0:
            return self.edge
        now = time.time() if now is None else now
        age = max(0.0, now - self.created_ts)
        return round(self.edge * (0.5 ** (age / half_life_s)), 8)

    def to_dict(self) -> dict:
        return {"relation": self.relation, "outcome_ids": self.outcome_ids,
                "local_incoherence": self.local_incoherence, "edge": self.edge,
                "tradeable": self.tradeable, "certificate": self.certificate.to_dict(),
                "created_ts": self.created_ts}


@dataclass
class BregmanResult:
    candidates: int
    certified: int
    certified_profit: float
    false_positives: int
    fill_feasible: int
    opportunities: list = field(default_factory=list)
    projection: Optional[ProjectionResult] = None
    incoherence: dict = field(default_factory=dict)

    def tradeable(self) -> list:
        """Certified + fill-feasible opportunities only."""
        return [o for o in self.opportunities if o.tradeable]

    def to_dict(self) -> dict:
        return {
            "candidates": self.candidates, "certified": self.certified,
            "certified_profit": self.certified_profit,
            "false_positives": self.false_positives,
            "fill_feasible": self.fill_feasible,
            "incoherence": dict(self.incoherence),
            "projection": self.projection.to_dict() if self.projection else None,
            "opportunities": [o.to_dict() for o in self.opportunities],
        }


class BregmanStrategy:
    """Primary coherence-arbitrage strategy (pure planner)."""

    def __init__(self, *, fee_model: Optional[FeeModel] = None,
                 profit_floor: float = 0.005, max_size: float = 1e9,
                 incoherence_tol: float = 1e-3, decay_half_life_s: float = 300.0):
        self.fee_model = fee_model or FeeModel()
        self.profit_floor = float(profit_floor)
        self.max_size = float(max_size)
        self.incoherence_tol = float(incoherence_tol)
        self.decay_half_life_s = float(decay_half_life_s)

    def evaluate(self, graph: ConstraintGraph, *, now: Optional[float] = None) -> BregmanResult:
        """Run project -> detect -> certify and return the result with metrics."""
        now = time.time() if now is None else now
        issues = graph.validate()
        if issues:
            logger.warning("constraint graph issues: %s", issues)

        prims = graph.to_primitives()
        x_market = graph.price_vector()
        proj = bregman_project(x_market, prims)
        incoh = incoherence(x_market, proj.x)

        opportunities: list[BregmanOpportunity] = []
        candidates = certified = false_positives = fill_feasible = 0
        certified_profit = 0.0

        # Evaluate ALL constraints: certify_group returns not-certified (with a
        # reason) for non-buy-set-arb structures, so incoherent-but-uncertifiable
        # groups (e.g. an overpriced mutually-exclusive set) are counted as
        # false positives rather than silently ignored.
        for c in graph.constraints():
            local = local_incoherence(x_market, proj.x, c.outcome_ids)
            cert = certify_group(graph, c, fee_model=self.fee_model,
                                 profit_floor=self.profit_floor, max_size=self.max_size)
            is_candidate = local > self.incoherence_tol or cert.certified
            opp = BregmanOpportunity(
                relation=c.type.value, outcome_ids=list(c.outcome_ids),
                local_incoherence=local, certificate=cert, created_ts=now,
                edge=cert.after_fee_profit_per_set if cert.certified else 0.0)
            opportunities.append(opp)
            if is_candidate:
                candidates += 1
            if cert.certified:
                certified += 1
                certified_profit += cert.total_after_fee_profit
                if cert.fill_feasible:
                    fill_feasible += 1
            elif local > self.incoherence_tol:
                # Looked mispriced but no executable certificate => false positive.
                false_positives += 1

        result = BregmanResult(
            candidates=candidates, certified=certified,
            certified_profit=round(certified_profit, 6),
            false_positives=false_positives, fill_feasible=fill_feasible,
            opportunities=opportunities, projection=proj, incoherence=incoh)
        logger.info("bregman eval: candidates=%d certified=%d profit=%.4f "
                    "false_positives=%d fill_feasible=%d max_violation=%.4g",
                    candidates, certified, result.certified_profit,
                    false_positives, fill_feasible, proj.max_violation)
        return result

    def tradeable(self, result: BregmanResult, *, now: Optional[float] = None,
                  min_decayed_edge: float = 0.0) -> list:
        """Return certified + fill-feasible opportunities whose decayed edge still
        clears ``min_decayed_edge``. Enforces 'no certified proof => no trade'."""
        out = []
        for o in result.tradeable():
            if o.decayed_edge(now=now, half_life_s=self.decay_half_life_s) >= min_decayed_edge:
                out.append(o)
        return out

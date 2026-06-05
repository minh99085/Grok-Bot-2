"""Bregman arbitrage candidate generation (PAPER ONLY, pure, deterministic).

Bridges the projection math and the certificate: for every constraint group it
converts executable market prices into implied probabilities, KL-projects them
onto the coherent set, measures the **incoherence residual**, and emits a typed
:class:`CandidateBundle` only when the residual exceeds the fee/spread/slippage
friction (otherwise it records a reject reason — no false candidates).

Telemetry per group: projection residual, divergence (KL) score, implied edge,
gross candidate profit, after-cost candidate profit, a confidence band, and the
reject reason. Candidate ranking is deterministic.

Quant responsibilities
----------------------
* **Acquisition / preprocessing** — executable quotes (ask/bid/depth) come from
  discovery; this module never performs I/O.
* **Statistical / probabilistic modeling** — implied probabilities + the
  confidence band quantify mispricing uncertainty.
* **Bregman signal development** — KL projection + residual localize incoherence;
  candidates are generated only past the cost friction.
* **Risk / portfolio** — after-cost profit + band feed sizing/veto; never a buy
  without a certified worst-case proof.
* **Backtesting / robustness / monitoring** — telemetry is deterministic + audited.
* **CLOB v2 execution** — depth-bounded size + spread feed executable planning.
* **Compliance / security / ops** — PAPER-only; no wallet/order path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .bregman_projection import bregman_project, kl_divergence, local_incoherence
from .certificate import Certificate, FeeModel, certify_group
from .constraint_graph import EXACTLY_ONE_RELATIONS, Constraint, ConstraintGraph

logger = logging.getLogger("hte.arbitrage.candidate")

# Typed reject reasons (why a group did NOT become a tradeable candidate).
REJECT_NOT_BUY_SET = "not_buy_set_arb"
REJECT_RESIDUAL_BELOW_THRESHOLD = "residual_below_threshold"
REJECT_NO_POSITIVE_EDGE = "no_positive_edge"
REJECT_INSUFFICIENT_DEPTH = "insufficient_executable_depth"
REJECT_EDGE_BELOW_COSTS = "edge_below_costs"
REJECT_MALFORMED = "malformed_group"

REJECT_REASONS = frozenset({
    REJECT_NOT_BUY_SET, REJECT_RESIDUAL_BELOW_THRESHOLD, REJECT_NO_POSITIVE_EDGE,
    REJECT_INSUFFICIENT_DEPTH, REJECT_EDGE_BELOW_COSTS, REJECT_MALFORMED,
})


@dataclass
class CandidateBundle:
    """A constraint group's arbitrage candidate + full telemetry."""

    group_id: str
    relation: str
    outcome_ids: list
    projection_residual: float
    divergence_score: float
    implied_edge: float
    gross_candidate_profit: float
    after_cost_candidate_profit: float
    confidence_band: tuple
    size: float
    certified: bool
    reject_reason: Optional[str] = None
    certificate: Optional[Certificate] = field(default=None, repr=False)

    @property
    def is_candidate(self) -> bool:
        """A real tradeable candidate iff there is no reject reason."""
        return self.reject_reason is None

    def _sort_key(self) -> tuple:
        # deterministic: real candidates first, then by after-cost profit, residual,
        # implied edge, and finally group_id for a total order.
        return (0 if self.is_candidate else 1,
                -round(self.after_cost_candidate_profit, 10),
                -round(self.projection_residual, 10),
                -round(self.implied_edge, 10), self.group_id)

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id, "relation": self.relation,
            "outcome_ids": list(self.outcome_ids),
            "projection_residual": self.projection_residual,
            "divergence_score": self.divergence_score,
            "implied_edge": self.implied_edge,
            "gross_candidate_profit": self.gross_candidate_profit,
            "after_cost_candidate_profit": self.after_cost_candidate_profit,
            "confidence_band": list(self.confidence_band),
            "size": self.size, "certified": self.certified,
            "reject_reason": self.reject_reason,
            "is_candidate": self.is_candidate,
        }


def _half_spread_per_set(graph: ConstraintGraph, ids: Sequence[str]) -> float:
    """Sum of per-leg half-spreads (executable friction per set)."""
    total = 0.0
    for oid in ids:
        o = graph.get(oid)
        if o is None:
            continue
        ask = float(o.ask if o.ask is not None else o.price)
        bid = float(o.bid if o.bid is not None else o.price)
        if ask > 0 and bid > 0 and ask >= bid:
            total += (ask - bid) / 2.0
    return total


def _group_kl(x_market: dict, x_proj: dict, ids: Sequence[str]) -> float:
    sub_m = {i: x_market[i] for i in ids if i in x_market and i in x_proj}
    sub_p = {i: x_proj[i] for i in ids if i in x_market and i in x_proj}
    return kl_divergence(sub_m, sub_p)


def generate_candidates(graph: ConstraintGraph, *, fee_model: Optional[FeeModel] = None,
                        slippage_bps: float = 0.0, profit_floor: float = 0.005,
                        max_size: float = 1e9,
                        residual_threshold: Optional[float] = None) -> list:
    """Generate per-group candidate bundles with telemetry (pure, deterministic).

    Projects the market price vector onto the coherent set once, then for each
    constraint group measures the residual + divergence, certifies a depth-aware
    worst-case profit, and emits a :class:`CandidateBundle`. A bundle is a real
    candidate only when its relation is buy-set-certifiable, the residual exceeds
    the fee/spread/slippage friction, the implied edge is positive, depth is
    sufficient, and the after-cost profit clears ``profit_floor``. Otherwise a
    typed ``reject_reason`` is recorded. Ranking is deterministic.
    """
    fee_model = fee_model or FeeModel()
    prims = graph.to_primitives()
    x_market = graph.price_vector()
    proj = bregman_project(x_market, prims)
    bundles: list[CandidateBundle] = []

    for c in graph.constraints():
        try:
            bundles.append(_candidate_for_group(
                graph, c, proj.x, x_market, fee_model=fee_model,
                slippage_bps=slippage_bps, profit_floor=profit_floor,
                max_size=max_size, residual_threshold=residual_threshold))
        except Exception as exc:  # noqa: BLE001 — a malformed group must never crash the scan
            logger.debug("candidate generation failed for %s: %s", c.type.value, exc)
            bundles.append(CandidateBundle(
                group_id=_group_id(c), relation=c.type.value,
                outcome_ids=list(c.outcome_ids), projection_residual=0.0,
                divergence_score=0.0, implied_edge=0.0, gross_candidate_profit=0.0,
                after_cost_candidate_profit=0.0, confidence_band=(0.0, 0.0),
                size=0.0, certified=False, reject_reason=REJECT_MALFORMED))

    bundles.sort(key=lambda b: b._sort_key())
    n_cand = sum(1 for b in bundles if b.is_candidate)
    logger.info("candidate generation: groups=%d candidates=%d", len(bundles), n_cand)
    return bundles


def _group_id(c: Constraint) -> str:
    o = list(c.outcome_ids)
    return o[0].split(":")[0] if o else c.type.value


def _candidate_for_group(graph: ConstraintGraph, c: Constraint, x_proj: dict,
                         x_market: dict, *, fee_model: FeeModel, slippage_bps: float,
                         profit_floor: float, max_size: float,
                         residual_threshold: Optional[float]) -> CandidateBundle:
    ids = list(c.outcome_ids)
    residual = local_incoherence(x_market, x_proj, ids)
    divergence = _group_kl(x_market, x_proj, ids)
    cert = certify_group(graph, c, fee_model=fee_model, profit_floor=profit_floor,
                         max_size=max_size)
    cost_per_set = float(cert.cost_per_set)
    payoff = float(cert.worst_case_payoff_per_set)
    implied_edge = round(payoff - cost_per_set, 8)          # gross, pre-friction
    half_spread = _half_spread_per_set(graph, ids)
    slippage = (slippage_bps / 10_000.0) * cost_per_set
    friction_per_set = round(float(cert.fee_per_set) + half_spread + slippage, 8)
    size = float(cert.size)
    after_cost_per_set = round(implied_edge - friction_per_set, 8)
    gross = round(max(0.0, implied_edge) * size, 8)
    after_cost = round(after_cost_per_set * size, 8)
    unc = round(half_spread * max(size, 0.0), 8)            # spread-driven uncertainty
    from engine.models.probability_ensemble import coherence_confidence_band
    band = coherence_confidence_band(after_cost, unc)

    thr = friction_per_set if residual_threshold is None else float(residual_threshold)
    reject: Optional[str] = None
    if c.type not in EXACTLY_ONE_RELATIONS:
        reject = REJECT_NOT_BUY_SET
    elif residual <= thr:
        reject = REJECT_RESIDUAL_BELOW_THRESHOLD
    elif implied_edge <= 0:
        reject = REJECT_NO_POSITIVE_EDGE
    elif size <= 0 or not cert.executable_depth_ok:
        reject = REJECT_INSUFFICIENT_DEPTH
    elif after_cost_per_set <= profit_floor:
        reject = REJECT_EDGE_BELOW_COSTS

    return CandidateBundle(
        group_id=_group_id(c), relation=c.type.value, outcome_ids=ids,
        projection_residual=residual, divergence_score=divergence,
        implied_edge=implied_edge, gross_candidate_profit=gross,
        after_cost_candidate_profit=after_cost, confidence_band=band,
        size=round(size, 6), certified=bool(cert.certified and reject is None),
        reject_reason=reject, certificate=cert)

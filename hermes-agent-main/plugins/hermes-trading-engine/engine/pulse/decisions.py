"""GS Quant-style structured decision lifecycle records for the BTC pulse (Hermes-native).

These are small, auditable dataclasses (no gs-quant import, no external code) that give every
candidate a complete, reconcilable lifecycle:

    created -> feature_scored -> execution_costed -> accepted|rejected -> ledgered -> reported

They WRAP the existing flow (market data → signal → execution gate → paper fill → ledger);
they add structure/auditability only and never change decision logic. The execution-quality
gate remains the sole authority on whether a paper trade happens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


def ttc_bucket(ttc_s: Optional[float]) -> str:
    if ttc_s is None:
        return "na"
    if ttc_s < 60:
        return "<60s"
    if ttc_s < 120:
        return "60-120s"
    if ttc_s < 240:
        return "120-240s"
    return ">=240s"


def half_life_bucket(hl_s: Optional[float]) -> str:
    if hl_s is None:
        return "na"
    if hl_s < 30:
        return "<30s"
    if hl_s < 120:
        return "30-120s"
    return ">=120s"


@dataclass
class MarketContext:
    """Everything known about the market at the moment a candidate is created."""
    event_id: str
    market_id: str
    title: str
    asset: str = "BTC"
    open_ts: Optional[float] = None
    close_ts: Optional[float] = None
    ttc_s: Optional[float] = None
    oracle_source: str = "rtds_chainlink"
    s_open: Optional[float] = None
    s_now: Optional[float] = None
    sigma_per_sec: Optional[float] = None
    poly_yes: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    ask_depth_usd: Optional[float] = None
    lead_prices: dict = field(default_factory=dict)

    @property
    def ttc_bucket(self) -> str:
        return ttc_bucket(self.ttc_s)

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "market_id": self.market_id, "title": self.title,
                "asset": self.asset, "ttc_s": (round(self.ttc_s, 1) if self.ttc_s is not None else None),
                "ttc_bucket": self.ttc_bucket, "oracle_source": self.oracle_source,
                "s_open": self.s_open, "s_now": self.s_now,
                "sigma_per_sec": self.sigma_per_sec, "poly_yes": self.poly_yes,
                "best_bid": self.best_bid, "best_ask": self.best_ask, "spread": self.spread,
                "ask_depth_usd": self.ask_depth_usd, "lead_prices": dict(self.lead_prices)}


@dataclass
class CandidateDecision:
    """The directional model's view (not authoritative for execution)."""
    side: Optional[str]
    fair_p_up: Optional[float]
    outcome_prob: Optional[float]
    model_edge: float
    tradeable: bool
    reason: str

    def to_dict(self) -> dict:
        return {"side": self.side,
                "fair_p_up": (round(self.fair_p_up, 4) if self.fair_p_up is not None else None),
                "outcome_prob": (round(self.outcome_prob, 4) if self.outcome_prob is not None else None),
                "model_edge": round(self.model_edge, 4), "tradeable": self.tradeable,
                "reason": self.reason}


@dataclass
class ExecutionCostEstimate:
    """Output of the authoritative execution-quality gate (orderbook-reality EV)."""
    accepted: bool
    reason: str
    best_ask: Optional[float] = None
    vwap: Optional[float] = None
    slippage: float = 0.0
    ev_after_slippage: Optional[float] = None
    ev_at_mid: Optional[float] = None
    fillable_usd: float = 0.0
    spread: Optional[float] = None

    @classmethod
    def from_exec_result(cls, ex) -> "ExecutionCostEstimate":
        return cls(accepted=ex.accepted, reason=ex.reason, best_ask=ex.best_ask, vwap=ex.vwap,
                   slippage=ex.slippage, ev_after_slippage=ex.ev_after_slippage,
                   ev_at_mid=ex.ev_at_mid, fillable_usd=ex.fillable_usd, spread=ex.spread)

    def to_dict(self) -> dict:
        return {"accepted": self.accepted, "reason": self.reason, "best_ask": self.best_ask,
                "vwap": (round(self.vwap, 6) if self.vwap is not None else None),
                "slippage": round(self.slippage, 6),
                "ev_after_slippage": (round(self.ev_after_slippage, 6)
                                      if self.ev_after_slippage is not None else None),
                "ev_at_mid": (round(self.ev_at_mid, 6) if self.ev_at_mid is not None else None),
                "fillable_usd": round(self.fillable_usd, 2), "spread": self.spread}


@dataclass
class TradeAction:
    kind: str = "trade"
    side: Optional[str] = None
    token_id: Optional[str] = None
    fill_price: Optional[float] = None
    size_usd: float = 0.0
    shares: float = 0.0

    def to_dict(self) -> dict:
        return {"kind": "trade", "side": self.side, "fill_price": self.fill_price,
                "size_usd": self.size_usd, "shares": round(self.shares, 6)}


@dataclass
class RejectAction:
    kind: str = "reject"
    stage: str = "unknown"          # pre_candidate | directional | execution_gate
    reason: str = ""

    def to_dict(self) -> dict:
        return {"kind": "reject", "stage": self.stage, "reason": self.reason}


@dataclass
class PaperFill:
    window_key: str
    side: str
    fill_price: float
    shares: float
    size_usd: float

    def to_dict(self) -> dict:
        return {"window_key": self.window_key, "side": self.side, "fill_price": self.fill_price,
                "shares": round(self.shares, 6), "size_usd": self.size_usd}


@dataclass
class DecisionResult:
    """The complete, auditable lifecycle record for one candidate."""
    market_context: MarketContext
    candidate: CandidateDecision
    features: Optional[dict] = None
    cost: Optional[ExecutionCostEstimate] = None
    action: Optional[object] = None             # TradeAction | RejectAction
    fill: Optional[PaperFill] = None
    status: str = "rejected"                    # accepted | rejected
    reject_stage: Optional[str] = None
    lifecycle: list = field(default_factory=lambda: ["created"])

    def mark(self, stage: str) -> None:
        if stage not in self.lifecycle:
            self.lifecycle.append(stage)

    def to_dict(self) -> dict:
        return {"market_context": self.market_context.to_dict(),
                "candidate": self.candidate.to_dict(),
                "features": self.features,
                "cost": (self.cost.to_dict() if self.cost else None),
                "action": (self.action.to_dict() if self.action else None),
                "fill": (self.fill.to_dict() if self.fill else None),
                "status": self.status, "reject_stage": self.reject_stage,
                "lifecycle": list(self.lifecycle)}


class LifecycleReconciler:
    """Tallies every candidate through the lifecycle so the report can prove that
    created == accepted + rejected, ledgered == accepted, and reported == created."""

    def __init__(self):
        self.created = 0
        self.feature_scored = 0
        self.execution_costed = 0
        self.accepted = 0
        self.ledgered = 0
        self.reported = 0
        self.rejected = {"pre_candidate": 0, "directional": 0, "execution_gate": 0}

    def record(self, dr: DecisionResult) -> None:
        self.created += 1
        self.reported += 1
        if dr.features is not None:
            self.feature_scored += 1
        if dr.cost is not None:
            self.execution_costed += 1
        if dr.status == "accepted":
            self.accepted += 1
            if dr.fill is not None:
                self.ledgered += 1
        else:
            self.rejected[dr.reject_stage or "pre_candidate"] = \
                self.rejected.get(dr.reject_stage or "pre_candidate", 0) + 1

    def report(self) -> dict:
        rej_total = sum(self.rejected.values())
        return {"created": self.created, "feature_scored": self.feature_scored,
                "execution_costed": self.execution_costed, "accepted": self.accepted,
                "rejected_total": rej_total, "rejected_by_stage": dict(self.rejected),
                "ledgered": self.ledgered, "reported": self.reported,
                "reconciled": (self.created == self.accepted + rej_total
                               and self.ledgered == self.accepted
                               and self.reported == self.created)}

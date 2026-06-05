"""Canonical Algorithmic Edge Audit model (PAPER ONLY, pure, deterministic).

A single typed model the report, status CLI, and dashboard all agree on. Its job
is to make the bot **incapable of reporting algorithmic readiness when the edge
engine is inactive**: it encodes the hard failures and the readiness caps so a
green-looking number can never hide a disabled Bregman engine, a zero-scan run,
missing fill realism / after-cost PnL, a red test suite, or a dashboard/paper
equity mismatch.

Readiness caps (a readiness score may never exceed these):
* **< 40** when Bregman is disabled or scans zero constraint groups.
* **< 50** when the full pytest suite is not green.
* **< 60** when fill realism or after-cost PnL is missing.

Hard failures additionally force ``ok=False`` (the report is not decision-grade).

Quant responsibilities — this model is the contract the whole quant org reports
against; per-domain ownership is documented in :data:`QUANT_RESPONSIBILITY_DOMAINS`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Mapping, Optional

from engine.arbitrage.certificate import missing_bregman_fields
from engine.fill_realism import missing_fill_realism_fields
from engine.strategies.strategy_attribution import missing_attribution_fields

logger = logging.getLogger("hte.edge_audit")

# Readiness ceilings (a score may never exceed the applicable cap).
CAP_BREGMAN_INACTIVE = 39   # "below 40"
CAP_TESTS_NOT_GREEN = 49    # "below 50"
CAP_REALISM_OR_AFTERCOST_MISSING = 59  # "below 60"

# Required non-null fields for the sections this module owns directly.
CALIBRATION_AUDIT_REQUIRED = ("brier",)
RISK_AUDIT_REQUIRED = ("max_drawdown",)
EXECUTION_AUDIT_REQUIRED = ("clob_v2_executable",)
READINESS_AUDIT_REQUIRED = ("production_readiness_score",)


def _missing(section: Mapping, required, prefix: str) -> list:
    section = section or {}
    return [f"{prefix}.{k}" for k in required if section.get(k) is None]


@dataclass
class AlgorithmicEdgeAudit:
    """Typed, non-null-validated audit across the seven decision-grade domains."""

    strategy_attribution: dict
    bregman: dict
    fill_realism: dict
    calibration: dict
    risk: dict
    execution: dict
    readiness: dict
    bregman_enabled: bool = False
    tests_passing: Optional[bool] = None
    equity_mismatch_pct: Optional[float] = None
    raw_readiness_score: Optional[float] = None
    stale: bool = False
    status_age_s: Optional[float] = None
    no_status: bool = False

    # -- validation ----------------------------------------------------------
    def required_field_violations(self) -> list:
        """Required non-null fields that are missing across all seven sections."""
        v: list = []
        v += missing_attribution_fields(self.strategy_attribution)
        v += missing_bregman_fields(self.bregman)
        v += missing_fill_realism_fields(self.fill_realism)
        v += _missing(self.calibration, CALIBRATION_AUDIT_REQUIRED, "calibration")
        v += _missing(self.risk, RISK_AUDIT_REQUIRED, "risk")
        v += _missing(self.execution, EXECUTION_AUDIT_REQUIRED, "execution")
        v += _missing(self.readiness, READINESS_AUDIT_REQUIRED, "readiness")
        return v

    def _scans(self) -> Optional[float]:
        try:
            return float(self.bregman.get("constraint_groups_scanned"))
        except (TypeError, ValueError):
            return None

    def hard_failures(self) -> list:
        """Canonical blockers that force a non-decision-grade audit (paper)."""
        fails: list = []
        if self.no_status:
            fails.append("no_training_status")
        if not self.bregman_enabled:
            fails.append("bregman_disabled")
        scans = self._scans()
        if scans is None or scans <= 0:
            fails.append("bregman_zero_groups_scanned")
        if self.fill_realism.get("fantasy_fills_rejected") is None:
            fails.append("fill_realism_null")
        if self.strategy_attribution.get("after_cost_pnl") is None:
            fails.append("after_cost_pnl_null")
        if (self.bregman.get("certified_arbitrages") is None
                or self.bregman.get("executable_depth_certified") is None):
            fails.append("missing_certified_arbitrage_fields")
        if self.tests_passing is False:
            fails.append("pytest_failed")
        if self.equity_mismatch_pct is not None and self.equity_mismatch_pct > 1.0:
            fails.append("dashboard_equity_mismatch_gt_1pct")
        if self.stale:
            fails.append("status_stale")
        return fails

    def readiness_cap(self) -> int:
        """Maximum readiness score permitted given the current edge-engine state."""
        cap = 100
        scans = self._scans()
        if (not self.bregman_enabled) or scans is None or scans <= 0:
            cap = min(cap, CAP_BREGMAN_INACTIVE)
        if self.tests_passing is False:
            cap = min(cap, CAP_TESTS_NOT_GREEN)
        if (self.fill_realism.get("fantasy_fills_rejected") is None
                or self.strategy_attribution.get("after_cost_pnl") is None):
            cap = min(cap, CAP_REALISM_OR_AFTERCOST_MISSING)
        return cap

    def capped_readiness_score(self) -> Optional[float]:
        """Readiness score after applying the caps. When the raw score is unknown
        but a cap applies, the cap itself is reported (never a high number)."""
        cap = self.readiness_cap()
        raw = self.raw_readiness_score
        if raw is None:
            return None if cap >= 100 else float(cap)
        return float(min(float(raw), cap))

    def ok(self) -> bool:
        """Decision-grade only when there are no hard failures and no missing
        required fields. (Inactive edge engine can never be 'ok'.)"""
        return not self.hard_failures() and not self.required_field_violations()

    def to_dict(self) -> dict:
        return {
            "ok": self.ok(),
            "status": "complete" if self.ok() else "incomplete",
            "bregman_enabled": bool(self.bregman_enabled),
            "tests_passing": self.tests_passing,
            "equity_mismatch_pct": self.equity_mismatch_pct,
            "stale": bool(self.stale),
            "status_age_s": self.status_age_s,
            "hard_failures": self.hard_failures(),
            "required_field_violations": self.required_field_violations(),
            "readiness_cap": self.readiness_cap(),
            "raw_readiness_score": self.raw_readiness_score,
            "capped_readiness_score": self.capped_readiness_score(),
            "sections": {
                "strategy_attribution": self.strategy_attribution,
                "bregman": self.bregman,
                "fill_realism": self.fill_realism,
                "calibration": self.calibration,
                "risk": self.risk,
                "execution": self.execution,
                "readiness": self.readiness,
            },
        }


# Per-domain quant ownership (analyst / researcher / developer / trader) across
# the full pipeline. Documented here so the canonical audit and the report agree.
QUANT_RESPONSIBILITY_DOMAINS: dict = {
    "data_acquisition_ingestion": {
        "analyst": "define the market/feed universe + freshness SLAs",
        "researcher": "validate feed coverage + latency assumptions",
        "developer": "read-only CLOB v2 / Chainlink / fast-price ingestion (no live)",
        "trader": "consume only fresh, validated inputs",
    },
    "data_preprocessing_feature_engineering": {
        "analyst": "specify causal, no-lookahead features",
        "researcher": "oracle/fast-price features; stale-anchor + disagreement",
        "developer": "pure feature transforms (engine.features.*)",
        "trader": "uses features only as evidence, never as proof",
    },
    "statistical_probabilistic_modeling": {
        "analyst": "calibration targets (Brier/ECE)",
        "researcher": "isotonic/Platt + rollback guardrails; conformal bands",
        "developer": "probability ensemble + calibration models",
        "trader": "trades calibrated probabilities, not raw model output",
    },
    "signal_generation_strategy_bregman_priority": {
        "analyst": "constraint universe / relationship graph",
        "researcher": "incoherence + certificate thresholds; Bregman FIRST",
        "developer": "Bregman projection + certificate + tiered router",
        "trader": "acts only on certified, fill-feasible Bregman arbs first",
    },
    "risk_management_portfolio_optimization": {
        "analyst": "exposure / drawdown / CVaR limits",
        "researcher": "fractional-Kelly + correlated/per-event caps",
        "developer": "deterministic RiskEngine gate + portfolio optimizer",
        "trader": "never exceeds caps; guaranteed arb over probabilistic edge",
    },
    "backtesting_simulation": {
        "analyst": "after-cost, depth-aware success criteria",
        "researcher": "latency/stale-book/fee realism assumptions",
        "developer": "fill model + paper OMS; fantasy-fill rejection",
        "trader": "trusts only after-cost, fill-realistic paper PnL",
    },
    "strategy_optimization_robustness": {
        "analyst": "regime buckets + significance thresholds",
        "researcher": "walk-forward + purged CV + bootstrap CIs + ablations",
        "developer": "robustness tooling; exploration vs validation split",
        "trader": "production-readiness only on validation evidence",
    },
    "clob_v2_execution": {
        "analyst": "executable-depth + atomicity requirements",
        "researcher": "FOK/IOC + worst-case slippage + timeout policy",
        "developer": "paper multi-leg execution planner (no live orders)",
        "trader": "acts only on atomic, fill-feasible plans",
    },
    "live_trading_monitoring": {
        "analyst": "monitoring KPIs + kill-switch criteria",
        "researcher": "opportunity decay, latency, stale-data, rollback signals",
        "developer": "monitoring endpoints + status board controls",
        "trader": "halts on kill-switch / negative after-cost expectancy",
    },
    "compliance_security_operational_excellence": {
        "analyst": "PAPER-only policy + audit requirements",
        "researcher": "no-leakage + secret-handling validation",
        "developer": "secret redaction + forbidden-live-flag audit",
        "trader": "never enables a live/wallet/order path",
    },
}

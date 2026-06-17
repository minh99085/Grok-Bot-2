"""Live-readiness gate + capital-preservation plan (PAPER ONLY — verdicts only).

The bot is transitioning from aggressive paper training toward real-money
Polymarket use. This module is the GATE that blocks real-money escalation unless
the strategy proves durable after-cost profitability, execution realism,
calibration quality, settlement-label quality, and risk-gate cleanliness. It
produces readiness VERDICTS and HARD BLOCKERS only — it never enables live
trading, never sizes a real order, and never touches a live flag.

Quant scope (documented end-to-end):

* **Data Acquisition & Ingestion / Preprocessing & Feature Engineering** — the
  no-stale-data gate (stale Chainlink / stale order books) and the
  settlement-label-quality gate (no unresolved / ambiguous / suppressed labels).
* **Statistical & Probabilistic Modeling** — the calibration gate (Brier / ECE /
  calibration error) and out-of-sample Sharpe / Sortino / Calmar gates.
* **Signal Generation & Strategy Development (Bregman arbitrage priority)** — the
  Bregman gate: zero false-positive certified opportunities, positive worst-case
  PnL after costs, full-hedge validation, all-leg fill feasibility, and
  partial-fill hedge-break rejection.
* **Risk Management & Portfolio Optimization** — the risk-gate-cleanliness gate
  and the capital-preservation plan (bounded initial live notional, daily loss,
  per-market + event exposure, auto-downgrade rules).
* **Backtesting & Simulation / Strategy Optimization & Robustness Testing** — the
  minimum-sample-size + out-of-sample + bounded-drawdown gates.
* **CLOB v2 Execution** — the realistic-fill profitability gate (a strategy that
  is only profitable under optimistic fills is BLOCKED).
* **Live Trading & Monitoring / Compliance/Security/Operational Excellence** —
  staged readiness states + a hard invariant that live is never auto-enabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


class ReadinessState:
    BLOCKED = "blocked"
    PAPER_LEARNING = "paper_learning"
    PAPER_QUALIFIED = "paper_qualified"
    MICRO_CANARY_READY = "micro_canary_ready"
    CANARY_READY = "canary_ready"

    ORDER = [BLOCKED, PAPER_LEARNING, PAPER_QUALIFIED, MICRO_CANARY_READY, CANARY_READY]
    LIVE_READY = {MICRO_CANARY_READY, CANARY_READY}


@dataclass
class GateResult:
    name: str
    passed: bool
    severity: str            # "CRITICAL" (blocker) | "TIER" | "INFO"
    observed: object = None
    threshold: object = None
    reason: str = ""
    applies: bool = True

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "severity": self.severity,
                "observed": self.observed, "threshold": self.threshold,
                "reason": self.reason, "applies": self.applies}


@dataclass
class ReadinessCriteria:
    # sample-size staging
    min_eval_samples: int = 30
    min_qualified_samples: int = 200
    min_canary_samples: int = 500
    min_canary_full_samples: int = 1000
    # edge / execution realism (strictly positive)
    min_after_cost_expectancy: float = 0.0
    min_realistic_fill_expectancy: float = 0.0
    # 6C out-of-sample expectancy promotion gate (held-out readiness trades)
    min_oos_expectancy_samples: int = 20
    min_oos_after_cost_expectancy: float = 0.0
    oos_require_positive_lower_bound: bool = True
    # out-of-sample risk-adjusted return
    min_oos_sharpe: float = 1.0
    min_canary_sharpe: float = 1.5
    min_oos_sortino: float = 1.0
    min_oos_calmar: float = 0.5
    max_drawdown_pct: float = 0.15
    # calibration quality
    max_calibration_error: float = 0.10
    max_ece: float = 0.10
    # settlement-label quality
    max_label_suppression_rate: float = 0.20
    max_unresolved_rate: float = 0.20
    max_ambiguous_rate: float = 0.20
    # data freshness / risk
    max_stale_rejection_rate: float = 0.10
    max_risk_violations: int = 0
    # Bregman
    max_bregman_fp_rate: float = 0.0
    min_bregman_worst_case_pnl: float = 0.0

    @classmethod
    def from_config(cls, cfg) -> "ReadinessCriteria":
        g = lambda n, d: getattr(cfg, n, d)
        return cls(
            min_eval_samples=int(g("readiness_min_eval_samples", 30)),
            min_qualified_samples=int(g("readiness_min_qualified_samples", 200)),
            min_canary_samples=int(g("readiness_min_canary_samples", 500)),
            min_canary_full_samples=int(g("readiness_min_canary_full_samples", 1000)),
            min_oos_sharpe=float(g("readiness_min_oos_sharpe", 1.0)),
            min_canary_sharpe=float(g("readiness_min_canary_sharpe", 1.5)),
            min_oos_sortino=float(g("readiness_min_oos_sortino", 1.0)),
            min_oos_calmar=float(g("readiness_min_oos_calmar", 0.5)),
            max_drawdown_pct=float(g("readiness_max_drawdown_pct", 0.15)),
            max_calibration_error=float(g("readiness_max_calibration_error", 0.10)),
            max_ece=float(g("readiness_max_ece", 0.10)),
            max_label_suppression_rate=float(g("readiness_max_label_suppression_rate", 0.20)),
            max_unresolved_rate=float(g("readiness_max_unresolved_rate", 0.20)),
            max_ambiguous_rate=float(g("readiness_max_ambiguous_rate", 0.20)),
            max_stale_rejection_rate=float(g("readiness_max_stale_rejection_rate", 0.10)),
            min_oos_expectancy_samples=int(g("readiness_min_oos_expectancy_samples", 20)),
            min_oos_after_cost_expectancy=float(g("readiness_min_oos_after_cost_expectancy", 0.0)),
            oos_require_positive_lower_bound=bool(
                g("readiness_oos_require_positive_lower_bound", True)))


@dataclass
class ReadinessVerdict:
    state: str
    gates: list = field(default_factory=list)
    blockers: list = field(default_factory=list)
    score: int = 0
    evidence: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    # HARD INVARIANT: a verdict never enables live trading.
    live_trading_enabled: bool = False

    @property
    def allows_live_escalation(self) -> bool:
        return self.state in ReadinessState.LIVE_READY

    def to_dict(self) -> dict:
        return {"state": self.state, "allows_live_escalation": self.allows_live_escalation,
                "live_trading_enabled": False, "score": self.score,
                "blockers": list(self.blockers), "notes": list(self.notes),
                "gates": [g.to_dict() for g in self.gates], "evidence": dict(self.evidence)}


def _f(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def evaluate_live_readiness(evidence: dict,
                            criteria: Optional[ReadinessCriteria] = None) -> ReadinessVerdict:
    """Evaluate the readiness gate against ``evidence`` and return a verdict.

    A verdict only reaches ``micro_canary_ready`` / ``canary_ready`` when every
    CRITICAL gate passes AND the staged sample-size + out-of-sample thresholds are
    met. Any CRITICAL failure -> ``blocked``. Insufficient samples (with otherwise
    clean evidence) -> ``paper_learning`` (NOT live-ready, NOT blocked)."""
    c = criteria or ReadinessCriteria()
    e = evidence or {}
    breg = e.get("bregman", {}) or {}
    samples = int(_f(e.get("samples"), 0))
    enough_eval = samples >= c.min_eval_samples
    breg_opps = int(_f(breg.get("opportunities"), 0))

    gates: list[GateResult] = []

    def crit(name, passed, *, observed=None, threshold=None, reason="", applies=True):
        gates.append(GateResult(name, bool(passed), "CRITICAL", observed, threshold,
                                reason, applies))

    def tier(name, passed, *, observed=None, threshold=None):
        gates.append(GateResult(name, bool(passed), "TIER", observed, threshold))

    # ---- always-on safety / data-integrity / Bregman blockers ----
    no_stale = (_f(e.get("stale_data_rejection_rate")) <= c.max_stale_rejection_rate
                and not bool(e.get("chainlink_stale")) and not bool(e.get("stale_book")))
    crit("no_stale_data_dependence", no_stale,
         observed={"rate": _f(e.get("stale_data_rejection_rate")),
                   "chainlink_stale": bool(e.get("chainlink_stale")),
                   "stale_book": bool(e.get("stale_book"))},
         threshold=c.max_stale_rejection_rate, reason="stale Chainlink / order book")
    crit("no_risk_gate_violations", int(_f(e.get("risk_violations"))) <= c.max_risk_violations,
         observed=int(_f(e.get("risk_violations"))), threshold=c.max_risk_violations)
    clean_labels = (_f(e.get("label_suppression_rate")) <= c.max_label_suppression_rate
                    and _f(e.get("unresolved_rate")) <= c.max_unresolved_rate
                    and _f(e.get("ambiguous_rate")) <= c.max_ambiguous_rate)
    crit("clean_settlement_labels", clean_labels,
         observed={"suppression": _f(e.get("label_suppression_rate")),
                   "unresolved": _f(e.get("unresolved_rate")),
                   "ambiguous": _f(e.get("ambiguous_rate"))},
         reason="dirty / unresolved settlement labels")
    crit("not_kill_switch_downgraded", not bool(e.get("downgraded")),
         observed=bool(e.get("downgraded")))
    # Bregman gates (false positives + partial-fill break ALWAYS apply)
    crit("bregman_zero_false_positives", _f(breg.get("false_positive_rate")) <= c.max_bregman_fp_rate,
         observed=_f(breg.get("false_positive_rate")), threshold=c.max_bregman_fp_rate)
    crit("bregman_no_partial_fill_hedge_break", not bool(breg.get("partial_fill_hedge_break")),
         observed=bool(breg.get("partial_fill_hedge_break")))
    crit("bregman_positive_worst_case_pnl",
         (breg_opps == 0) or _f(breg.get("worst_case_pnl")) > c.min_bregman_worst_case_pnl,
         observed=_f(breg.get("worst_case_pnl")), threshold=c.min_bregman_worst_case_pnl,
         applies=breg_opps > 0)
    crit("bregman_full_hedge_validated",
         (breg_opps == 0) or bool(breg.get("full_hedge_validated")),
         observed=bool(breg.get("full_hedge_validated")), applies=breg_opps > 0)
    crit("bregman_all_leg_fill_feasible",
         (breg_opps == 0) or bool(breg.get("all_leg_fill_feasible")),
         observed=bool(breg.get("all_leg_fill_feasible")), applies=breg_opps > 0)

    # ---- sample-gated edge / execution / calibration blockers ----
    crit("positive_after_cost_expectancy",
         (not enough_eval) or _f(e.get("after_cost_expectancy")) > c.min_after_cost_expectancy,
         observed=_f(e.get("after_cost_expectancy")), threshold=c.min_after_cost_expectancy,
         applies=enough_eval, reason="negative after-cost expectancy")
    crit("realistic_fill_profitable",
         (not enough_eval) or _f(e.get("realistic_fill_expectancy")) > c.min_realistic_fill_expectancy,
         observed=_f(e.get("realistic_fill_expectancy")),
         threshold=c.min_realistic_fill_expectancy, applies=enough_eval,
         reason="not profitable under realistic fills (optimistic-only)")
    # 6C: held-out (out-of-sample) after-cost expectancy must be CREDIBLY positive before
    # promotion — in-sample profit alone can be overfit. Applies only once the held-out
    # window has enough samples; below that it stays paper_learning (not blocked).
    oos_n = int(_f(e.get("oos_expectancy_samples"), 0))
    oos_exp = _f(e.get("oos_after_cost_expectancy"))
    oos_lb = _f(e.get("oos_after_cost_expectancy_lb"))
    oos_applicable = oos_n >= c.min_oos_expectancy_samples
    oos_credible = (oos_exp > c.min_oos_after_cost_expectancy
                    and (not c.oos_require_positive_lower_bound
                         or oos_lb > c.min_oos_after_cost_expectancy))
    crit("positive_out_of_sample_expectancy", (not oos_applicable) or oos_credible,
         observed={"oos_expectancy": round(oos_exp, 6), "oos_lower_bound": round(oos_lb, 6),
                   "oos_samples": oos_n},
         threshold=c.min_oos_after_cost_expectancy, applies=oos_applicable,
         reason="held-out after-cost expectancy not credibly positive (overfit guard)")
    crit("calibrated_probabilities",
         (not enough_eval) or (_f(e.get("calibration_error")) <= c.max_calibration_error
                               and _f(e.get("ece")) <= c.max_ece),
         observed={"calibration_error": _f(e.get("calibration_error")), "ece": _f(e.get("ece"))},
         applies=enough_eval)
    crit("bounded_max_drawdown",
         (not enough_eval) or _f(e.get("max_drawdown_pct")) <= c.max_drawdown_pct,
         observed=_f(e.get("max_drawdown_pct")), threshold=c.max_drawdown_pct,
         applies=enough_eval)

    # ---- tier gates (staging, not blockers) ----
    tier("sufficient_samples_qualified", samples >= c.min_qualified_samples,
         observed=samples, threshold=c.min_qualified_samples)
    tier("oos_sharpe", _f(e.get("oos_sharpe")) >= c.min_oos_sharpe,
         observed=_f(e.get("oos_sharpe")), threshold=c.min_oos_sharpe)
    tier("oos_sortino", _f(e.get("oos_sortino")) >= c.min_oos_sortino,
         observed=_f(e.get("oos_sortino")), threshold=c.min_oos_sortino)
    tier("oos_calmar", _f(e.get("oos_calmar")) >= c.min_oos_calmar,
         observed=_f(e.get("oos_calmar")), threshold=c.min_oos_calmar)

    blockers = [g.name + (f"({g.reason})" if g.reason else "")
                for g in gates if g.severity == "CRITICAL" and g.applies and not g.passed]

    # ---- state machine ----
    if blockers:
        state = ReadinessState.BLOCKED
    else:
        oos_ok = (_f(e.get("oos_sharpe")) >= c.min_oos_sharpe
                  and _f(e.get("oos_sortino")) >= c.min_oos_sortino
                  and _f(e.get("oos_calmar")) >= c.min_oos_calmar)
        bregman_validated = (_f(breg.get("false_positive_rate")) <= c.max_bregman_fp_rate
                             and not bool(breg.get("partial_fill_hedge_break"))
                             and (breg_opps == 0 or (_f(breg.get("worst_case_pnl")) > 0.0
                                  and bool(breg.get("full_hedge_validated"))
                                  and bool(breg.get("all_leg_fill_feasible")))))
        if enough_eval and samples >= c.min_qualified_samples and oos_ok:
            state = ReadinessState.PAPER_QUALIFIED
            if (samples >= c.min_canary_samples
                    and _f(e.get("oos_sharpe")) >= c.min_canary_sharpe
                    and bregman_validated):
                state = ReadinessState.MICRO_CANARY_READY
                if samples >= c.min_canary_full_samples:
                    state = ReadinessState.CANARY_READY
        else:
            state = ReadinessState.PAPER_LEARNING

    applicable = [g for g in gates if g.applies]
    passed = sum(1 for g in applicable if g.passed)
    score = round(100.0 * passed / len(applicable)) if applicable else 0
    return ReadinessVerdict(state=state, gates=gates, blockers=blockers, score=score,
                            evidence={"samples": samples, "bregman_opportunities": breg_opps},
                            notes=["PAPER ONLY — verdict never enables live trading."])


# --------------------------------------------------------------------------- #
# capital-preservation plan
# --------------------------------------------------------------------------- #
def capital_preservation_report(verdict_or_state: Union[ReadinessVerdict, str], *,
                                bankroll: float, cfg=None) -> dict:
    """Capital-preservation plan for a readiness state. NON-live-ready states get
    ZERO allowed live notional. Live-ready states get a tiny, hard-bounded initial
    notional + daily-loss / per-market / event caps + automatic downgrade rules.
    Never enables live trading — it only bounds what a future live escalation
    could risk, and how it would auto-downgrade."""
    state = verdict_or_state.state if isinstance(verdict_or_state, ReadinessVerdict) \
        else str(verdict_or_state)
    bankroll = max(0.0, float(bankroll or 0.0))

    def g(n, d):
        return float(getattr(cfg, n, d)) if cfg is not None else float(d)

    micro_cap = g("live_micro_canary_notional_usd", 5.0)
    canary_cap = g("live_canary_notional_usd", 25.0)
    max_daily = g("live_max_daily_loss_usd", 10.0)
    per_market_cap = g("live_max_per_market_usd", 5.0)
    event_cap = g("live_max_event_usd", 5.0)

    rules = [
        {"trigger": "daily_loss > max_daily_loss", "action": "downgrade_to_paper"},
        {"trigger": "drawdown > max_drawdown_pct", "action": "downgrade_to_conservative"},
        {"trigger": "kill_switch_triggered", "action": "downgrade_to_paper"},
        {"trigger": "reconciliation_high_severity", "action": "halt"},
        {"trigger": "bregman_false_positive_or_partial_fill_break", "action": "halt"},
        {"trigger": "stale_chainlink_or_order_book", "action": "halt"},
    ]

    if state == ReadinessState.MICRO_CANARY_READY:
        initial = round(min(micro_cap, 0.01 * bankroll), 2)
        daily = round(min(max_daily, 0.01 * bankroll), 2)
        per_market = round(min(per_market_cap, initial), 2)
        event = round(min(event_cap, initial), 2)
    elif state == ReadinessState.CANARY_READY:
        initial = round(min(canary_cap, 0.05 * bankroll), 2)
        daily = round(min(max_daily, 0.02 * bankroll), 2)
        per_market = round(min(per_market_cap, initial), 2)
        event = round(min(event_cap, initial), 2)
    else:
        initial = daily = per_market = event = 0.0

    return {
        "state": state,
        "allowed": initial > 0.0,
        "bankroll": round(bankroll, 2),
        "max_initial_live_notional": initial,
        "max_daily_loss": daily,
        "max_per_market_exposure": per_market,
        "max_event_exposure": event,
        "auto_downgrade_rules": rules,
        "note": "PAPER ONLY — bounds a FUTURE manual live escalation; never auto-enables live.",
    }


def readiness_markdown(verdict: dict, capital: dict) -> list:
    """Concise markdown for the readiness + capital-preservation report."""
    v = verdict or {}
    cap = capital or {}
    return [
        "## Live-readiness gate (PAPER ONLY — verdict never enables live)",
        f"- state: **{v.get('state')}**  ·  live-escalation allowed: "
        f"{v.get('allows_live_escalation')}  ·  score: {v.get('score')}",
        f"- hard blockers: {', '.join(v.get('blockers', [])) or 'none'}",
        "## Capital preservation",
        f"- max initial live notional: {cap.get('max_initial_live_notional')}  ·  "
        f"max daily loss: {cap.get('max_daily_loss')}  ·  per-market: "
        f"{cap.get('max_per_market_exposure')}  ·  per-event: {cap.get('max_event_exposure')}",
        f"- auto-downgrade rules: {len(cap.get('auto_downgrade_rules', []))} "
        f"({', '.join(r['trigger'] for r in cap.get('auto_downgrade_rules', []))})",
    ]

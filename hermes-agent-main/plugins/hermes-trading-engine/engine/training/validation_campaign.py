"""Final institutional validation campaign (PAPER ONLY — never enables live).

This is the single decision-making harness that decides whether the bot is ready
for micro-live real-money Polymarket trading. It runs a fixed set of nine
campaign profiles, aggregates the full institutional metric set per profile,
evaluates the seven hard readiness criteria, produces a machine-readable +
markdown pass/fail report with an exact blocker list, and — ONLY when every gate
passes — emits a live-ready readiness verdict and mints a (dry-run, not
manually-enabled) canary readiness certificate. It never enables live trading.

Quant scope covered end-to-end:
* Data Acquisition & Ingestion / Preprocessing — evidence is read-only; freshness
  + settlement-label quality are inputs.
* Statistical & Probabilistic Modeling — calibration (Brier / log-loss / ECE /
  CI coverage) gates.
* Signal Generation & Strategy Development w/ Bregman priority — the Bregman-only
  and Bregman+Chainlink profiles + the Bregman-certification criterion.
* Risk Management & Portfolio Optimization — risk-gate cleanliness + drawdown /
  CVaR / capital-efficiency metrics.
* Backtesting & Simulation — conservative / aggressive / profit-governor profiles.
* Strategy Optimization & Robustness Testing — research + Chainlink ablations.
* CLOB v2 Execution — the realistic-fill profile + realistic-fill criterion.
* Live Trading & Monitoring — the micro-live dry-run profile + readiness verdict.
* Compliance/Security/Operational Excellence — no live trading; certificate only
  when ALL gates pass; every block carries the exact failed criterion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from .live_readiness import (ReadinessCriteria, ReadinessState,
                             capital_preservation_report, evaluate_live_readiness)

__all__ = [
    "CAMPAIGN_PROFILES", "CAMPAIGN_PROFILE_IDS", "CAMPAIGN_REQUIRED_CRITERIA",
    "CampaignProfile", "ProfileResult", "CampaignReport", "compute_profile_metrics",
    "evaluate_profile", "evaluate_campaign_criteria", "run_campaign",
    "build_ablation_report", "default_campaign_evidence", "campaign_markdown",
    "campaign_json",
]


# --------------------------------------------------------------------------- #
# profiles
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CampaignProfile:
    id: str
    label: str
    category: str           # "gate" | "ablation"
    description: str


CAMPAIGN_PROFILES = (
    CampaignProfile("conservative_baseline", "Conservative baseline", "gate",
                    "Conservative paper trading baseline."),
    CampaignProfile("aggressive_learning", "Aggressive learning", "gate",
                    "Aggressive paper learning."),
    CampaignProfile("aggressive_plus_profit_governor", "Aggressive + profit governor", "gate",
                    "Aggressive learning gated by the profitability governor."),
    CampaignProfile("bregman_certified_only", "Bregman certified only", "gate",
                    "Only certified Bregman arbitrage."),
    CampaignProfile("bregman_plus_chainlink", "Bregman + Chainlink fair value", "gate",
                    "Certified Bregman with Chainlink fair-value support."),
    CampaignProfile("no_research_ablation", "No-research ablation", "ablation",
                    "Research advisory disabled (robustness)."),
    CampaignProfile("no_chainlink_ablation", "No-Chainlink ablation", "ablation",
                    "Chainlink fair-value disabled (robustness)."),
    CampaignProfile("realistic_fill_validation", "Realistic-fill validation", "gate",
                    "Profitability under realistic CLOB v2 fills."),
    CampaignProfile("micro_live_dry_run", "Micro-live dry-run", "gate",
                    "Micro-live dry-run (no real orders)."),
)
CAMPAIGN_PROFILE_IDS = tuple(p.id for p in CAMPAIGN_PROFILES)
_PROFILE_BY_ID = {p.id: p for p in CAMPAIGN_PROFILES}

_GATING_PROFILES = tuple(p.id for p in CAMPAIGN_PROFILES if p.category == "gate")
_BREGMAN_PROFILES = ("bregman_certified_only", "bregman_plus_chainlink")
_REALISTIC_PROFILES = ("realistic_fill_validation", "micro_live_dry_run")

# the seven hard institutional criteria; readiness requires ALL of them
CAMPAIGN_REQUIRED_CRITERIA = (
    "after_cost_profitability",
    "out_of_sample_robustness",
    "realistic_fill_profitability",
    "clean_settlement_labels",
    "calibrated_probabilities",
    "bregman_certification",
    "risk_gate_cleanliness",
)

# criterion -> (readiness gate names, profile-id subset to check)
_CRITERION_GATES = {
    "after_cost_profitability": (("positive_after_cost_expectancy",), _GATING_PROFILES),
    "out_of_sample_robustness": (("oos_sharpe", "oos_sortino", "oos_calmar"), _GATING_PROFILES),
    "realistic_fill_profitability": (("realistic_fill_profitable",), _REALISTIC_PROFILES),
    "clean_settlement_labels": (("clean_settlement_labels",), _GATING_PROFILES),
    "calibrated_probabilities": (("calibrated_probabilities",), _GATING_PROFILES),
    "bregman_certification": (("bregman_zero_false_positives",
                               "bregman_no_partial_fill_hedge_break",
                               "bregman_positive_worst_case_pnl",
                               "bregman_full_hedge_validated",
                               "bregman_all_leg_fill_feasible"), _BREGMAN_PROFILES),
    "risk_gate_cleanliness": (("no_risk_gate_violations", "not_kill_switch_downgraded",
                               "no_stale_data_dependence"), _GATING_PROFILES),
}


def _f(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


# --------------------------------------------------------------------------- #
# per-profile metrics (the full final metric set)
# --------------------------------------------------------------------------- #
def compute_profile_metrics(evidence: dict, *, readiness_state: Optional[str] = None) -> dict:
    """Assemble the full institutional final-metric set for a profile from
    ``evidence`` (read-only). Missing values default to safe zeros so the report
    always has a complete, machine-readable shape."""
    e = evidence or {}
    breg = e.get("bregman", {}) or {}
    suppression = _f(e.get("label_suppression_rate"))
    unresolved = _f(e.get("unresolved_rate"))
    ambiguous = _f(e.get("ambiguous_rate"))
    label_quality = round(1.0 - max(suppression, unresolved, ambiguous), 6)
    state = readiness_state if readiness_state is not None else \
        evaluate_live_readiness(e).state
    return {
        "net_pnl": round(_f(e.get("net_pnl")), 6),
        "after_cost_expectancy": round(_f(e.get("after_cost_expectancy")), 8),
        "realistic_fill_expectancy": round(_f(e.get("realistic_fill_expectancy")), 8),
        "sharpe": round(_f(e.get("sharpe", e.get("oos_sharpe"))), 6),
        "sortino": round(_f(e.get("sortino", e.get("oos_sortino"))), 6),
        "calmar": round(_f(e.get("calmar", e.get("oos_calmar"))), 6),
        "omega": round(_f(e.get("omega")), 6),
        "max_drawdown": round(_f(e.get("max_drawdown_pct", e.get("max_drawdown"))), 6),
        "cvar": round(_f(e.get("cvar")), 6),
        "profit_factor": round(_f(e.get("profit_factor")), 6),
        "turnover": round(_f(e.get("turnover")), 6),
        "brier": round(_f(e.get("brier")), 6),
        "log_loss": round(_f(e.get("log_loss")), 6),
        "ece": round(_f(e.get("ece")), 6),
        "ci_coverage": round(_f(e.get("ci_coverage")), 6),
        "edge_decay": round(_f(e.get("edge_decay")), 6),
        "fill_quality": round(_f(e.get("fill_quality")), 6),
        "slippage_bps": round(_f(e.get("slippage_bps")), 6),
        "markout": round(_f(e.get("markout")), 6),
        "label_quality": label_quality,
        "bregman_fp_rate": round(_f(breg.get("false_positive_rate")), 6),
        "capital_efficiency": round(_f(e.get("capital_efficiency")), 6),
        "samples": int(_f(e.get("samples"))),
        "readiness_state": state,
    }


# --------------------------------------------------------------------------- #
# per-profile evaluation
# --------------------------------------------------------------------------- #
@dataclass
class ProfileResult:
    profile_id: str
    label: str
    category: str
    metrics: dict
    verdict: dict
    gate_status: dict           # gate_name -> {"applies": bool, "passed": bool}
    passed: bool
    blockers: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"profile_id": self.profile_id, "label": self.label, "category": self.category,
                "passed": self.passed, "blockers": list(self.blockers),
                "metrics": self.metrics, "verdict": self.verdict}


def evaluate_profile(profile_id: str, evidence: dict,
                     criteria: Optional[ReadinessCriteria] = None) -> ProfileResult:
    """Evaluate one campaign profile: readiness verdict + full metrics + the
    per-gate status used by the campaign criteria aggregation."""
    prof = _PROFILE_BY_ID.get(profile_id)
    label = prof.label if prof else profile_id
    category = prof.category if prof else "gate"
    verdict = evaluate_live_readiness(evidence or {}, criteria)
    gate_status = {g.name: {"applies": bool(g.applies), "passed": bool(g.passed)}
                   for g in verdict.gates}
    metrics = compute_profile_metrics(evidence, readiness_state=verdict.state)
    passed = verdict.state != ReadinessState.BLOCKED
    return ProfileResult(profile_id=profile_id, label=label, category=category,
                         metrics=metrics, verdict=verdict.to_dict(),
                         gate_status=gate_status, passed=passed,
                         blockers=list(verdict.blockers))


# --------------------------------------------------------------------------- #
# campaign criteria aggregation
# --------------------------------------------------------------------------- #
def evaluate_campaign_criteria(profile_results: dict) -> dict:
    """Aggregate the per-profile gate status into the seven hard institutional
    criteria. A criterion PASSES only when every mapped readiness gate passes in
    every profile where it applies."""
    out: dict = {}
    for crit, (gate_names, profile_ids) in _CRITERION_GATES.items():
        failed_profiles: list = []
        applied_anywhere = False
        for pid in profile_ids:
            pr = profile_results.get(pid)
            if pr is None:
                continue
            for gname in gate_names:
                gs = pr.gate_status.get(gname)
                if not gs or not gs["applies"]:
                    continue
                applied_anywhere = True
                if not gs["passed"]:
                    failed_profiles.append(pid)
                    break
        passed = applied_anywhere and not failed_profiles
        out[crit] = {"passed": bool(passed), "applied": bool(applied_anywhere),
                     "profiles_failed": sorted(set(failed_profiles)),
                     "gates": list(gate_names)}
    return out


# --------------------------------------------------------------------------- #
# campaign report
# --------------------------------------------------------------------------- #
@dataclass
class CampaignReport:
    profiles: dict                 # profile_id -> ProfileResult
    criteria: dict
    overall_ready: bool
    readiness_state: str
    readiness_verdict: dict
    blockers: list
    capital_preservation: dict
    ablation: dict
    certificate: object = None     # CanaryReadinessCertificate | None

    def to_dict(self) -> dict:
        return {
            "overall_ready": self.overall_ready,
            "readiness_state": self.readiness_state,
            "readiness_verdict": self.readiness_verdict,
            "blockers": list(self.blockers),
            "criteria": self.criteria,
            "ablation": self.ablation,
            "capital_preservation": self.capital_preservation,
            "certificate": self.certificate.to_dict() if self.certificate else None,
            "profiles": {pid: pr.to_dict() for pid, pr in self.profiles.items()},
            "note": "PAPER ONLY — this report never enables live trading.",
        }


def _state_rank(state: str) -> int:
    try:
        return ReadinessState.ORDER.index(state)
    except ValueError:
        return 0


def run_campaign(evidence_by_profile: dict, *, criteria: Optional[ReadinessCriteria] = None,
                 bankroll: float = 1000.0, caps=None) -> CampaignReport:
    """Run the full institutional validation campaign and return a pass/fail
    report. Mints a (dry-run) canary certificate ONLY when every hard criterion
    passes AND the combined readiness state is live-ready. Never enables live."""
    evidence_by_profile = dict(evidence_by_profile or {})
    results: dict = {}
    for pid in CAMPAIGN_PROFILE_IDS:
        results[pid] = evaluate_profile(pid, evidence_by_profile.get(pid, {}), criteria)

    crit_results = evaluate_campaign_criteria(results)
    overall_ready = all(crit_results[c]["passed"] for c in CAMPAIGN_REQUIRED_CRITERIA)

    # combined readiness = the MOST CONSERVATIVE gating profile state
    gating = [(pid, results[pid]) for pid in _GATING_PROFILES if pid in results]
    min_pid, min_pr = min(gating, key=lambda kv: _state_rank(kv[1].verdict["state"])) \
        if gating else (None, None)
    readiness_state = min_pr.verdict["state"] if min_pr else ReadinessState.BLOCKED
    readiness_verdict = dict(min_pr.verdict) if min_pr else {
        "state": ReadinessState.BLOCKED, "allows_live_escalation": False,
        "live_trading_enabled": False, "blockers": [], "score": 0}

    blockers: list = []
    for crit in CAMPAIGN_REQUIRED_CRITERIA:
        cr = crit_results[crit]
        if not cr["passed"]:
            detail = ("(profiles: " + ",".join(cr["profiles_failed"]) + ")") \
                if cr["profiles_failed"] else "(no applicable evidence)"
            blockers.append(f"{crit} {detail}")

    cap = capital_preservation_report(readiness_state, bankroll=bankroll)
    ablation = build_ablation_report(evidence_by_profile)

    certificate = None
    live_ready = readiness_state in ReadinessState.LIVE_READY
    if overall_ready and live_ready:
        try:
            from ..micro_live.canary import CanaryCaps, issue_canary_certificate
            certificate = issue_canary_certificate(
                readiness_state, caps=caps or CanaryCaps(),
                config_hash="institutional_campaign",
                evidence={"criteria": {c: crit_results[c]["passed"]
                                       for c in CAMPAIGN_REQUIRED_CRITERIA}},
                dry_run=True, manual_enable=False)
        except Exception:  # noqa: BLE001 — certificate is best-effort, never enables live
            certificate = None

    return CampaignReport(
        profiles=results, criteria=crit_results, overall_ready=overall_ready,
        readiness_state=readiness_state, readiness_verdict=readiness_verdict,
        blockers=blockers, capital_preservation=cap, ablation=ablation,
        certificate=certificate)


# --------------------------------------------------------------------------- #
# ablation report (research / Chainlink are advisory, never load-bearing)
# --------------------------------------------------------------------------- #
def build_ablation_report(evidence_by_profile: dict) -> dict:
    """Measure the marginal contribution of research + Chainlink fair value, and
    flag whether the strategy stays profitable WITHOUT each advisory input. An
    advisory input that is load-bearing for after-cost edge is a robustness risk."""
    ev = dict(evidence_by_profile or {})
    full = ev.get("aggressive_learning", {}) or {}
    no_research = ev.get("no_research_ablation", {}) or {}
    no_chainlink = ev.get("no_chainlink_ablation", {}) or {}
    full_edge = _f(full.get("after_cost_expectancy"))
    nr_edge = _f(no_research.get("after_cost_expectancy"))
    nc_edge = _f(no_chainlink.get("after_cost_expectancy"))

    def _robust(ablated: dict, edge: float) -> bool:
        return edge > 0.0 and _f(ablated.get("realistic_fill_expectancy"),
                                 edge) > 0.0

    return {
        "research_contribution": round(full_edge - nr_edge, 8),
        "chainlink_contribution": round(full_edge - nc_edge, 8),
        "robust_without_research": _robust(no_research, nr_edge),
        "robust_without_chainlink": _robust(no_chainlink, nc_edge),
        "profiles": {
            "full": compute_profile_metrics(full),
            "no_research": compute_profile_metrics(no_research),
            "no_chainlink": compute_profile_metrics(no_chainlink),
        },
        "note": "Research + Chainlink are advisory; after-cost edge must survive their removal.",
    }


# --------------------------------------------------------------------------- #
# default (all-passing) evidence — used by tests + as a documented template
# --------------------------------------------------------------------------- #
def _good_profile_evidence(**over) -> dict:
    base = {
        "samples": 1200,
        "net_pnl": 180.0,
        "after_cost_expectancy": 0.020,
        "realistic_fill_expectancy": 0.012,
        "sharpe": 1.9, "sortino": 1.7, "calmar": 0.9, "omega": 1.6,
        "oos_sharpe": 1.8, "oos_sortino": 1.5, "oos_calmar": 0.8,
        "max_drawdown_pct": 0.08, "cvar": 0.04, "profit_factor": 1.8, "turnover": 2.5,
        "brier": 0.18, "log_loss": 0.52, "ece": 0.05, "calibration_error": 0.05,
        "ci_coverage": 0.95, "edge_decay": 0.10, "fill_quality": 0.92,
        "slippage_bps": 18.0, "markout": 0.004, "capital_efficiency": 0.05,
        "label_suppression_rate": 0.05, "unresolved_rate": 0.05, "ambiguous_rate": 0.05,
        "stale_data_rejection_rate": 0.0, "chainlink_stale": False, "stale_book": False,
        "risk_violations": 0, "downgraded": False,
        "bregman": {"opportunities": 5, "false_positive_rate": 0.0,
                    "partial_fill_hedge_break": False, "worst_case_pnl": 0.5,
                    "full_hedge_validated": True, "all_leg_fill_feasible": True},
    }
    base.update(over)
    return base


def default_campaign_evidence() -> dict:
    """A complete, all-passing evidence set for every profile. Tests mutate it to
    prove each gate blocks readiness; it also documents the expected evidence
    shape each profile must supply from real replay/training runs."""
    ev = {pid: _good_profile_evidence() for pid in CAMPAIGN_PROFILE_IDS}
    # Bregman-only profile leans on certified Bregman opportunities.
    ev["bregman_certified_only"]["bregman"]["opportunities"] = 40
    ev["bregman_plus_chainlink"]["bregman"]["opportunities"] = 35
    # ablation profiles: still profitable WITHOUT the advisory input (advisory only)
    ev["no_research_ablation"]["after_cost_expectancy"] = 0.016
    ev["no_chainlink_ablation"]["after_cost_expectancy"] = 0.017
    return ev


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def campaign_json(report: CampaignReport) -> str:
    return json.dumps(report.to_dict(), indent=2, default=str, sort_keys=True)


def campaign_markdown(report: CampaignReport) -> str:
    L: list = []
    a = L.append
    verdict = "READY (micro-live canary)" if report.overall_ready else "NOT READY"
    a("# Institutional validation campaign")
    a("")
    a("## Readiness verdict")
    a(f"- decision: **{verdict}**")
    a(f"- combined readiness state: **{report.readiness_state}**  ·  "
      f"live-escalation allowed: {report.readiness_verdict.get('allows_live_escalation')}")
    a(f"- canary certificate: {'ISSUED (dry-run, not enabled)' if report.certificate else 'NOT ISSUED'}")
    a(f"- hard blockers: {', '.join(report.blockers) or 'none'}")
    a("")
    a("## Hard criteria")
    for crit in CAMPAIGN_REQUIRED_CRITERIA:
        cr = report.criteria.get(crit, {})
        mark = "PASS" if cr.get("passed") else "FAIL"
        extra = ("" if cr.get("passed")
                 else f"  (failed: {', '.join(cr.get('profiles_failed', [])) or 'n/a'})")
        a(f"- {mark}  {crit}{extra}")
    a("")
    a("## Profiles")
    a("| profile | state | net_pnl | after_cost | realistic_fill | sharpe | "
      "sortino | calmar | maxDD | brier | ece | bregman_fp | passed |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for pid in CAMPAIGN_PROFILE_IDS:
        pr = report.profiles.get(pid)
        if not pr:
            continue
        m = pr.metrics
        a(f"| {pid} | {m['readiness_state']} | {m['net_pnl']} | "
          f"{m['after_cost_expectancy']} | {m['realistic_fill_expectancy']} | "
          f"{m['sharpe']} | {m['sortino']} | {m['calmar']} | {m['max_drawdown']} | "
          f"{m['brier']} | {m['ece']} | {m['bregman_fp_rate']} | {pr.passed} |")
    a("")
    abl = report.ablation or {}
    a("## Ablation (advisory inputs must not be load-bearing)")
    a(f"- research contribution: {abl.get('research_contribution')}  ·  "
      f"robust without research: {abl.get('robust_without_research')}")
    a(f"- Chainlink contribution: {abl.get('chainlink_contribution')}  ·  "
      f"robust without Chainlink: {abl.get('robust_without_chainlink')}")
    a("")
    cap = report.capital_preservation or {}
    a("## Capital preservation (bounds a FUTURE manual escalation; never auto-enables live)")
    a(f"- max initial live notional: {cap.get('max_initial_live_notional')}  ·  "
      f"max daily loss: {cap.get('max_daily_loss')}")
    a("")
    a("_PAPER ONLY. No live trading is enabled by this report._")
    return "\n".join(L) + "\n"

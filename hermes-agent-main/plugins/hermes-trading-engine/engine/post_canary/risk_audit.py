"""RiskAudit (Phase 10). Confirms RiskEngine + SafetyEnvelope decisions existed,
occurred before submit, were not bypassed, and that the kill switch was checked
and not active at submit. Missing risk/safety is a hard STOP (CRITICAL).

Quant scope — *Compliance/Security/Operational Excellence*: the audit that risk
was never bypassed is UNCHANGED. The paper risk/portfolio upgrade keeps
TrainingRiskGate + RiskEngine mandatory for every simulated order/bundle, so this
"risk-not-bypassed" invariant continues to hold end-to-end."""

from __future__ import annotations

from .schemas import RiskAuditResult, aggregate_status, make_check


def aggregate_risk_clean(results: list) -> dict:
    """Aggregate a set of per-attempt RiskAuditResults into a single
    risk-gate-cleanliness verdict for the live-readiness gate.

    Quant scope — *Compliance/Security/Operational Excellence*: clean == every
    audited submit had risk present, no bypass, and no limit breach. A single
    dirty audit blocks live escalation. Read-only; mirrors the existing
    "risk-not-bypassed" invariant across many decisions instead of one."""
    rs = list(results or [])
    bypass = sum(1 for r in rs if getattr(r, "bypass_detected", False))
    breach = sum(1 for r in rs if getattr(r, "limit_breach_detected", False))
    missing = sum(1 for r in rs if not getattr(r, "risk_approved", False))
    violations = bypass + breach + missing
    return {"audited": len(rs), "bypass": bypass, "limit_breach": breach,
            "missing_risk": missing, "violations": violations,
            "clean": violations == 0}


def run(ctx: dict, cfg) -> RiskAuditResult:
    a = ctx.get("attempt") or {}
    safety = ctx.get("safety_decision")
    events = ctx.get("audit_events") or []
    checks = []
    submit_ts = a.get("ts_ms")

    risk_id = a.get("risk_decision_id")
    checks.append(make_check("risk_decision_present", "PASS" if risk_id else "FAIL", "CRITICAL",
                             observed=risk_id))
    safety_allowed = bool(safety and int(safety.get("allowed", 0)))
    if cfg.require_safety_allowed:
        checks.append(make_check("safety_decision_present_and_allowed",
                                 "PASS" if safety_allowed else "FAIL", "CRITICAL",
                                 observed=bool(safety)))
    # decision before submit
    if safety and safety.get("ts_ms") is not None and submit_ts is not None:
        before = int(safety["ts_ms"]) <= int(submit_ts)
        checks.append(make_check("safety_decision_before_submit", "PASS" if before else "FAIL",
                                 "CRITICAL", observed=safety.get("ts_ms"), expected=f"<= {submit_ts}"))
    bypass = bool(ctx.get("bypass_detected"))
    checks.append(make_check("no_bypass_detected", "FAIL" if bypass else "PASS", "CRITICAL"))

    if cfg.require_kill_switch_check:
        checked = ctx.get("kill_switch_checked")
        if checked is None:
            checked = any(e.get("event_type") == "last_chance_before_submit" for e in events)
        checks.append(make_check("kill_switch_checked_before_submit",
                                 "PASS" if checked else "WARN", "WARN", observed=bool(checked)))
    if ctx.get("kill_switch_active_at_submit"):
        checks.append(make_check("kill_switch_not_active_at_submit", "FAIL", "CRITICAL",
                                 "kill switch active at submit"))

    breach = bool(ctx.get("limit_breach_detected"))
    checks.append(make_check("no_limit_breach", "FAIL" if breach else "PASS", "CRITICAL"))

    # Capital-allocation audit (Risk Management + Compliance): a clean canary must
    # never have funded a negative-expectancy strategy outside tiny exploration,
    # and the drawdown governor must not be in a pause/downgrade state.
    cap = ctx.get("capital_allocation") or {}
    if cap:
        leak = int(cap.get("negative_expectancy_leak", 0) or 0)
        checks.append(make_check("no_negative_expectancy_allocation",
                                 "FAIL" if leak else "PASS", "CRITICAL", observed=leak))
        gov_action = str((cap.get("drawdown_governor") or {}).get("action", "trade"))
        bad_gov = gov_action in ("pause_strategy", "downgrade_conservative")
        checks.append(make_check("drawdown_governor_not_tripped",
                                 "FAIL" if bad_gov else "PASS", "WARN", observed=gov_action))

    # Institutional validation campaign audit: a live escalation is permitted only
    # when the campaign marked the strategy READY (all seven hard criteria pass).
    campaign = ctx.get("campaign") or {}
    if campaign:
        ready = bool(campaign.get("overall_ready"))
        checks.append(make_check("institutional_campaign_ready",
                                 "PASS" if ready else "FAIL", "CRITICAL",
                                 observed=campaign.get("readiness_state"),
                                 reason="" if ready else "campaign not ready: "
                                 + ",".join(campaign.get("blockers", []))[:160]))

    # Micro-live CANARY audit (real-money prep; default disabled): a live canary
    # order must have carried a VALID readiness certificate and must NOT have run
    # while a rollback was active. Inert outside canary mode.
    canary = ctx.get("canary") or {}
    if canary:
        cert_ok = bool(canary.get("certificate_valid"))
        checks.append(make_check("canary_readiness_certificate_valid",
                                 "PASS" if cert_ok else "FAIL", "CRITICAL",
                                 observed=canary.get("certificate_id")))
        rolled = bool(canary.get("rolled_back"))
        checks.append(make_check("canary_not_rolled_back_at_submit",
                                 "FAIL" if rolled else "PASS", "CRITICAL", observed=rolled))

    return RiskAuditResult(
        status=aggregate_status(checks), checks=checks, risk_decision_id=risk_id,
        safety_envelope_decision_id=a.get("safety_envelope_decision_id"),
        risk_approved=bool(risk_id), safety_allowed=safety_allowed, bypass_detected=bypass,
        limit_breach_detected=breach)

"""Micro-live canary framework (real-money preparation, DISABLED by default).

This module builds a strictly-capped canary layer ON TOP of the existing Phase 8
guarded-live + Phase 9 micro-live control surface. It NEVER enables live trading
by default, never changes the existing risk gates, and only ever *tightens* what
is already there. A live canary order is impossible unless ALL of the following
hold simultaneously:

* a valid, unexpired **readiness certificate** (only mintable from a live-ready
  ``ReadinessState``) authorises canary operation,
* the explicit **manual-enable flag** is set AND **dry-run is turned off**,
* the deterministic **RiskEngine** approval is present (enforced by preflight),
* market data is **fresh**,
* the strategy is on the **canary allow-list** (default: certified Bregman +
  highest-confidence statistically-proven edge), with Bregman requiring a passing
  certification,
* every **canary capital cap** is satisfied (tiny notional, orders/day, daily
  loss, open / event / strategy exposure, Bregman bundle capital lock),
* there is **no active rollback**.

If anything degrades (drawdown, fill failure, slippage blowout, stale data,
settlement ambiguity, reconciliation mismatch, calibration deterioration, or a
risk violation) the canary **automatically rolls back** to paper/conservative
mode and writes a rollback kill switch that blocks any further live order.

Quant scope covered here:
* Data Acquisition & Ingestion / Preprocessing — freshness + market-status are
  read-only inputs; this layer never ingests or transforms market data itself.
* Statistical & Probabilistic Modeling — consumes the calibrated readiness
  verdict; only a live-ready verdict can mint a certificate.
* Signal Generation & Strategy Development w/ Bregman priority — the canary
  allow-list defaults to certified Bregman first + proven statistical edge.
* Risk Management & Portfolio Optimization — tiny hard caps + rollback governor.
* Backtesting & Simulation / Robustness — pure, deterministic, stdlib-only.
* CLOB v2 Execution — slippage / fill-failure rollback triggers.
* Live Trading & Monitoring — the canary report compares live fills to the
  realistic paper predictions; rollback on any monitored degradation.
* Compliance/Security/Operational Excellence — certificate is tamper-evident,
  every block carries an auditable reason, default remains disabled.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import (HARD_MAX_DAILY_NOTIONAL_USD, HARD_MAX_ORDER_NOTIONAL_USD,
                     HARD_MAX_ORDERS_PER_DAY)

try:  # canonical readiness states (no live trading is ever enabled here)
    from ..training.live_readiness import ReadinessState
    _LIVE_READY = set(ReadinessState.LIVE_READY)
except Exception:  # noqa: BLE001 — defensive fallback, keep canary self-contained
    _LIVE_READY = {"micro_canary_ready", "canary_ready"}

__all__ = [
    "ALLOWED_CANARY_STRATEGIES_DEFAULT", "CanaryCaps", "CanaryRollbackLimits",
    "CanaryReadinessCertificate", "CanaryAuthorization", "RollbackDecision",
    "CanaryConfig", "CanaryController", "issue_canary_certificate",
    "verify_canary_certificate", "authorize_canary_order", "evaluate_canary_rollback",
    "compare_fill_to_paper_prediction", "canary_comparison_report",
]

ALLOWED_CANARY_STRATEGIES_DEFAULT = ("certified_bregman", "statistical_proven")

ROLLBACK_TARGET_PAPER = "paper"
ROLLBACK_TARGET_CONSERVATIVE = "conservative"

_HARD_ORDER = float(HARD_MAX_ORDER_NOTIONAL_USD)
_HARD_DAILY = float(HARD_MAX_DAILY_NOTIONAL_USD)
_HARD_ORDERS = int(HARD_MAX_ORDERS_PER_DAY)
_BREGMAN_TOKENS = ("bregman",)


def _f(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _cert_secret() -> bytes:
    return (os.getenv("CANARY_CERT_SECRET", "hermes-canary-readiness-v1") or "x").encode()


# --------------------------------------------------------------------------- #
# capital caps (tiny, hard-capped in code — env can only make them smaller)
# --------------------------------------------------------------------------- #
@dataclass
class CanaryCaps:
    max_order_notional_usd: float = 1.0
    max_orders_per_day: int = 3
    max_daily_loss_usd: float = 1.0
    max_open_exposure_usd: float = 1.0
    max_event_exposure_usd: float = 1.0
    max_strategy_exposure_usd: float = 1.0
    max_bregman_bundle_capital_lock_usd: float = 1.0

    def __post_init__(self):
        # HARD code caps — money limits can never exceed the micro hard caps.
        self.max_order_notional_usd = min(max(0.0, _f(self.max_order_notional_usd)), _HARD_ORDER)
        self.max_daily_loss_usd = min(max(0.0, _f(self.max_daily_loss_usd)), _HARD_DAILY)
        self.max_open_exposure_usd = min(max(0.0, _f(self.max_open_exposure_usd)), _HARD_DAILY)
        self.max_event_exposure_usd = min(max(0.0, _f(self.max_event_exposure_usd)), _HARD_DAILY)
        self.max_strategy_exposure_usd = min(max(0.0, _f(self.max_strategy_exposure_usd)), _HARD_DAILY)
        self.max_bregman_bundle_capital_lock_usd = min(
            max(0.0, _f(self.max_bregman_bundle_capital_lock_usd)), _HARD_DAILY)
        self.max_orders_per_day = min(max(0, int(self.max_orders_per_day)), _HARD_ORDERS)

    @classmethod
    def from_config(cls, cfg) -> "CanaryCaps":
        g = lambda n, d: getattr(cfg, n, d)
        return cls(
            max_order_notional_usd=_f(g("canary_max_order_notional_usd", 1.0), 1.0),
            max_orders_per_day=int(g("canary_max_orders_per_day", 3)),
            max_daily_loss_usd=_f(g("canary_max_daily_loss_usd", 1.0), 1.0),
            max_open_exposure_usd=_f(g("canary_max_open_exposure_usd", 1.0), 1.0),
            max_event_exposure_usd=_f(g("canary_max_event_exposure_usd", 1.0), 1.0),
            max_strategy_exposure_usd=_f(g("canary_max_strategy_exposure_usd", 1.0), 1.0),
            max_bregman_bundle_capital_lock_usd=_f(
                g("canary_max_bregman_bundle_capital_lock_usd", 1.0), 1.0))

    def check(self, *, notional: float, orders_today: int = 0, daily_loss: float = 0.0,
              open_exposure: float = 0.0, event_exposure: float = 0.0,
              strategy_exposure: float = 0.0, bregman_bundle_lock: float = 0.0,
              strategy: str = "") -> tuple:
        n = _f(notional)
        if n <= 0.0:
            return False, "order_notional_non_positive"
        if n > self.max_order_notional_usd + 1e-9:
            return False, "order_notional_cap"
        if int(orders_today) >= self.max_orders_per_day:
            return False, "max_orders_per_day"
        if _f(daily_loss) >= self.max_daily_loss_usd - 1e-9:
            return False, "daily_loss_cap"
        if _f(open_exposure) + n > self.max_open_exposure_usd + 1e-9:
            return False, "open_exposure_cap"
        if _f(event_exposure) + n > self.max_event_exposure_usd + 1e-9:
            return False, "event_exposure_cap"
        if _f(strategy_exposure) + n > self.max_strategy_exposure_usd + 1e-9:
            return False, "strategy_exposure_cap"
        if any(tok in str(strategy).lower() for tok in _BREGMAN_TOKENS):
            if _f(bregman_bundle_lock) + n > self.max_bregman_bundle_capital_lock_usd + 1e-9:
                return False, "bregman_bundle_capital_lock_cap"
        return True, "ok"

    def to_dict(self) -> dict:
        return dict(self.__dict__)


# --------------------------------------------------------------------------- #
# rollback limits + decision
# --------------------------------------------------------------------------- #
@dataclass
class CanaryRollbackLimits:
    max_drawdown_usd: float = 1.0
    max_fill_failure_rate: float = 0.34
    max_slippage_bps: float = 150.0
    max_stale_ms: int = 750
    max_ambiguity_score: float = 0.20
    max_calibration_error: float = 0.15

    @classmethod
    def from_config(cls, cfg) -> "CanaryRollbackLimits":
        g = lambda n, d: getattr(cfg, n, d)
        return cls(
            max_drawdown_usd=_f(g("canary_max_drawdown_usd", 1.0), 1.0),
            max_fill_failure_rate=_f(g("canary_max_fill_failure_rate", 0.34), 0.34),
            max_slippage_bps=_f(g("canary_max_slippage_bps", 150.0), 150.0),
            max_stale_ms=int(g("canary_max_stale_ms", g("max_stale_ms", 750))),
            max_ambiguity_score=_f(g("canary_max_ambiguity_score", 0.20), 0.20),
            max_calibration_error=_f(g("canary_max_calibration_error", 0.15), 0.15))


@dataclass
class RollbackDecision:
    should_rollback: bool
    target_mode: str
    reasons: list = field(default_factory=list)
    triggers: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"should_rollback": self.should_rollback, "target_mode": self.target_mode,
                "reasons": list(self.reasons), "triggers": dict(self.triggers)}


def evaluate_canary_rollback(ctx: dict, *,
                             limits: Optional[CanaryRollbackLimits] = None) -> RollbackDecision:
    """Decide whether the canary must roll back to a safe (paper/conservative)
    mode. Rolls back on ANY monitored degradation. Pure + deterministic."""
    lim = limits or CanaryRollbackLimits()
    c = ctx or {}
    reasons: list = []
    triggers: dict = {}

    def trip(name: str, condition: bool, observed) -> None:
        triggers[name] = {"observed": observed, "tripped": bool(condition)}
        if condition:
            reasons.append(name)

    trip("drawdown_breach", _f(c.get("drawdown")) > lim.max_drawdown_usd, c.get("drawdown"))
    trip("fill_failure_spike",
         _f(c.get("fill_failure_rate")) > lim.max_fill_failure_rate, c.get("fill_failure_rate"))
    trip("slippage_blowout", _f(c.get("slippage_bps")) > lim.max_slippage_bps, c.get("slippage_bps"))
    trip("stale_data", int(_f(c.get("stale_ms"))) > lim.max_stale_ms, c.get("stale_ms"))
    trip("settlement_ambiguity",
         _f(c.get("ambiguity_score")) > lim.max_ambiguity_score, c.get("ambiguity_score"))
    trip("reconciliation_mismatch", not bool(c.get("reconciliation_clean", True)),
         c.get("reconciliation_clean", True))
    trip("calibration_deterioration",
         _f(c.get("calibration_error")) > lim.max_calibration_error, c.get("calibration_error"))
    trip("risk_violation", bool(c.get("risk_violation", False)), c.get("risk_violation", False))

    should = len(reasons) > 0
    # Severe degradations (capital / risk / position integrity) force a full stop
    # to paper; softer signals downgrade to conservative.
    severe = {"drawdown_breach", "risk_violation", "reconciliation_mismatch"}
    target = ROLLBACK_TARGET_PAPER if (severe & set(reasons)) else (
        ROLLBACK_TARGET_CONSERVATIVE if should else "live")
    return RollbackDecision(should_rollback=should, target_mode=target,
                            reasons=reasons, triggers=triggers)


# --------------------------------------------------------------------------- #
# readiness certificate (tamper-evident; only mintable from a live-ready state)
# --------------------------------------------------------------------------- #
@dataclass
class CanaryReadinessCertificate:
    certificate_id: str
    issued_ms: int
    expires_ms: int
    readiness_state: str
    allowed_strategies: tuple
    caps: dict
    config_hash: str
    evidence_hash: str
    issuer: str = "canary_framework"
    dry_run: bool = True
    manual_enable: bool = False
    signature: str = ""

    def _signed_fields(self) -> dict:
        return {
            "certificate_id": self.certificate_id, "issued_ms": int(self.issued_ms),
            "expires_ms": int(self.expires_ms), "readiness_state": self.readiness_state,
            "allowed_strategies": list(self.allowed_strategies), "caps": self.caps,
            "config_hash": self.config_hash, "evidence_hash": self.evidence_hash,
            "issuer": self.issuer, "dry_run": bool(self.dry_run),
            "manual_enable": bool(self.manual_enable),
        }

    def compute_signature(self) -> str:
        body = json.dumps(self._signed_fields(), sort_keys=True, default=str).encode()
        return hmac.new(_cert_secret(), body, hashlib.sha256).hexdigest()[:32]

    def to_dict(self) -> dict:
        d = self._signed_fields()
        d["signature"] = self.signature
        return d


def issue_canary_certificate(verdict_or_state, *, caps: CanaryCaps,
                             allowed_strategies=ALLOWED_CANARY_STRATEGIES_DEFAULT,
                             now_ms: Optional[int] = None, ttl_seconds: int = 3600,
                             config_hash: str = "", evidence: Optional[dict] = None,
                             dry_run: bool = True,
                             manual_enable: bool = False) -> Optional[CanaryReadinessCertificate]:
    """Mint a canary readiness certificate — ONLY when the readiness state is
    live-ready (``micro_canary_ready`` / ``canary_ready``). Returns ``None`` for
    any non-live-ready state. The certificate is tamper-evident (HMAC signature)
    and time-limited."""
    state = getattr(verdict_or_state, "state", verdict_or_state)
    if str(state) not in _LIVE_READY:
        return None
    # a verdict that explicitly disables live escalation can never mint a cert
    if hasattr(verdict_or_state, "allows_live_escalation") and \
            not bool(getattr(verdict_or_state, "allows_live_escalation")):
        return None
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    ev_hash = hashlib.sha256(
        json.dumps(evidence or {}, sort_keys=True, default=str).encode()).hexdigest()[:16]
    cert = CanaryReadinessCertificate(
        certificate_id="canarycert_" + uuid.uuid4().hex[:12], issued_ms=now,
        expires_ms=now + int(max(1, ttl_seconds)) * 1000, readiness_state=str(state),
        allowed_strategies=tuple(allowed_strategies), caps=caps.to_dict(),
        config_hash=str(config_hash), evidence_hash=ev_hash, dry_run=bool(dry_run),
        manual_enable=bool(manual_enable))
    cert.signature = cert.compute_signature()
    return cert


def verify_canary_certificate(cert: Optional[CanaryReadinessCertificate], *,
                              now_ms: Optional[int] = None,
                              expected_config_hash: Optional[str] = None) -> tuple:
    """Verify a certificate. Returns ``(ok, reason)``. Fails closed: a missing,
    tampered, expired, or non-live-ready certificate is rejected."""
    if cert is None:
        return False, "missing_certificate"
    try:
        if not hmac.compare_digest(cert.signature or "", cert.compute_signature()):
            return False, "signature_mismatch"
    except Exception:  # noqa: BLE001
        return False, "signature_error"
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    if now >= int(cert.expires_ms):
        return False, "expired"
    if str(cert.readiness_state) not in _LIVE_READY:
        return False, "state_not_live_ready"
    if expected_config_hash is not None and str(cert.config_hash) != str(expected_config_hash):
        return False, "config_hash_mismatch"
    return True, "ok"


# --------------------------------------------------------------------------- #
# authorization gate
# --------------------------------------------------------------------------- #
@dataclass
class CanaryAuthorization:
    allowed: bool
    reasons: list = field(default_factory=list)
    checks: dict = field(default_factory=dict)
    dry_run: bool = True
    target_mode: str = "paper"

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "reasons": list(self.reasons),
                "checks": dict(self.checks), "dry_run": self.dry_run,
                "target_mode": self.target_mode}


def authorize_canary_order(ctx: dict, *, caps: Optional[CanaryCaps] = None,
                           max_stale_ms: int = 750,
                           now_ms: Optional[int] = None) -> CanaryAuthorization:
    """The authoritative canary order gate. Authorizes a live order ONLY when
    every prerequisite is satisfied; otherwise blocks and falls back to paper.

    Required (in order): valid readiness certificate, manual-enable flag, dry-run
    OFF, RiskEngine approval, SafetyEnvelope approval, fresh market data, an
    allowed (Bregman-certified / proven-statistical) strategy, the canary caps,
    and no active rollback."""
    ctx = dict(ctx or {})
    caps = caps or CanaryCaps()
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    checks: dict = {}
    reasons: list = []

    def chk(name: str, ok: bool, reason: str) -> None:
        checks[name] = bool(ok)
        if not ok:
            reasons.append(reason)

    cert = ctx.get("certificate")
    if cert is None:
        chk("readiness_certificate", False, "no_readiness_certificate")
        allowed_strategies = ALLOWED_CANARY_STRATEGIES_DEFAULT
    else:
        cok, creason = verify_canary_certificate(cert, now_ms=now)
        chk("readiness_certificate", cok, "certificate_invalid:" + creason)
        allowed_strategies = tuple(getattr(cert, "allowed_strategies", None)
                                   or ALLOWED_CANARY_STRATEGIES_DEFAULT)

    chk("manual_enable", bool(ctx.get("manual_enable", False)), "manual_enable_required")
    dry = bool(ctx.get("dry_run", True))
    chk("live_not_dry_run", not dry, "dry_run_mode")
    chk("risk_approved", bool(ctx.get("risk_approved", False)), "risk_not_approved")
    chk("safety_allowed", bool(ctx.get("safety_allowed", True)), "safety_not_allowed")
    chk("market_data_fresh", int(_f(ctx.get("stale_ms"))) <= int(max_stale_ms), "stale_market_data")

    strat = str(ctx.get("strategy", "")).lower()
    allowed_list = [s.lower() for s in allowed_strategies]
    chk("strategy_allowed", strat in allowed_list, "strategy_not_allowed")
    if any(tok in strat for tok in _BREGMAN_TOKENS):
        chk("bregman_certified", bool(ctx.get("bregman_certified", False)), "bregman_not_certified")

    caps_ok, caps_reason = caps.check(
        notional=_f(ctx.get("notional")), orders_today=int(_f(ctx.get("orders_today"))),
        daily_loss=_f(ctx.get("daily_loss")), open_exposure=_f(ctx.get("open_exposure")),
        event_exposure=_f(ctx.get("event_exposure")),
        strategy_exposure=_f(ctx.get("strategy_exposure")),
        bregman_bundle_lock=_f(ctx.get("bregman_bundle_lock")), strategy=strat)
    chk("canary_caps", caps_ok, "cap_breach:" + caps_reason)

    chk("no_active_rollback", not bool(ctx.get("rolled_back", False)), "rollback_active")

    allowed = all(checks.values())
    return CanaryAuthorization(allowed=allowed, reasons=reasons, checks=checks, dry_run=dry,
                               target_mode="live" if allowed else ROLLBACK_TARGET_PAPER)


# --------------------------------------------------------------------------- #
# canary config (DISABLED by default) + stateful controller
# --------------------------------------------------------------------------- #
def _envb(name, d=False) -> bool:
    return os.getenv(name, "1" if d else "0") not in ("0", "false", "False", "")


def _envf(name, d) -> float:
    try:
        return float(os.getenv(name, str(d)))
    except (TypeError, ValueError):
        return d


def _envi(name, d) -> int:
    try:
        return int(os.getenv(name, str(d)))
    except (TypeError, ValueError):
        return d


@dataclass
class CanaryConfig:
    enabled: bool = False            # master canary switch (DEFAULT OFF)
    dry_run: bool = True             # DEFAULT dry-run -> no real orders
    manual_enable: bool = False      # explicit manual enable (DEFAULT OFF)
    require_certificate: bool = True  # a live order ALWAYS needs a certificate
    certificate_ttl_seconds: int = 3600
    allowed_strategies: tuple = ALLOWED_CANARY_STRATEGIES_DEFAULT
    rollback_kill_switch_path: str = "./CANARY_ROLLBACK_KILL_SWITCH"
    caps: CanaryCaps = field(default_factory=CanaryCaps)
    rollback_limits: CanaryRollbackLimits = field(default_factory=CanaryRollbackLimits)

    @classmethod
    def from_env(cls) -> "CanaryConfig":
        caps = CanaryCaps(
            max_order_notional_usd=_envf("MICRO_LIVE_CANARY_MAX_ORDER_NOTIONAL_USD", 1.0),
            max_orders_per_day=_envi("MICRO_LIVE_CANARY_MAX_ORDERS_PER_DAY", 3),
            max_daily_loss_usd=_envf("MICRO_LIVE_CANARY_MAX_DAILY_LOSS_USD", 1.0),
            max_open_exposure_usd=_envf("MICRO_LIVE_CANARY_MAX_OPEN_EXPOSURE_USD", 1.0),
            max_event_exposure_usd=_envf("MICRO_LIVE_CANARY_MAX_EVENT_EXPOSURE_USD", 1.0),
            max_strategy_exposure_usd=_envf("MICRO_LIVE_CANARY_MAX_STRATEGY_EXPOSURE_USD", 1.0),
            max_bregman_bundle_capital_lock_usd=_envf(
                "MICRO_LIVE_CANARY_MAX_BREGMAN_BUNDLE_LOCK_USD", 1.0))
        rl = CanaryRollbackLimits(
            max_drawdown_usd=_envf("MICRO_LIVE_CANARY_MAX_DRAWDOWN_USD", 1.0),
            max_fill_failure_rate=_envf("MICRO_LIVE_CANARY_MAX_FILL_FAILURE_RATE", 0.34),
            max_slippage_bps=_envf("MICRO_LIVE_CANARY_MAX_SLIPPAGE_BPS", 150.0),
            max_stale_ms=_envi("MICRO_LIVE_CANARY_MAX_STALE_MS", 750),
            max_ambiguity_score=_envf("MICRO_LIVE_CANARY_MAX_AMBIGUITY_SCORE", 0.20),
            max_calibration_error=_envf("MICRO_LIVE_CANARY_MAX_CALIBRATION_ERROR", 0.15))
        strategies = [s.strip() for s in os.getenv(
            "MICRO_LIVE_CANARY_ALLOWED_STRATEGIES",
            ",".join(ALLOWED_CANARY_STRATEGIES_DEFAULT)).split(",") if s.strip()]
        return cls(
            enabled=_envb("MICRO_LIVE_CANARY_ENABLED", False),
            dry_run=_envb("MICRO_LIVE_CANARY_DRY_RUN", True),
            manual_enable=_envb("MICRO_LIVE_CANARY_MANUAL_ENABLE", False),
            require_certificate=_envb("MICRO_LIVE_CANARY_REQUIRE_CERTIFICATE", True),
            certificate_ttl_seconds=_envi("MICRO_LIVE_CANARY_CERT_TTL_SECONDS", 3600),
            allowed_strategies=tuple(strategies or ALLOWED_CANARY_STRATEGIES_DEFAULT),
            rollback_kill_switch_path=os.getenv("CANARY_ROLLBACK_KILL_SWITCH_PATH",
                                                "./CANARY_ROLLBACK_KILL_SWITCH"),
            caps=caps, rollback_limits=rl)


class CanaryController:
    """Stateful canary controller: authorizes live orders, monitors for
    degradation, and engages an automatic rollback (writes a rollback kill
    switch) that blocks any further live order until manually cleared."""

    def __init__(self, *, config: Optional[CanaryConfig] = None,
                 rollback_kill_switch_path: Optional[str] = None,
                 caps: Optional[CanaryCaps] = None,
                 limits: Optional[CanaryRollbackLimits] = None):
        self.cfg = config or CanaryConfig()
        self.caps = caps or self.cfg.caps
        self.limits = limits or self.cfg.rollback_limits
        self.ks_path = rollback_kill_switch_path or self.cfg.rollback_kill_switch_path
        self.last_rollback: Optional[RollbackDecision] = None

    def is_rolled_back(self) -> bool:
        try:
            return bool(self.ks_path) and Path(self.ks_path).exists()
        except OSError:
            return False

    def live_blocked(self) -> bool:
        return self.is_rolled_back()

    def engage_rollback(self, decision: RollbackDecision) -> None:
        self.last_rollback = decision
        try:
            p = Path(self.ks_path)
            p.write_text(json.dumps(decision.to_dict(), default=str), encoding="utf-8")
        except OSError:
            pass

    def check_and_rollback(self, ctx: dict) -> RollbackDecision:
        decision = evaluate_canary_rollback(ctx, limits=self.limits)
        if decision.should_rollback:
            self.engage_rollback(decision)
        return decision

    def authorize(self, ctx: dict, *, now_ms: Optional[int] = None) -> CanaryAuthorization:
        ctx = dict(ctx or {})
        if self.is_rolled_back():
            ctx["rolled_back"] = True
        return authorize_canary_order(ctx, caps=self.caps,
                                      max_stale_ms=int(self.limits.max_stale_ms), now_ms=now_ms)

    def status(self) -> dict:
        return {"enabled": bool(self.cfg.enabled), "dry_run": bool(self.cfg.dry_run),
                "manual_enable": bool(self.cfg.manual_enable),
                "require_certificate": bool(self.cfg.require_certificate),
                "rolled_back": self.is_rolled_back(),
                "rollback_kill_switch_path": self.ks_path,
                "allowed_strategies": list(self.cfg.allowed_strategies),
                "caps": self.caps.to_dict(),
                "last_rollback": self.last_rollback.to_dict() if self.last_rollback else None}


# --------------------------------------------------------------------------- #
# canary report — live fills vs realistic paper predictions
# --------------------------------------------------------------------------- #
def compare_fill_to_paper_prediction(live_fill: dict, paper_prediction: dict, *,
                                     price_tolerance: float = 0.02,
                                     slippage_tolerance_bps: float = 100.0) -> dict:
    """Compare a realised live fill to the realistic PAPER prediction made before
    submission (CLOB v2 forward estimate). Surfaces fill-probability realism,
    slippage forecast error, and price error so an optimistic paper model is
    caught early. Read-only analytics."""
    lf = live_fill or {}
    pp = paper_prediction or {}
    pred_fill_p = _f(pp.get("fill_probability"), 0.0)
    realized_filled = 1.0 if (_f(lf.get("filled_quantity")) > 0 or lf.get("filled")) else 0.0
    pred_slip = _f(pp.get("slippage_forecast_bps", pp.get("slippage_bps")), 0.0)
    realized_slip = _f(lf.get("slippage_bps"), 0.0)
    pred_price = _f(pp.get("predicted_price", pp.get("price")), 0.0)
    realized_price = _f(lf.get("avg_fill_price", lf.get("fill_price")), 0.0)
    price_err = round(abs(realized_price - pred_price), 6) if (pred_price and realized_price) else 0.0
    slip_err = round(realized_slip - pred_slip, 4)
    within = (price_err <= price_tolerance) and (abs(slip_err) <= slippage_tolerance_bps) \
        and (realized_filled >= 1.0 or pred_fill_p < 0.5)
    return {
        "market_id": lf.get("market_id") or pp.get("market_id"),
        "predicted_fill_probability": round(pred_fill_p, 6),
        "realized_filled": realized_filled,
        "predicted_slippage_bps": round(pred_slip, 4),
        "realized_slippage_bps": round(realized_slip, 4),
        "slippage_forecast_error_bps": slip_err,
        "predicted_price": round(pred_price, 6), "realized_price": round(realized_price, 6),
        "price_error": price_err,
        "within_tolerance": bool(within),
    }


def canary_comparison_report(comparisons: list) -> dict:
    """Aggregate per-fill live-vs-paper comparisons into a canary report
    (Live Trading & Monitoring + Robustness)."""
    rows = list(comparisons or [])
    n = len(rows)
    if not n:
        return {"count": 0, "fills_compared": 0, "mean_slippage_forecast_error_bps": 0.0,
                "mean_price_error": 0.0, "within_tolerance_rate": 0.0,
                "predicted_fill_rate": 0.0, "realized_fill_rate": 0.0, "rows": []}
    mean_slip_err = round(sum(_f(r.get("slippage_forecast_error_bps")) for r in rows) / n, 4)
    mean_price_err = round(sum(_f(r.get("price_error")) for r in rows) / n, 6)
    within = round(sum(1 for r in rows if r.get("within_tolerance")) / n, 6)
    pred_fill = round(sum(_f(r.get("predicted_fill_probability")) for r in rows) / n, 6)
    realized_fill = round(sum(_f(r.get("realized_filled")) for r in rows) / n, 6)
    return {"count": n, "fills_compared": n,
            "mean_slippage_forecast_error_bps": mean_slip_err,
            "mean_price_error": mean_price_err, "within_tolerance_rate": within,
            "predicted_fill_rate": pred_fill, "realized_fill_rate": realized_fill,
            "rows": rows}

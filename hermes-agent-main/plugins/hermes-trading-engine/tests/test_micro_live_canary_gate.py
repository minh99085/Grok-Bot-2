"""Micro-live canary authorization gate.

Quant scope — *Compliance/Security/Operational Excellence* + *Risk Management*:
proves a live canary order is authorized ONLY when EVERY gate passes — a valid
readiness certificate, the explicit manual-enable flag, dry-run turned off, a
valid risk approval, fresh market data, an allowed (certified-Bregman /
proven-statistical) strategy, the canary caps, and no active rollback. Any single
missing prerequisite blocks the order and falls back to paper. Default disabled.
"""

from __future__ import annotations

import time

from engine.micro_live.canary import (authorize_canary_order, CanaryCaps,
                                       issue_canary_certificate)
from engine.micro_live.config import MicroLiveConfig
from engine.micro_live.safety import MicroSafetyEnvelope
from engine.training.live_readiness import ReadinessState


def _cert():
    return issue_canary_certificate(ReadinessState.MICRO_CANARY_READY, caps=CanaryCaps(),
                                    now_ms=int(time.time() * 1000), config_hash="cfg")


def _good_ctx(**over):
    ctx = {
        "certificate": _cert(),
        "manual_enable": True,
        "dry_run": False,
        "risk_approved": True,
        "safety_allowed": True,
        "stale_ms": 0,
        "strategy": "certified_bregman",
        "bregman_certified": True,
        "notional": 0.5, "orders_today": 0, "daily_loss": 0.0,
        "open_exposure": 0.0, "event_exposure": 0.0, "strategy_exposure": 0.0,
        "bregman_bundle_lock": 0.0, "rolled_back": False,
    }
    ctx.update(over)
    return ctx


def test_fully_valid_context_is_authorized():
    auth = authorize_canary_order(_good_ctx(), caps=CanaryCaps())
    assert auth.allowed is True
    assert auth.reasons == []
    assert auth.target_mode == "live"


def test_missing_manual_enable_blocks():
    auth = authorize_canary_order(_good_ctx(manual_enable=False), caps=CanaryCaps())
    assert auth.allowed is False
    assert any("manual" in r for r in auth.reasons)
    assert auth.target_mode == "paper"


def test_dry_run_blocks_live_order():
    auth = authorize_canary_order(_good_ctx(dry_run=True), caps=CanaryCaps())
    assert auth.allowed is False
    assert any("dry_run" in r for r in auth.reasons)


def test_dry_run_is_the_default_when_unspecified():
    ctx = _good_ctx()
    ctx.pop("dry_run")  # unspecified -> must default to dry-run (no live order)
    auth = authorize_canary_order(ctx, caps=CanaryCaps())
    assert auth.allowed is False
    assert any("dry_run" in r for r in auth.reasons)


def test_risk_not_approved_blocks():
    auth = authorize_canary_order(_good_ctx(risk_approved=False), caps=CanaryCaps())
    assert auth.allowed is False
    assert any("risk" in r for r in auth.reasons)


def test_stale_market_data_blocks():
    auth = authorize_canary_order(_good_ctx(stale_ms=10_000), caps=CanaryCaps())
    assert auth.allowed is False
    assert any("stale" in r for r in auth.reasons)


def test_disallowed_strategy_blocks():
    auth = authorize_canary_order(_good_ctx(strategy="directional"), caps=CanaryCaps())
    assert auth.allowed is False
    assert any("strategy" in r for r in auth.reasons)


def test_uncertified_bregman_blocks():
    auth = authorize_canary_order(_good_ctx(strategy="certified_bregman",
                                            bregman_certified=False), caps=CanaryCaps())
    assert auth.allowed is False
    assert any("bregman" in r or "strategy" in r for r in auth.reasons)


def test_cap_breach_blocks():
    auth = authorize_canary_order(_good_ctx(notional=5.0), caps=CanaryCaps())
    assert auth.allowed is False
    assert any("cap" in r or "notional" in r for r in auth.reasons)


def test_active_rollback_blocks():
    auth = authorize_canary_order(_good_ctx(rolled_back=True), caps=CanaryCaps())
    assert auth.allowed is False
    assert any("rollback" in r for r in auth.reasons)


# --- MicroSafetyEnvelope consumes the certificate in canary mode ----------- #
def _safety_ctx(**over):
    ctx = {
        "locks_ok": True, "environment": "demo", "venue": "kalshi", "market_ref": "TEST",
        "order_type": "FOK", "time_in_force": "fill_or_kill", "notional": 0.5,
        "market_exposure": 0, "venue_exposure": 0, "total_exposure": 0, "daily_loss": 0,
        "edge_after_costs": 0.2, "stale_ms": 0, "spread": 0.0, "orderbook_valid": True,
        "venue_status": "ready", "market_status": "open", "ambiguity_score": 0.0,
        "evidence_score": 0.8, "source_count": 3, "canary_mode": True,
        "strategy": "certified_bregman", "bregman_certified": True,
    }
    ctx.update(over)
    return ctx


def test_safety_envelope_blocks_canary_without_certificate(monkeypatch):
    monkeypatch.setenv("MICRO_LIVE_ALLOWED_VENUES", "kalshi")
    cfg = MicroLiveConfig.from_env()
    decision = MicroSafetyEnvelope(cfg).validate(_safety_ctx(canary_certificate=None))
    assert decision.allowed is False
    assert decision.checks.get("canary_certificate_valid") is False


def test_safety_envelope_accepts_canary_with_valid_certificate(monkeypatch):
    monkeypatch.setenv("MICRO_LIVE_ALLOWED_VENUES", "kalshi")
    cfg = MicroLiveConfig.from_env()
    decision = MicroSafetyEnvelope(cfg).validate(_safety_ctx(canary_certificate=_cert()))
    assert decision.checks.get("canary_certificate_valid") is True

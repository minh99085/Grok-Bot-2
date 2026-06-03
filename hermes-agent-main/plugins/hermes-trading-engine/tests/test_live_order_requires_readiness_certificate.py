"""A live canary order is impossible without a valid readiness certificate.

Quant scope — *Compliance/Security/Operational Excellence* + *Live Trading &
Monitoring*: proves a readiness certificate is REQUIRED for any live canary
order, that the certificate is only issued for a live-ready readiness state, that
it is verified (tamper + expiry), and that the real micro-live execution path is
blocked when the certificate is absent. Default is disabled; no certificate ->
no live order — ever.
"""

from __future__ import annotations

import time

import pytest

from engine.micro_live.canary import (authorize_canary_order, CanaryCaps,
                                       issue_canary_certificate,
                                       verify_canary_certificate)
from engine.training.live_readiness import ReadinessState


def _cert(now=None, **over):
    now = now or int(time.time() * 1000)
    return issue_canary_certificate(
        over.pop("state", ReadinessState.MICRO_CANARY_READY),
        caps=CanaryCaps(), now_ms=now, ttl_seconds=over.pop("ttl_seconds", 3600),
        config_hash=over.pop("config_hash", "cfg"), **over)


def test_certificate_only_issued_for_live_ready_states():
    assert _cert(state=ReadinessState.MICRO_CANARY_READY) is not None
    assert _cert(state=ReadinessState.CANARY_READY) is not None
    # non-live-ready states cannot mint a certificate
    assert _cert(state=ReadinessState.PAPER_QUALIFIED) is None
    assert _cert(state=ReadinessState.PAPER_LEARNING) is None
    assert _cert(state=ReadinessState.BLOCKED) is None


def test_valid_certificate_verifies():
    cert = _cert()
    ok, reason = verify_canary_certificate(cert)
    assert ok is True
    assert reason == "ok"


def test_missing_certificate_fails_verification():
    ok, reason = verify_canary_certificate(None)
    assert ok is False
    assert "missing" in reason or "no_" in reason


def test_expired_certificate_fails_verification():
    now = int(time.time() * 1000)
    cert = _cert(now=now - 7_200_000, ttl_seconds=3600)  # issued 2h ago, 1h ttl
    ok, reason = verify_canary_certificate(cert, now_ms=now)
    assert ok is False
    assert "expired" in reason


def test_tampered_certificate_fails_verification():
    cert = _cert()
    cert.caps["max_order_notional_usd"] = 1000.0  # tamper to lift the cap
    ok, reason = verify_canary_certificate(cert)
    assert ok is False
    assert "signature" in reason or "tamper" in reason


def test_authorize_without_certificate_is_blocked():
    auth = authorize_canary_order({
        "manual_enable": True, "dry_run": False, "risk_approved": True,
        "strategy": "certified_bregman", "bregman_certified": True, "stale_ms": 0,
    }, caps=CanaryCaps())
    assert auth.allowed is False
    assert any("certificate" in r for r in auth.reasons)


# --------------------------------------------------------------------------- #
# real micro-live execution path: no certificate -> blocked
# --------------------------------------------------------------------------- #
ACK = "I ACCEPT MICRO LIVE REAL MONEY RISK"
CONFIRM = "SUBMIT ONE MICRO LIVE CANARY ORDER"


@pytest.fixture
def store(tmp_path):
    from engine.storage import Store
    return Store(tmp_path / "ml.db")


@pytest.fixture
def canary_open_env(monkeypatch):
    from engine.micro_live import locks as ml_locks
    monkeypatch.setattr(ml_locks, "BUILD_ENABLED", True)
    monkeypatch.setenv("MICRO_LIVE_ENABLED", "1")
    monkeypatch.setenv("MICRO_LIVE_ACKNOWLEDGE_REAL_MONEY_RISK", ACK)
    monkeypatch.setenv("KALSHI_MICRO_LIVE_ENABLED", "1")
    monkeypatch.setenv("MICRO_LIVE_CANARY_ENABLED", "1")  # engage canary framework
    monkeypatch.delenv("MICRO_LIVE_KILL_SWITCH_PATH", raising=False)
    return True


def _seed_ready(store, now):
    store.add_conformance_run({"conformance_run_id": "cr", "started_ts_ms": now,
                               "finished_ts_ms": now, "status": "PASS", "config_hash": "x",
                               "test_count": 1, "pass_count": 1, "fail_count": 0,
                               "warning_count": 0, "report_path": None})
    store.add_readiness_report({"report_id": "rr", "shadow_session_id": "s", "generated_ts_ms": now,
                                "overall_status": "READY_FOR_MANUAL_REVIEW", "summary_json": {},
                                "report_path": None})
    store.add_dry_run_order_intent({
        "dry_run_intent_id": "dri", "ts_ms": now, "venue": "kalshi", "market_id": "M",
        "market_ticker": "TEST-MKT", "asset_id": None, "outcome": "YES", "side": "BUY",
        "order_type": "FOK", "limit_price": "0.50", "quantity": "1", "notional": "0.50",
        "internal_order_request_json": "{}", "venue_payload_json": "{}", "unsigned": 1,
        "unsent": 1, "signer_used": 0, "network_called": 0, "risk_decision_id": "rd",
        "safety_envelope_decision_id": "se", "oms_order_id": None, "status": "CREATED",
        "reason": None})


def test_execution_path_blocks_without_certificate(store, canary_open_env):
    from engine.micro_live.canary_plan import create_canary_plan
    from engine.micro_live.config import MicroLiveConfig
    from engine.micro_live.execution_service import (FixtureSigner,
                                                     MicroLiveExecutionService,
                                                     fixture_transport)
    now = int(time.time() * 1000)
    _seed_ready(store, now)
    plan, _ = create_canary_plan(store, MicroLiveConfig.from_env(), dry_run_intent_id="dri",
                                 readiness_report_id="rr", venue="kalshi", environment="demo",
                                 approval_batch_id="ab", arming_token_id="at", now_ms=now)
    svc = MicroLiveExecutionService(store, MicroLiveConfig.from_env())
    # canary engaged, manual-enable + non-dry-run requested, but NO certificate
    res = svc.submit_canary_order(
        plan.canary_plan_id, arming_token="tok", confirm=CONFIRM,
        market_ctx={"edge_after_costs": 0.2, "spread": 0.0, "stale_ms": 0,
                    "venue_status": "ready", "market_status": "open", "evidence_score": 0.8,
                    "source_count": 3, "ambiguity_score": 0.0,
                    "canary_manual_enable": True, "canary_dry_run": False,
                    "strategy": "certified_bregman", "bregman_certified": True},
        transport=fixture_transport(fill=True), signer=FixtureSigner(),
        non_interactive_test_fixture=True, now_ms=now)
    assert res.get("submitted") is not True
    assert res.get("blocked") is True
    assert "certificate" in str(res.get("reason", "")).lower()

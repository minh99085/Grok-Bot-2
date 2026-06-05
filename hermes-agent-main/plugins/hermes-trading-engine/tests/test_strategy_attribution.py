"""Tests for strategy-attribution audit fields + the canonical AlgorithmicEdgeAudit
required-field validation and readiness caps."""

from __future__ import annotations

from engine.strategies.strategy_attribution import (
    ATTRIBUTION_AUDIT_REQUIRED,
    attribution_audit,
    missing_attribution_fields,
)
from engine.fill_realism import missing_fill_realism_fields
from engine.arbitrage.certificate import missing_bregman_fields
from engine.edge_audit import (
    CAP_BREGMAN_INACTIVE,
    CAP_REALISM_OR_AFTERCOST_MISSING,
    CAP_TESTS_NOT_GREEN,
    AlgorithmicEdgeAudit,
)


# --- per-section required-field validators ----------------------------------
def test_missing_attribution_fields_flags_nulls():
    assert missing_attribution_fields({}) == [
        "strategy_attribution.gross_pnl", "strategy_attribution.after_cost_pnl",
        "strategy_attribution.win_rate"]
    full = {"gross_pnl": 1.0, "after_cost_pnl": 0.5, "win_rate": 0.6}
    assert missing_attribution_fields(full) == []
    assert set(ATTRIBUTION_AUDIT_REQUIRED) == {"gross_pnl", "after_cost_pnl", "win_rate"}


def test_missing_fill_realism_fields():
    assert missing_fill_realism_fields({}) == ["fill_realism.fantasy_fills_rejected"]
    assert missing_fill_realism_fields({"fantasy_fills_rejected": 0}) == []


def test_missing_bregman_fields():
    assert "bregman.certified_arbitrages" in missing_bregman_fields({})
    full = {"constraint_groups_scanned": 10, "candidate_arbitrages": 2,
            "certified_arbitrages": 1, "executable_depth_certified": 1}
    assert missing_bregman_fields(full) == []


# --- attribution_audit edges + splits ---------------------------------------
def test_attribution_audit_basic():
    recs = [{"strategy": "bregman", "pnl": 2.0, "after_cost_pnl": 1.6,
             "edge_entry": 0.05, "edge_realized": 0.04, "is_open": False}]
    a = attribution_audit(recs, rejected_trades=2, open_exposure=5.0)
    assert a["gross_pnl"] == 2.0 and a["after_cost_pnl"] == 1.6
    assert a["rejected_trades"] == 2 and a["open_exposure"] == 5.0


# --- canonical model: required fields, hard failures, caps ------------------
def _full_sections():
    return dict(
        strategy_attribution={"gross_pnl": 1.0, "after_cost_pnl": 0.5, "win_rate": 0.6},
        bregman={"constraint_groups_scanned": 10, "candidate_arbitrages": 2,
                 "certified_arbitrages": 1, "executable_depth_certified": 1},
        fill_realism={"fantasy_fills_rejected": 3},
        calibration={"brier": 0.2},
        risk={"max_drawdown": 0.1},
        execution={"clob_v2_executable": True},
        readiness={"production_readiness_score": 80},
    )


def _audit(**over):
    s = _full_sections()
    kwargs = dict(bregman_enabled=True, tests_passing=True, equity_mismatch_pct=0.0,
                  raw_readiness_score=80.0)
    kwargs.update(over)
    return AlgorithmicEdgeAudit(**s, **kwargs)


def test_model_ok_when_complete():
    a = _audit()
    assert a.ok() is True
    assert a.required_field_violations() == []
    assert a.hard_failures() == []
    assert a.readiness_cap() == 100
    assert a.capped_readiness_score() == 80.0


def test_model_required_field_violation_breaks_ok():
    s = _full_sections()
    s["calibration"] = {}  # missing brier
    a = AlgorithmicEdgeAudit(**s, bregman_enabled=True, tests_passing=True,
                             raw_readiness_score=80.0)
    assert "calibration.brier" in a.required_field_violations()
    assert a.ok() is False


def test_model_bregman_disabled_caps_below_40():
    a = _audit(bregman_enabled=False)
    assert a.readiness_cap() == CAP_BREGMAN_INACTIVE
    assert a.capped_readiness_score() <= 39
    assert "bregman_disabled" in a.hard_failures()


def test_model_zero_scans_caps_below_40():
    s = _full_sections()
    s["bregman"]["constraint_groups_scanned"] = 0
    a = AlgorithmicEdgeAudit(**s, bregman_enabled=True, tests_passing=True,
                             raw_readiness_score=80.0)
    assert a.readiness_cap() == CAP_BREGMAN_INACTIVE
    assert "bregman_zero_groups_scanned" in a.hard_failures()


def test_model_pytest_red_caps_below_50():
    a = _audit(tests_passing=False)
    assert a.readiness_cap() == CAP_TESTS_NOT_GREEN
    assert "pytest_failed" in a.hard_failures()


def test_model_missing_realism_caps_below_60():
    s = _full_sections()
    s["fill_realism"] = {}
    a = AlgorithmicEdgeAudit(**s, bregman_enabled=True, tests_passing=True,
                             raw_readiness_score=80.0)
    assert a.readiness_cap() == CAP_REALISM_OR_AFTERCOST_MISSING
    assert "fill_realism_null" in a.hard_failures()


def test_model_capped_score_reports_cap_when_raw_unknown():
    a = _audit(bregman_enabled=False, raw_readiness_score=None)
    assert a.capped_readiness_score() == float(CAP_BREGMAN_INACTIVE)


def test_model_equity_mismatch_hard_failure():
    a = _audit(equity_mismatch_pct=2.5)
    assert "dashboard_equity_mismatch_gt_1pct" in a.hard_failures()
    assert a.ok() is False


def test_model_to_dict_shape():
    d = _audit().to_dict()
    assert set(d["sections"]) == {
        "strategy_attribution", "bregman", "fill_realism", "calibration",
        "risk", "execution", "readiness"}
    assert "hard_failures" in d and "readiness_cap" in d

"""Tests for the mandatory Algorithmic Edge Audit (metrics + engine helpers + report).

Covers all seven sections, loud failure on missing/stale core fields, the engine
diagnostics helpers that feed it, and the report wiring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_bot_inspection_report as gen  # noqa: E402
import inspection_metrics as metrics  # noqa: E402
import inspection_recommendations as recs  # noqa: E402

from engine.arbitrage.constraint_graph import ConstraintGraph, Outcome  # noqa: E402
from engine.strategies.bregman import BregmanStrategy  # noqa: E402
from engine.fill_realism import assess_fill, fill_audit_fields  # noqa: E402
from engine.training.btc_pulse import pulse_audit_fields  # noqa: E402
from engine.strategies.strategy_attribution import attribution_audit  # noqa: E402


def _full_status():
    """A status carrying every core audit field (decision-grade)."""
    return {
        "generated_at": None,
        "pnl": {"gross_pnl": 12.0, "after_cost_pnl": 8.0, "win_rate": 0.58,
                "fantasy_fill_rejections": 4, "open_positions": 2,
                "realized_pnl": 6.0, "unrealized_pnl": 2.0, "max_drawdown": 0.08,
                "exploration_pnl": 1.0, "validation_pnl": 7.0},
        "scan_metrics": {"scanned": 500, "kept": 40},
        "bregman": {"enabled": True, "constraint_groups_scanned": 30, "incoherent_groups": 4,
                    "candidate_arbitrages": 4, "certified_arbitrages": 2,
                    "executable_depth_certified": 1, "expected_min_profit": 0.02,
                    "worst_case_payoff": 1.0, "execution_atomicity_risk": True,
                    "opportunity_decay_half_life_s": 300.0, "clob_v2_executable": True},
        "btc_pulse": {"btc_pulse_regime": "trending_up", "btc_pulse_after_cost_pnl": 0.5,
                      "trend_persistence": 0.7, "oracle_disagreement_bps": 12.0},
        "chainlink_oracle": {"price": 67000.0, "age_seconds": 30},
        "btc_fast_price": {"price": 67010.0, "age_seconds": 1},
        "calibration": {"brier": 0.20, "ece": 0.04, "method": "isotonic", "rollbacks": 0},
        "risk": {"max_drawdown": 0.08, "kill_switch_triggers": []},
        "safety": {"ok": True, "live_detected": False},
    }


# --- audit completeness ------------------------------------------------------
def test_audit_complete_has_all_sections():
    feats = metrics.extract_features(_full_status())
    audit = metrics.build_algorithmic_edge_audit(feats, _full_status(),
                                                 scorecard={"score": 70})
    assert audit["ok"] is True
    assert audit["status"] == "complete"
    for sec in ("strategy_attribution", "bregman", "btc_pulse", "calibration",
                "fill_realism", "risk", "training_readiness"):
        assert sec in audit["sections"]
    # spot-check fields across sections
    sa = audit["sections"]["strategy_attribution"]
    assert sa["gross_pnl"] == 12.0 and sa["after_cost_pnl"] == 8.0
    assert audit["sections"]["bregman"]["certified_arbitrages"] == 2
    assert audit["sections"]["btc_pulse"]["chainlink_anchor_price"] == 67000.0
    assert audit["sections"]["calibration"]["brier"] == 0.20
    assert audit["sections"]["risk"]["max_drawdown"] == 0.08
    assert audit["sections"]["training_readiness"]["production_readiness_score"] == 70
    assert audit["sections"]["training_readiness"]["paper_only"] is True


def test_audit_fails_loudly_on_missing_core_field():
    st = _full_status()
    del st["bregman"]["certified_arbitrages"]
    del st["bregman"]["constraint_groups_scanned"]
    st["scan_metrics"].pop("scanned", None)
    feats = metrics.extract_features(st)
    # also remove the feature fallback for certified count
    feats["bregman_certified_count"] = None
    feats["bregman_candidates_found"] = None
    audit = metrics.build_algorithmic_edge_audit(feats, st, scorecard={"score": 70})
    assert audit["ok"] is False
    assert audit["status"] == "incomplete"
    assert "bregman.certified_arbitrages" in audit["missing_core_fields"]
    assert "missing_certified_arbitrage_fields" in audit["hard_failures"]
    assert "bregman_zero_groups_scanned" in audit["hard_failures"]


# --- hard failures + readiness caps (the core of this change) ---------------
def test_bregman_disabled_caps_readiness_below_40():
    st = _full_status()
    st["bregman"]["enabled"] = False
    st["bregman"]["constraint_groups_scanned"] = 0
    feats = metrics.extract_features(st)
    feats["bregman_enabled"] = False
    feats["bregman_candidates_found"] = 0
    audit = metrics.build_algorithmic_edge_audit(feats, st, scorecard={"score": 95})
    assert audit["ok"] is False
    assert audit["readiness_cap"] == 39
    assert audit["capped_readiness_score"] <= 39
    assert "bregman_disabled" in audit["hard_failures"]
    assert "bregman_zero_groups_scanned" in audit["hard_failures"]


def test_pytest_red_caps_readiness_below_50():
    feats = metrics.extract_features(_full_status())
    feats["tests_passing"] = False
    audit = metrics.build_algorithmic_edge_audit(feats, _full_status(), scorecard={"score": 95})
    assert audit["readiness_cap"] == 49
    assert audit["capped_readiness_score"] <= 49
    assert "pytest_failed" in audit["hard_failures"]
    assert audit["ok"] is False


def test_missing_fill_realism_caps_readiness_below_60():
    st = _full_status()
    st["pnl"].pop("fantasy_fill_rejections", None)
    feats = metrics.extract_features(st)
    feats["fantasy_fill_rejections"] = None
    feats["tests_passing"] = True
    audit = metrics.build_algorithmic_edge_audit(feats, st, scorecard={"score": 95})
    assert audit["readiness_cap"] == 59
    assert audit["capped_readiness_score"] <= 59
    assert "fill_realism_null" in audit["hard_failures"]


def test_missing_after_cost_pnl_caps_readiness_below_60():
    st = _full_status()
    st["pnl"].pop("after_cost_pnl", None)
    feats = metrics.extract_features(st)
    feats["after_cost_pnl"] = None
    feats["tests_passing"] = True
    audit = metrics.build_algorithmic_edge_audit(feats, st, scorecard={"score": 95})
    assert audit["readiness_cap"] == 59
    assert "after_cost_pnl_null" in audit["hard_failures"]


def test_equity_mismatch_above_1pct_is_hard_failure():
    feats = metrics.extract_features(_full_status())
    feats["tests_passing"] = True
    feats["equity"] = 500.0
    feats["dashboard_equity"] = 400.0  # 20% mismatch
    audit = metrics.build_algorithmic_edge_audit(feats, _full_status(), scorecard={"score": 95})
    assert "dashboard_equity_mismatch_gt_1pct" in audit["hard_failures"]
    assert audit["ok"] is False


def test_capped_score_never_exceeds_cap_even_when_raw_high():
    st = _full_status()
    st["bregman"]["constraint_groups_scanned"] = 0
    feats = metrics.extract_features(st)
    feats["bregman_enabled"] = False
    feats["bregman_candidates_found"] = 0
    audit = metrics.build_algorithmic_edge_audit(feats, st, scorecard={"score": 100})
    assert audit["capped_readiness_score"] < 40


def test_audit_fails_loudly_on_stale_status():
    feats = metrics.extract_features(_full_status())
    audit = metrics.build_algorithmic_edge_audit(
        feats, _full_status(), scorecard={"score": 70},
        status_age_s=7200.0, max_status_age_s=3600.0)
    assert audit["ok"] is False
    assert audit["stale"] is True
    assert any("stale" in b for b in audit["top_5_blockers"])


def test_audit_no_status_fails():
    audit = metrics.build_algorithmic_edge_audit({}, {})
    assert audit["ok"] is False
    assert any("no training status" in b for b in audit["top_5_blockers"])


def test_audit_blockers_flag_negative_after_cost():
    st = _full_status()
    st["pnl"]["after_cost_pnl"] = -3.0
    feats = metrics.extract_features(st)
    audit = metrics.build_algorithmic_edge_audit(feats, st, scorecard={"score": 70})
    assert any("after-cost PnL negative" in b for b in audit["top_5_blockers"])


def test_recommendations_include_audit_p0():
    audit = {"ok": False, "missing_core_fields": ["bregman.certified_arbitrages"],
             "stale": False}
    out = recs.build_recommendations({}, [], {}, {}, True, audit=audit)
    assert any(r["area"] == "audit" and r["priority"] == "P0" for r in out)


# --- engine diagnostics helpers ---------------------------------------------
def test_bregman_audit_diagnostics():
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="a", price=0.4, ask=0.4, ask_depth=100))
    g.add_outcome(Outcome(id="b", price=0.4, ask=0.4, ask_depth=100))
    g.add_complement("a", "b")
    res = BregmanStrategy().evaluate(g, now=0.0)
    diag = res.audit_diagnostics()
    assert diag["certified_arbitrages"] >= 1
    assert diag["executable_depth_certified"] >= 1
    assert diag["execution_atomicity_risk"] is True  # 2-leg complement
    assert diag["expected_min_profit"] > 0


def test_fill_audit_fields():
    r = assess_fill(requested_size=1000, ask=0.5, ask_depth=10, bid=0.49)
    fields = fill_audit_fields(r, fee_adjusted_ev=-0.1, clob_v2_executable=False)
    assert fields["fantasy_fill_rejected"] is True
    assert fields["partial_fill"] is True
    assert fields["clob_v2_executable"] is False
    assert fields["available_depth_at_decision"] == 10.0


def test_pulse_audit_fields():
    block = {"btc_pulse_regime": "chop", "oracle_disagreement_bps": 50.0,
             "trend_persistence": 0.3, "btc_pulse_after_cost_pnl": -0.2}
    fields = pulse_audit_fields(block, chainlink={"price": 67000}, fast={"price": 67050})
    assert fields["volatility_regime"] == "chop"
    assert fields["feed_disagreement_bps"] == 50.0
    assert fields["chainlink_anchor_price"] == 67000
    assert fields["after_cost_expectancy"] == -0.2


def test_attribution_audit_edges_and_splits():
    records = [
        {"strategy": "bregman", "pnl": 2.0, "after_cost_pnl": 1.6,
         "edge_entry": 0.05, "edge_realized": 0.04, "is_open": False},
        {"strategy": "btc_pulse", "pnl": -0.5, "edge_entry": 0.02,
         "edge_realized": -0.01, "is_open": False},
        {"strategy": "bregman", "pnl": 0.3, "is_open": True},
    ]
    a = attribution_audit(records, rejected_trades=3, open_exposure=10.0)
    assert a["trades_by_strategy"]["bregman"] == 2
    assert a["gross_pnl"] == 1.8
    assert a["after_cost_pnl"] == 1.4  # 1.6 + (-0.5) + 0.3 (open uses pnl fallback)
    assert a["win_rate"] == 0.5        # 1 win of 2 closed
    assert a["avg_edge_at_entry"] is not None
    assert a["realized_pnl"] == 1.5 and a["unrealized_pnl"] == 0.3
    assert a["rejected_trades"] == 3 and a["open_exposure"] == 10.0


# --- report wiring -----------------------------------------------------------
def _runner():
    def r(cmd, cwd, timeout):
        return (0, "git out" if cmd[:1] == ["git"] else "", "")
    return r


def _opener(url, timeout):
    return (0, "connection refused")


def test_report_includes_edge_audit_section(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "polymarket_training.json").write_text(json.dumps(_full_status()),
                                                       encoding="utf-8")
    out = tmp_path / "inspection_reports"
    res = gen.generate_report(
        output_dir=str(out), repo_root=str(tmp_path), data_dir=str(data_dir),
        skip_tests=True, include_docker=False, include_api=False,
        include_artifacts=False, runner=_runner(), opener=_opener)
    bundle = Path(res["bundle_dir"])
    assert (bundle / "algorithmic_edge_audit.json").is_file()
    report = json.loads((bundle / "report.json").read_text())
    assert "algorithmic_edge_audit" in report
    audit = report["algorithmic_edge_audit"]
    assert set(audit["sections"]) >= {
        "strategy_attribution", "bregman", "btc_pulse", "calibration",
        "fill_realism", "risk", "training_readiness"}
    md = (bundle / "report.md").read_text()
    assert "Algorithmic Edge Audit (MANDATORY)" in md
    assert "Top 5 Algorithmic Blockers" in md


def test_report_warns_when_audit_incomplete(tmp_path):
    # status missing several core fields -> audit incomplete -> loud warning
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "polymarket_training.json").write_text(json.dumps({
        "mode": "paper", "pnl": {"equity": 500.0}, "safety": {"ok": True}}),
        encoding="utf-8")
    out = tmp_path / "inspection_reports"
    res = gen.generate_report(
        output_dir=str(out), repo_root=str(tmp_path), data_dir=str(data_dir),
        skip_tests=True, include_docker=False, include_api=False,
        include_artifacts=False, runner=_runner(), opener=_opener)
    assert res["algorithmic_edge_audit_ok"] is False
    assert any("ALGORITHMIC EDGE AUDIT INCOMPLETE" in w for w in res["warnings"])

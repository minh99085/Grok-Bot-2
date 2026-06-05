"""Tests for final-validation monitoring (metrics helper + report wiring)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_bot_inspection_report as gen  # noqa: E402
import inspection_metrics as metrics  # noqa: E402


def make_runner():
    def runner(cmd, cwd, timeout):
        if cmd[:1] == ["git"]:
            return (0, "git output", "")
        return (0, "", "")
    return runner


def unreachable_opener(url, timeout):
    return (0, "connection refused")


# --- build_final_validation -------------------------------------------------
def test_final_validation_ready_when_all_pass():
    feats = {"after_cost_pnl": 5.0, "production_ready": True, "significance_passed": True,
             "live_detected": False, "fantasy_fill_rejections": 3,
             "calibration_rollbacks": 0, "bregman_certified_profit": 2.0}
    fv = metrics.build_final_validation(feats)
    assert fv["validation_ready"] is True
    assert fv["blocking_reasons"] == []
    assert fv["exploration_excluded"] is True
    assert fv["checks"]["after_cost_pnl"] == 5.0


def test_final_validation_blocked_by_negative_after_cost():
    fv = metrics.build_final_validation({"after_cost_pnl": -1.0, "production_ready": True})
    assert fv["validation_ready"] is False
    assert "after_cost_pnl_negative" in fv["blocking_reasons"]


def test_final_validation_blocked_by_live_detected():
    fv = metrics.build_final_validation({"after_cost_pnl": 5.0, "production_ready": True,
                                         "live_detected": True})
    assert fv["validation_ready"] is False
    assert "live_detected" in fv["blocking_reasons"]


def test_final_validation_surfaces_monitoring_fields():
    feats = {"bregman_opportunity_decay": 0.3, "fantasy_fill_rejections": 7,
             "calibration_rollbacks": 1}
    checks = metrics.build_final_validation(feats)["checks"]
    assert checks["bregman_opportunity_decay"] == 0.3
    assert checks["rejected_bad_fills"] == 7
    assert checks["calibration_rollbacks"] == 1


# --- report wiring ----------------------------------------------------------
def test_report_includes_final_validation(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "polymarket_training.json").write_text(json.dumps({
        "mode": "paper", "runtime_seconds": 3600,
        "pnl": {"after_cost_pnl": 2.0, "equity": 510.0, "fantasy_fill_rejections": 4},
        "safety": {"ok": True, "live_detected": False},
        "monitoring": {"bregman_opportunity_decay": 0.25},
        "calibration": {"rollbacks": 0},
    }), encoding="utf-8")
    out = tmp_path / "inspection_reports"
    res = gen.generate_report(
        output_dir=str(out), repo_root=str(tmp_path), data_dir=str(data_dir),
        skip_tests=True, include_docker=False, include_api=False,
        include_artifacts=False, runner=make_runner(), opener=unreachable_opener)
    bundle = Path(res["bundle_dir"])
    assert (bundle / "final_validation.json").is_file()
    report = json.loads((bundle / "report.json").read_text())
    assert "final_validation" in report
    assert report["final_validation"]["checks"]["after_cost_pnl"] == 2.0
    md = (bundle / "report.md").read_text()
    assert "Final Validation (Execution & Readiness)" in md

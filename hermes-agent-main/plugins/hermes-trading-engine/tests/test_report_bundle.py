"""Complete VPS light-report packaging (scripts/_report_bundle.py).

Proves the zip contains the FULL light bundle + tail samples + git proof + metrics +
validation, and that an incomplete (thin) bundle is REFUSED rather than shipped as a
success. Also asserts the VPS runner wires this in and fails on a thin zip.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import _report_bundle as rb  # noqa: E402

PLUGIN = Path(__file__).resolve().parents[1]
RUNNER = PLUGIN / "scripts" / "vps_generate_light_report.sh"


def _fake_git(args):
    if "--abbrev-ref" in args:
        out = "main"
    elif "rev-parse" in args:
        out = "deadbeefcommit"
    elif "log" in args:
        out = "deadbeef latest commit"
    elif "ls-remote" in args:
        out = "deadbeef\trefs/heads/main"
    else:
        out = ""
    return type("R", (), {"stdout": out})()


def _full_bundle(tmp_path):
    b = tmp_path / "inspection_reports" / "bot_inspection_20260613_120000"
    b.mkdir(parents=True)
    (b / "report.json").write_text(json.dumps({"run_ready": True}), encoding="utf-8")
    (b / "report.md").write_text("# Hermes light report", encoding="utf-8")
    (b / "validation_contract.json").write_text("{}", encoding="utf-8")
    (b / "final_validation.json").write_text("{}", encoding="utf-8")
    (b / "algorithmic_edge_audit.json").write_text("{}", encoding="utf-8")
    (b / "metrics").mkdir()
    (b / "metrics" / "run_ready.json").write_text("{}", encoding="utf-8")
    (b / "logs").mkdir()
    (b / "logs" / "training_tail.log").write_text("...training tail...", encoding="utf-8")
    (b / "samples").mkdir()
    (b / "samples" / "events_tail.jsonl").write_text('{"e":1}\n', encoding="utf-8")
    (tmp_path / "runtime_data" / "metrics").mkdir(parents=True)
    (tmp_path / "runtime_data" / "metrics" / "bregman_funnel.json").write_text("{}", encoding="utf-8")
    (tmp_path / "runtime_data" / "metrics" / "run_ready.json").write_text("{}", encoding="utf-8")
    (tmp_path / "runtime_data" / "inspection_summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / "validation_light_latest.txt").write_text("SAFE TO RUN: True", encoding="utf-8")
    (tmp_path / "report_logs").mkdir()
    (tmp_path / "report_logs" / "report_x.log").write_text("log", encoding="utf-8")
    return b


# --------------------------------------------------------------------------- #
# complete bundle -> full zip
# --------------------------------------------------------------------------- #
def test_zip_contains_full_light_bundle_and_tail_samples(tmp_path):
    _full_bundle(tmp_path)
    res = rb.build_report_bundle_zip(tmp_path, tmp_path / "out.zip", runner=_fake_git)
    assert res["ok"] and res["has_report_json"]
    with zipfile.ZipFile(tmp_path / "out.zip") as zf:
        names = zf.namelist()
    # full light bundle
    assert any(n.endswith("report.json") for n in names)
    assert any(n.endswith("report.md") for n in names)
    assert any(n.endswith("validation_contract.json") for n in names)
    assert any(n.endswith("final_validation.json") for n in names)
    assert any(n.endswith("algorithmic_edge_audit.json") for n in names)
    # tail samples + logs
    assert any("training_tail.log" in n for n in names)
    assert any("events_tail.jsonl" in n for n in names)
    assert any("report_x.log" in n for n in names)
    # metric files + validation output + git proof
    assert any("runtime_data/metrics/bregman_funnel.json" in n for n in names)
    assert any(n.endswith("validation_light_latest.txt") for n in names)
    assert any(n.endswith(rb.GIT_PROOF_NAME) for n in names)
    # not a thin zip
    assert res["file_count"] >= 8


def test_git_proof_written_with_commit(tmp_path):
    _full_bundle(tmp_path)
    rb.build_report_bundle_zip(tmp_path, tmp_path / "out.zip", runner=_fake_git)
    proof = (tmp_path / rb.GIT_PROOF_NAME).read_text()
    assert "HEAD: deadbeefcommit" in proof and "branch: main" in proof


# --------------------------------------------------------------------------- #
# incomplete bundle -> REFUSED (no thin zip shipped as success)
# --------------------------------------------------------------------------- #
def test_incomplete_bundle_is_refused_no_zip(tmp_path):
    (tmp_path / "inspection_reports" / "bot_x").mkdir(parents=True)   # empty skeleton
    (tmp_path / "runtime_data" / "metrics").mkdir(parents=True)
    (tmp_path / "validation_light_latest.txt").write_text("x", encoding="utf-8")
    res = rb.build_report_bundle_zip(tmp_path, tmp_path / "out.zip", runner=_fake_git)
    assert res["ok"] is False and res["reason"] == "incomplete_bundle"
    assert "report.json" in res["missing"]
    assert not (tmp_path / "out.zip").exists()       # thin zip NEVER written


def test_thin_four_file_bundle_is_refused_no_zip(tmp_path):
    """A thin bundle (only report.json + report.md + 2 stray files, the repeated ~39 KB
    failure) must be REFUSED — missing the required validation/audit + samples/metrics."""
    b = tmp_path / "inspection_reports" / "bot_thin_20260613_120000"
    b.mkdir(parents=True)
    (b / "report.json").write_text("{}", encoding="utf-8")
    (b / "report.md").write_text("# thin", encoding="utf-8")
    (b / "consistency.json").write_text("{}", encoding="utf-8")
    (b / "artifact_paths.json").write_text("{}", encoding="utf-8")
    res = rb.build_report_bundle_zip(tmp_path, tmp_path / "thin.zip", runner=_fake_git)
    assert res["ok"] is False and res["reason"] == "incomplete_bundle"
    # names the exact missing complete-bundle artifacts
    assert "final_validation.json" in res["missing"]
    assert "algorithmic_edge_audit.json" in res["missing"]
    assert "validation_contract.json" in res["missing"]
    assert any("samples" in m for m in res["missing"])
    assert any("metrics" in m for m in res["missing"])
    assert not (tmp_path / "thin.zip").exists()         # thin zip NEVER shipped


def test_main_cli_exit_codes(tmp_path):
    # complete -> 0
    _full_bundle(tmp_path)
    assert rb.main(["--plugin", str(tmp_path), "--out", str(tmp_path / "ok.zip")]) == 0
    assert (tmp_path / "ok.zip").is_file()
    # incomplete -> 13 (FATAL, refuse)
    t2 = tmp_path / "thin"
    (t2 / "inspection_reports" / "b").mkdir(parents=True)
    assert rb.main(["--plugin", str(t2), "--out", str(t2 / "thin.zip")]) == 13
    assert not (t2 / "thin.zip").exists()


def test_verify_bundle_complete():
    ok, missing = rb.verify_bundle_complete(None)
    assert not ok and "report.json" in missing


# --------------------------------------------------------------------------- #
# the VPS runner wires the complete-bundle packager + fails on a thin zip
# --------------------------------------------------------------------------- #
def test_runner_uses_complete_bundle_packager_and_fails_thin():
    t = RUNNER.read_text(encoding="utf-8")
    assert "_report_bundle.py" in t                  # uses the testable packager
    assert "--out" in t
    # never ships a thin zip: fails on non-zero rc or empty zip
    assert 'BUNDLE_RC' in t and "exit 13" in t
    assert "! -s" in t                               # empty-zip guard
    assert "refusing to ship a thin zip" in t.lower()
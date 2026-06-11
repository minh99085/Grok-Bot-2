"""Tests for the laptop coordinator CLI (scripts/laptop_agent_coordinator.py).

All subprocess calls go through an INJECTED runner, so these tests never touch the
network, SSH, Docker, or the VPS. They prove: config loading + required-field
validation, exact ssh/scp command construction + the remote light-report workflow,
secret redaction, artifact-directory creation, and the handoff-summary checklist.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import laptop_agent_coordinator as co  # noqa: E402

_FIXED = _dt.datetime(2026, 6, 11, 14, 30, 0)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class SpyRunner:
    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}

    def __call__(self, argv, cwd=None, timeout=None):
        self.calls.append(list(argv))
        joined = " ".join(str(a) for a in argv)
        for marker, resp in self._responses.items():
            if marker in joined:
                return resp
        return (0, "", "")

    def ran(self, token) -> bool:
        return any(token in " ".join(str(a) for a in c) for c in self.calls)


def collector():
    lines = []
    return lines, lines.append


def _cfg_dict(tmp_path, **over):
    d = {"repo_root": str(tmp_path), "plugin_path": str(tmp_path),
         "vps_host": "SECRET-HOST-1.2.3.4", "vps_user": "ubuntu", "vps_port": 2222,
         "vps_ssh_key": "/home/me/.ssh/SECRET_KEY",
         "vps_remote_plugin_path": "/opt/hermes/plugins/hermes-trading-engine",
         "local_artifact_dir": "artifacts"}
    d.update(over)
    return d


def write_cfg(tmp_path, **over) -> Path:
    p = tmp_path / co.DEFAULT_CONFIG
    p.write_text(json.dumps(_cfg_dict(tmp_path, **over)), encoding="utf-8")
    return p


def _plugin(tmp_path):
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "generate_bot_inspection_report.py").write_text("#", encoding="utf-8")


def _which(*avail):
    s = set(avail)
    return lambda n: (f"/usr/bin/{n}" if n in s else None)


def _run(args, tmp_path, runner=None, which=None, lines_sink=None):
    lines, printer = collector()
    if lines_sink is not None:
        lines = lines_sink
        printer = lines_sink.append
    rc = co.main(args, runner=runner or SpyRunner(), printer=printer,
                 which_fn=which or _which("git", "ssh", "scp"), now_fn=lambda: _FIXED)
    return rc, lines


# --------------------------------------------------------------------------- #
# Config loading + validation
# --------------------------------------------------------------------------- #
def test_config_loads_and_reports_set_without_secret_values(tmp_path):
    write_cfg(tmp_path)
    cfg, found = co.load_config(tmp_path / co.DEFAULT_CONFIG)
    assert found and not cfg.missing_required()
    summ = cfg.public_summary()
    assert summ["vps_host"] == "set"             # secret -> only set/unset, not the value
    assert summ["vps_user"] == "set"
    assert "SECRET-HOST-1.2.3.4" not in json.dumps(summ)
    assert summ["vps_remote_plugin_path"] == "/opt/hermes/plugins/hermes-trading-engine"


def test_missing_config_is_not_a_crash(tmp_path):
    cfg, found = co.load_config(tmp_path / "nope.json")
    assert found is False and isinstance(cfg, co.Config)


def test_missing_required_fields_detected(tmp_path):
    write_cfg(tmp_path, vps_remote_plugin_path="")
    cfg, _ = co.load_config(tmp_path / co.DEFAULT_CONFIG)
    assert "vps_remote_plugin_path" in cfg.missing_required()


# --------------------------------------------------------------------------- #
# Command construction (exact)
# --------------------------------------------------------------------------- #
def test_ssh_and_scp_command_construction(tmp_path):
    cfg, _ = co.load_config(write_cfg(tmp_path))
    ssh = co.build_ssh_cmd(cfg, "echo hi")
    assert ssh[0] == "ssh" and ssh[-2] == "ubuntu@SECRET-HOST-1.2.3.4" and ssh[-1] == "echo hi"
    assert "-i" in ssh and "/home/me/.ssh/SECRET_KEY" in ssh and "2222" in ssh
    scp = co.build_scp_pull_cmd(cfg, "/remote/x.zip", "artifacts")
    assert scp[0] == "scp" and "-P" in scp           # scp uses uppercase -P
    assert scp[-2] == "ubuntu@SECRET-HOST-1.2.3.4:/remote/x.zip"
    assert scp[-1].endswith("artifacts/")


def test_remote_collect_script_has_exact_workflow(tmp_path):
    cfg, _ = co.load_config(write_cfg(tmp_path))
    s = co.build_remote_collect_script(cfg, "/opt/hermes/plugins/hermes-trading-engine/r.zip")
    assert "cd /opt/hermes/plugins/hermes-trading-engine" in s
    assert "rm -rf runtime_data" in s
    assert "docker cp hermes-training:/data runtime_data" in s
    assert ("python scripts/generate_bot_inspection_report.py --output inspection_reports "
            "--data-dir runtime_data --bundle-mode light") in s
    assert "python scripts/validate_training_runtime.py --data-dir runtime_data | tee " \
           "validation_light_latest.txt" in s
    assert "zip -r" in s and "inspection_reports" in s
    assert "runtime_data/inspection_summary.json" in s and "validation_light_latest.txt" in s


def test_remote_zip_name_is_timestamped():
    assert co.remote_zip_name(_FIXED) == "hermes_light_report_20260611_143000.zip"


# --------------------------------------------------------------------------- #
# Secret redaction
# --------------------------------------------------------------------------- #
def test_redaction_masks_host_user_key(tmp_path):
    cfg, _ = co.load_config(write_cfg(tmp_path))
    shown = co.redact(co.build_ssh_cmd(cfg, "echo hi"), cfg)
    assert "SECRET-HOST-1.2.3.4" not in shown
    assert "/home/me/.ssh/SECRET_KEY" not in shown
    assert "ubuntu@SECRET-HOST" not in shown
    assert "<redacted>" in shown


def test_vps_smoke_output_has_no_secrets(tmp_path):
    _plugin(tmp_path)
    write_cfg(tmp_path)
    runner = SpyRunner({"echo hermes-coordinator-ok": (0, "hermes-coordinator-ok\n", ""),
                        "test -d": (0, "hermes-coordinator-ok\n", ""),
                        "docker version": (0, "27.0\n", ""),
                        "docker inspect": (0, "running\n", "")})
    rc, lines = _run(["vps-smoke", "--config", str(tmp_path / co.DEFAULT_CONFIG)],
                     tmp_path, runner=runner)
    out = "\n".join(lines)
    assert rc == 0
    assert "SECRET-HOST-1.2.3.4" not in out and "SECRET_KEY" not in out
    assert "SAFE TO CONTINUE" in out


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #
def test_doctor_passes_and_creates_artifact_dir(tmp_path):
    _plugin(tmp_path)
    write_cfg(tmp_path)
    runner = SpyRunner({"rev-parse": (0, "main\n", "")})
    rc, lines = _run(["doctor", "--config", str(tmp_path / co.DEFAULT_CONFIG)],
                     tmp_path, runner=runner)
    out = "\n".join(lines)
    assert rc == 0 and "SAFE TO CONTINUE" in out
    assert (tmp_path / "artifacts").is_dir()         # artifact dir created
    assert "SECRET-HOST-1.2.3.4" not in out


def test_doctor_missing_config_shows_setup(tmp_path):
    rc, lines = _run(["doctor", "--config", str(tmp_path / "nope.json")], tmp_path)
    assert rc == 2
    assert co.EXAMPLE_CONFIG in "\n".join(lines)


def test_doctor_stops_on_missing_tools(tmp_path):
    _plugin(tmp_path)
    write_cfg(tmp_path)
    rc, lines = _run(["doctor", "--config", str(tmp_path / co.DEFAULT_CONFIG)],
                     tmp_path, which=_which("git"))       # no ssh/scp
    out = "\n".join(lines)
    assert rc == 1 and "STOP" in out
    assert "[FAIL] ssh available" in out


# --------------------------------------------------------------------------- #
# collect-light-report
# --------------------------------------------------------------------------- #
def test_collect_dry_run_does_not_execute(tmp_path):
    _plugin(tmp_path)
    write_cfg(tmp_path)
    spy = SpyRunner()
    rc, lines = _run(["collect-light-report", "--config", str(tmp_path / co.DEFAULT_CONFIG),
                      "--dry-run"], tmp_path, runner=spy)
    out = "\n".join(lines)
    assert rc == 0 and "DRY-RUN" in out
    assert not spy.ran("docker cp")                  # nothing executed
    assert not (tmp_path / "artifacts").exists() or not any((tmp_path / "artifacts").iterdir())


def test_collect_execute_runs_ssh_then_scp(tmp_path):
    _plugin(tmp_path)
    write_cfg(tmp_path)
    spy = SpyRunner()
    rc, lines = _run(["collect-light-report", "--config", str(tmp_path / co.DEFAULT_CONFIG)],
                     tmp_path, runner=spy)
    assert rc == 0
    # the ssh remote workflow ran, then the scp pull ran, in that order
    assert spy.ran("docker cp hermes-training:/data runtime_data")
    assert spy.ran("--bundle-mode light")
    assert any(c[0] == "scp" for c in spy.calls)
    assert (tmp_path / "artifacts").is_dir()
    out = "\n".join(lines)
    assert "hermes_light_report_20260611_143000.zip" in out
    assert "SECRET-HOST-1.2.3.4" not in out


def test_collect_missing_field_stops(tmp_path):
    write_cfg(tmp_path, vps_remote_plugin_path="")
    rc, lines = _run(["collect-light-report", "--config", str(tmp_path / co.DEFAULT_CONFIG)],
                     tmp_path)
    assert rc == 2 and "STOP" in "\n".join(lines)


# --------------------------------------------------------------------------- #
# handoff-summary
# --------------------------------------------------------------------------- #
def _make_zip(tmp_path, *, with_summary=True, with_validation=True):
    art = tmp_path / "artifacts"
    art.mkdir(exist_ok=True)
    z = art / "hermes_light_report_20260611_143000.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("inspection_reports/report.json", "{}")
        if with_summary:
            zf.writestr("runtime_data/inspection_summary.json", "{}")
        if with_validation:
            zf.writestr("validation_light_latest.txt", "ok")
    return z


def test_handoff_summary_complete_zip(tmp_path):
    write_cfg(tmp_path)
    _make_zip(tmp_path)
    rc, lines = _run(["handoff-summary", "--config", str(tmp_path / co.DEFAULT_CONFIG)], tmp_path)
    out = "\n".join(lines)
    assert rc == 0
    assert "hermes_light_report_20260611_143000.zip" in out
    assert "validation file       : included" in out
    assert "inspection_summary    : included" in out
    assert "upload the zip" in out.lower()


def test_handoff_summary_missing_pieces_flagged(tmp_path):
    write_cfg(tmp_path)
    _make_zip(tmp_path, with_summary=False)
    rc, lines = _run(["handoff-summary", "--config", str(tmp_path / co.DEFAULT_CONFIG)], tmp_path)
    out = "\n".join(lines)
    assert rc == 1                                   # incomplete handoff
    assert "inspection_summary    : MISSING" in out


def test_handoff_summary_no_zip_guides_operator(tmp_path):
    write_cfg(tmp_path)
    (tmp_path / "artifacts").mkdir()
    rc, lines = _run(["handoff-summary", "--config", str(tmp_path / co.DEFAULT_CONFIG)], tmp_path)
    assert rc == 2
    assert "collect-light-report" in "\n".join(lines)


def test_help_lists_all_commands():
    p = co.build_parser()
    for name in ("doctor", "vps-smoke", "collect-light-report", "handoff-summary"):
        assert name in co.COMMANDS
    ns = p.parse_args(["collect-light-report", "--dry-run"])
    assert ns.command == "collect-light-report" and ns.dry_run is True

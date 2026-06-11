"""Tests for the laptop operator CLI (scripts/laptop_agent.py).

All subprocess calls go through an INJECTED runner, so these tests never touch the
network, Docker, git remotes, or the VPS. They prove:
  * command construction is EXACTLY the documented form,
  * config loads from JSON and from an env file,
  * dry-run is the default and never executes destructive (VPS/runtime_data) commands,
  * secrets from local config are never printed,
  * a missing config produces a clear setup message (no crash),
  * status renders SAFE / STOP correctly.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import laptop_agent as la  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class SpyRunner:
    """Records every command it is asked to run and returns scripted results."""

    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}

    def __call__(self, argv, cwd=None, timeout=None):
        self.calls.append(list(argv))
        key = argv[0] if argv else ""
        # allow keying by first token OR by a 'contains' marker
        for marker, resp in self._responses.items():
            if marker in argv or any(marker in str(t) for t in argv):
                return resp
        return self._responses.get(key, (0, "", ""))

    def ran(self, *tokens) -> bool:
        return any(all(t in call or any(t in str(c) for c in call) for t in tokens)
                   for call in self.calls)


def collector():
    lines = []
    return lines, lines.append


def write_json_config(tmp_path: Path, **kw) -> Path:
    p = tmp_path / la.CONFIG_JSON
    p.write_text(json.dumps(kw), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# Parser / help
# --------------------------------------------------------------------------- #
def test_parser_builds_and_lists_commands():
    p = la.build_parser()
    for name in ("status", "verify-sync", "local-head", "remote-head",
                 "check-docker", "check-vps", "collect", "report",
                 "validate", "package", "repo-status"):
        assert name in la.COMMANDS
    ns = p.parse_args(["status"])
    assert ns.command == "status"
    assert ns.execute is False           # dry-run is the default


def test_no_command_prints_help_returns_zero():
    lines, printer = collector()
    rc = la.main([], runner=SpyRunner(), printer=printer)
    assert rc == 0


# --------------------------------------------------------------------------- #
# Exact command construction (acceptance #7)
# --------------------------------------------------------------------------- #
def test_inspection_report_command_is_exact():
    cfg = la.Config()
    assert la.build_inspection_report_cmd(cfg, python_bin="python") == [
        "python", "scripts/generate_bot_inspection_report.py",
        "--output", "inspection_reports",
        "--data-dir", "runtime_data",
        "--bundle-mode", "light"]


def test_validate_command_is_exact():
    cfg = la.Config()
    assert la.build_validate_cmd(cfg, python_bin="python") == [
        "python", "scripts/validate_training_runtime.py",
        "--data-dir", "runtime_data"]


def test_report_command_honours_config_dirs():
    cfg = la.Config(runtime_data_dir="rd2", inspection_output_dir="out2")
    assert la.build_inspection_report_cmd(cfg, python_bin="python") == [
        "python", "scripts/generate_bot_inspection_report.py",
        "--output", "out2", "--data-dir", "rd2", "--bundle-mode", "light"]


# --------------------------------------------------------------------------- #
# Config loading (acceptance #4 + env support)
# --------------------------------------------------------------------------- #
def test_config_loads_from_json(tmp_path):
    write_json_config(tmp_path, vps_host="h", vps_user="u", vps_port=2222,
                      runtime_source="u@h:/p/")
    cfg, found = la.load_config(repo_root=tmp_path, env={})
    assert found is True
    assert cfg.vps_host == "h" and cfg.vps_user == "u" and cfg.vps_port == 2222
    assert cfg.vps_configured() and cfg.collect_configured()


def test_config_loads_from_env_file(tmp_path):
    (tmp_path / la.CONFIG_ENV).write_text(
        "LAPTOP_AGENT_VPS_HOST=eh\nLAPTOP_AGENT_VPS_USER=eu\n"
        "LAPTOP_AGENT_VPS_PORT=2200\n# comment\n", encoding="utf-8")
    cfg, found = la.load_config(repo_root=tmp_path, env={})
    assert found is True
    assert cfg.vps_host == "eh" and cfg.vps_user == "eu" and cfg.vps_port == 2200


def test_missing_config_is_not_an_error(tmp_path):
    cfg, found = la.load_config(repo_root=tmp_path, env={})
    assert found is False
    assert isinstance(cfg, la.Config) and not cfg.vps_configured()


def test_missing_config_check_vps_shows_setup_message_no_crash(tmp_path):
    lines, printer = collector()
    spy = SpyRunner()
    rc = la.main(["check-vps"], runner=spy, printer=printer, repo_root=tmp_path, env={})
    out = "\n".join(lines)
    assert rc == 2
    assert "No local operator config found" in out
    assert la.EXAMPLE_CONFIG in out
    assert not spy.ran("ssh")            # never attempted SSH without config


# --------------------------------------------------------------------------- #
# Dry-run safety (acceptance #3, #6)
# --------------------------------------------------------------------------- #
def test_dry_run_collect_does_not_execute_rsync(tmp_path):
    write_json_config(tmp_path, vps_host="h", vps_user="u",
                      runtime_source="u@h:/data/")
    lines, printer = collector()
    spy = SpyRunner()
    rc = la.main(["collect"], runner=spy, printer=printer, repo_root=tmp_path, env={})
    assert rc == 0
    assert not spy.ran("rsync")          # DESTRUCTIVE command never executed
    assert any("DRY-RUN" in ln for ln in lines)


def test_dry_run_check_vps_does_not_execute_ssh(tmp_path):
    write_json_config(tmp_path, vps_host="h", vps_user="u", vps_ssh_key="k")
    lines, printer = collector()
    spy = SpyRunner()
    rc = la.main(["check-vps"], runner=spy, printer=printer, repo_root=tmp_path, env={})
    assert rc == 0
    assert not spy.ran("ssh")
    assert any("DRY-RUN" in ln for ln in lines)


def test_dry_run_report_does_not_execute_generator(tmp_path):
    write_json_config(tmp_path)
    (tmp_path / "runtime_data").mkdir()
    (tmp_path / "runtime_data" / "x.json").write_text("{}", encoding="utf-8")
    lines, printer = collector()
    spy = SpyRunner()
    rc = la.main(["report"], runner=spy, printer=printer, repo_root=tmp_path, env={})
    assert rc == 0
    assert not spy.ran("generate_bot_inspection_report.py")
    assert any("DRY-RUN" in ln for ln in lines)


def test_execute_collect_runs_rsync(tmp_path):
    write_json_config(tmp_path, vps_host="h", vps_user="u",
                      runtime_source="u@h:/data/")
    lines, printer = collector()
    spy = SpyRunner({"rsync": (0, "", "")})
    rc = la.main(["collect", "--execute"], runner=spy, printer=printer,
                 repo_root=tmp_path, env={})
    assert rc == 0
    assert spy.ran("rsync")              # destructive command runs ONLY with --execute


def test_dry_run_flag_overrides_execute(tmp_path):
    write_json_config(tmp_path, vps_host="h", vps_user="u",
                      runtime_source="u@h:/data/")
    spy = SpyRunner({"rsync": (0, "", "")})
    rc = la.main(["collect", "--execute", "--dry-run"], runner=spy,
                 printer=lambda *_: None, repo_root=tmp_path, env={})
    assert rc == 0
    assert not spy.ran("rsync")          # explicit --dry-run keeps it safe


# --------------------------------------------------------------------------- #
# Secret safety (acceptance #8)
# --------------------------------------------------------------------------- #
def test_secrets_never_printed_in_status(tmp_path):
    secret_host = "SECRET-HOST-10.20.30.40"
    secret_key = "C:\\secret\\KEY-DO-NOT-LEAK"
    secret_src = "ubuntu@SECRET-HOST-10.20.30.40:/opt/secret/runtime_data/"
    write_json_config(tmp_path, vps_host=secret_host, vps_user="ubuntu",
                      vps_ssh_key=secret_key, runtime_source=secret_src)
    lines, printer = collector()
    spy = SpyRunner({"rev-parse": (0, "abc123\n", ""),
                     "ls-remote": (0, "abc123\trefs/heads/main\n", ""),
                     "status": (0, "", ""), "version": (0, "27.0\n", "")})
    la.main(["status"], runner=spy, printer=printer, repo_root=tmp_path, env={})
    out = "\n".join(lines)
    assert secret_host not in out
    assert secret_key not in out
    assert secret_src not in out


def test_secrets_never_printed_in_dry_run_collect(tmp_path):
    secret_src = "ubuntu@SECRET-HOST:/opt/secret/runtime_data/"
    secret_key = "SECRET-KEY-PATH"
    write_json_config(tmp_path, vps_host="SECRET-HOST", vps_user="ubuntu",
                      vps_ssh_key=secret_key, runtime_source=secret_src)
    lines, printer = collector()
    la.main(["collect"], runner=SpyRunner(), printer=printer,
            repo_root=tmp_path, env={})
    out = "\n".join(lines)
    assert "SECRET-HOST" not in out
    assert secret_key not in out
    assert secret_src not in out
    assert "<redacted" in out            # proves the command WAS shown, but masked


# --------------------------------------------------------------------------- #
# status SAFE / STOP + works without config (acceptance #2)
# --------------------------------------------------------------------------- #
def _sync_runner(local="aaa\n", remote="aaa\trefs/heads/main\n", dirty="", docker="27\n"):
    return SpyRunner({"rev-parse": (0, local, ""),
                      "ls-remote": (0, remote, ""),
                      "status": (0, dirty, ""),
                      "version": (0, docker, "")})


def test_status_safe_when_clean_and_in_sync(tmp_path):
    lines, printer = collector()
    rc = la.main(["status"], runner=_sync_runner(), printer=printer,
                 repo_root=tmp_path, env={})
    out = "\n".join(lines)
    assert rc == 0
    assert "SAFE TO CONTINUE" in out
    assert "NEXT COMMAND:" in out
    assert "UPLOAD REPORT TO CHATGPT:" in out


def test_status_stop_when_out_of_sync(tmp_path):
    lines, printer = collector()
    runner = _sync_runner(local="aaa\n", remote="bbb\trefs/heads/main\n")
    rc = la.main(["status"], runner=runner, printer=printer,
                 repo_root=tmp_path, env={})
    out = "\n".join(lines)
    assert rc == 3
    assert "STOP" in out
    assert "git pull" in out


def test_status_stop_when_repo_dirty(tmp_path):
    lines, printer = collector()
    runner = _sync_runner(dirty=" M somefile.py\n")
    rc = la.main(["status"], runner=runner, printer=printer,
                 repo_root=tmp_path, env={})
    assert rc == 3
    assert "STOP" in "\n".join(lines)


def test_status_works_without_config(tmp_path):
    lines, printer = collector()
    rc = la.main(["status"], runner=_sync_runner(), printer=printer,
                 repo_root=tmp_path, env={})    # no config file present
    out = "\n".join(lines)
    assert rc == 0
    assert "vps_configured             : False" in out or "vps_configured" in out


# --------------------------------------------------------------------------- #
# validate never hides failure
# --------------------------------------------------------------------------- #
def test_validate_failure_prints_stop(tmp_path):
    write_json_config(tmp_path)
    lines, printer = collector()
    spy = SpyRunner({"validate_training_runtime.py": (1, "FAIL details", "boom")})
    rc = la.main(["validate", "--execute"], runner=spy, printer=printer,
                 repo_root=tmp_path, env={})
    out = "\n".join(lines)
    assert rc == 3
    assert "STOP" in out and "FAILED" in out


# --------------------------------------------------------------------------- #
# packaging
# --------------------------------------------------------------------------- #
def test_package_dry_run_does_not_create_zip(tmp_path):
    out_dir = tmp_path / "inspection_reports" / "run1"
    out_dir.mkdir(parents=True)
    (out_dir / "report.json").write_text("{}", encoding="utf-8")
    lines, printer = collector()
    rc = la.main(["package"], runner=SpyRunner(), printer=printer,
                 repo_root=tmp_path, env={})
    assert rc == 0
    assert not list((tmp_path / "inspection_reports").rglob("*.zip"))


def test_package_execute_creates_zip(tmp_path):
    out_dir = tmp_path / "inspection_reports" / "run1"
    out_dir.mkdir(parents=True)
    (out_dir / "report.json").write_text("{}", encoding="utf-8")
    fixed = _dt.datetime(2026, 6, 11, 1, 2, 3)
    lines, printer = collector()
    rc = la.main(["package", "--execute"], runner=SpyRunner(), printer=printer,
                 now_fn=lambda: fixed, repo_root=tmp_path, env={})
    assert rc == 0
    zips = list((tmp_path / "inspection_reports").rglob("*.zip"))
    assert len(zips) == 1
    assert "20260611_010203" in zips[0].name


def test_package_missing_report_guides_operator(tmp_path):
    lines, printer = collector()
    rc = la.main(["package", "--execute"], runner=SpyRunner(), printer=printer,
                 repo_root=tmp_path, env={})
    assert rc == 2
    assert "report --execute" in "\n".join(lines)

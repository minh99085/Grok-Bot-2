"""Lint guard for scripts/vps_generate_full_report.sh (PAPER ONLY reporting tooling).

The ad-hoc "full report" command invoked bare ``python`` (absent on a python3-only VPS:
"Command 'python' not found"), so full-report + full-validation silently produced nothing.
The canonical script must NEVER execute bare ``python`` — only the report venv's python or
``python3`` — and must prove the 100X paper profile + live-off env WITHOUT leaking secrets.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "vps_generate_full_report.sh"


def _code_lines() -> list:
    """Non-comment, non-blank shell lines (heredoc python bodies excluded by '#' filter)."""
    out = []
    for ln in _SCRIPT.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        out.append(ln)
    return out


def test_script_exists_and_parses():
    assert _SCRIPT.is_file()
    if shutil.which("bash"):
        assert subprocess.run(["bash", "-n", str(_SCRIPT)]).returncode == 0


def test_never_executes_bare_python():
    # a bare `python <...>` EXECUTION is the exact failure we are preventing. Only flag
    # `python` in COMMAND position (start of line or right after ; | & ( or then/do/else),
    # so log strings like `echo "... venv python: ..."` are ignored. Allow python3 + venv.
    cmd_python = re.compile(r"(?:^|[;&|(]|\b(?:then|do|else)\b)\s*python(?![3\w])")
    bad = [ln.strip() for ln in _code_lines() if cmd_python.search(ln)]
    assert not bad, f"bare `python` execution(s) found (use python3/venv): {bad}"


def test_wraps_canonical_light_runner_and_proves_env():
    txt = _SCRIPT.read_text(encoding="utf-8")
    assert "vps_generate_light_report.sh" in txt          # builds the complete bundle
    assert "validate_training_runtime.py" in txt           # full validation via venv
    assert "AGGRESSIVE_PAPER_TRAINING" in txt              # 100X profile proof
    # every live/real-money flag is proven OFF in the env proof
    for k in ("MICRO_LIVE_ENABLED", "GUARDED_LIVE_ENABLED", "BTC_AUTOTRADE_ENABLED"):
        assert k in txt
    # secret presence only — never echo the raw key value
    assert "XAI_API_KEY_PRESENT" in txt
    assert "echo \"XAI_API_KEY=" not in txt and "${XAI_API_KEY}" not in txt


def test_refuses_thin_or_failed_bundle_and_resets_latest():
    txt = _SCRIPT.read_text(encoding="utf-8")
    # deletes stale latest before generation; refuses to ship on a failed/missing bundle
    assert 'rm -f "${ZIP_LATEST}"' in txt
    assert "exit 13" in txt

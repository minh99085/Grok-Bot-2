"""Start/stop CLI for the institutional paper campaign (PAPER ONLY).

Quant scope — *Compliance/Security/Operational Excellence*: --aggressive-paper
uses the aggressive PAPER config, --campaign + --algorithm-freeze engage the
campaign controller, the stop sentinel is honored by the run loop, and any
forbidden live flag fails the start closed.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load(script_name):
    path = _ROOT / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_aggressive_campaign_run_writes_campaign_state(tmp_path, monkeypatch):
    for k in ("MICRO_LIVE_ENABLED", "GUARDED_LIVE_ENABLED", "ARB_EXECUTION_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HTE_MODE", "paper")
    start = _load("start_polymarket_paper_training.py")
    rc = start.run([
        "--aggressive-paper", "--campaign", "--campaign-name", "cli_camp",
        "--algorithm-freeze", "--catalog", "synthetic", "--max-ticks", "2",
        "--data-dir", str(tmp_path), "--write-campaign-report"])
    assert rc == 0
    camp_path = tmp_path / "polymarket_training_campaign.json"
    assert camp_path.exists()
    data = json.loads(camp_path.read_text())
    assert data["campaign_name"] == "cli_camp"
    assert data["algorithm_freeze_mode"] is True
    # aggressive config was used (exploration on in the persisted status)
    status = json.loads((tmp_path / "polymarket_training.json").read_text())
    assert status["config"]["exploration_enabled"] is True
    # campaign report artifacts written
    assert (tmp_path / "training_campaign.json").exists()
    assert (tmp_path / "training_campaign.md").exists()


def test_stop_sentinel_is_honored_by_run_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("HTE_MODE", "paper")
    # pre-write the stop sentinel BEFORE starting the continue-until-thresholds loop
    (tmp_path / "polymarket_training.stop").write_text("stop", encoding="utf-8")
    start = _load("start_polymarket_paper_training.py")
    rc = start.run([
        "--aggressive-paper", "--campaign", "--algorithm-freeze",
        "--catalog", "synthetic", "--continue-until-thresholds", "--max-hours", "0.001",
        "--tick-seconds", "0", "--data-dir", str(tmp_path)])
    assert rc == 0  # exited promptly because the stop sentinel was present


def test_forbidden_live_flag_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("HTE_MODE", "paper")
    monkeypatch.setenv("MICRO_LIVE_ENABLED", "1")
    start = _load("start_polymarket_paper_training.py")
    rc = start.run(["--aggressive-paper", "--campaign", "--catalog", "synthetic",
                    "--max-ticks", "1", "--data-dir", str(tmp_path)])
    assert rc == 2  # fail closed


def test_stop_script_marks_campaign_stop_requested(tmp_path, monkeypatch):
    monkeypatch.setenv("HTE_MODE", "paper")
    # seed a campaign state file
    from engine.training.campaign_controller import TrainingCampaignController
    from _campaign_helpers import micro_ready_snapshot
    path = tmp_path / "polymarket_training_campaign.json"
    ctrl = TrainingCampaignController(algorithm_freeze_mode=True, state_path=path)
    ctrl.update(micro_ready_snapshot())
    ctrl.persist()
    stop = _load("stop_polymarket_paper_training.py")
    rc = stop.run(["--data-dir", str(tmp_path), "--no-report"])
    assert rc == 0
    assert (tmp_path / "polymarket_training.stop").exists()
    data = json.loads(path.read_text())
    assert data["stop_requested"] is True
    # evidence is NOT deleted
    assert data["runs"]

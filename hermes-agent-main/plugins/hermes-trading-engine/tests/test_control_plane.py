"""Tests for the runtime control plane (overrides file, API, board overlay).

PAPER ONLY: toggles can disable any subsystem and re-enable paper/advisory ones,
but never enable a live path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import engine.app as app_mod  # noqa: E402
from engine import control  # noqa: E402


def _client() -> TestClient:
    return TestClient(app_mod.app)


# --- pure control module ----------------------------------------------------
def test_write_read_roundtrip(tmp_path):
    control.write_override(tmp_path, "btc_pulse", "off")
    assert control.read_overrides(tmp_path) == {"btc_pulse": "off"}
    control.write_override(tmp_path, "news", "on")
    ov = control.read_overrides(tmp_path)
    assert ov["news"] == "on" and ov["btc_pulse"] == "off"


def test_auto_clears_override(tmp_path):
    control.write_override(tmp_path, "btc_pulse", "off")
    control.write_override(tmp_path, "btc_pulse", "auto")
    assert "btc_pulse" not in control.read_overrides(tmp_path)


def test_invalid_key_and_state_raise(tmp_path):
    try:
        control.write_override(tmp_path, "nope", "off")
        assert False
    except ValueError:
        pass
    try:
        control.write_override(tmp_path, "btc_pulse", "sideways")
        assert False
    except ValueError:
        pass


def test_effective_state_precedence():
    assert control.effective_state("news", default_on=False, overrides={"news": "on"}) is True
    assert control.effective_state("news", default_on=True, overrides={"news": "off"}) is False
    assert control.effective_state("news", default_on=True, overrides={}) is True


def test_apply_to_config_flips_paper_flags():
    cfg = SimpleNamespace(btc_pulse_enabled=False, news_scanner_enabled=True)
    applied = control.apply_to_config(cfg, {"btc_pulse": "on", "news": "off"})
    assert cfg.btc_pulse_enabled is True
    assert cfg.news_scanner_enabled is False
    assert ("btc_pulse_enabled", True) in applied


def test_apply_runtime_freezes_and_unfreezes_pulse():
    pulse = SimpleNamespace(frozen=False, enabled_flag=True, safety={"passed": True})
    trainer = SimpleNamespace(btc_pulse=pulse)
    control.apply_runtime(trainer, {"btc_pulse": "off"})
    assert pulse.frozen is True
    control.apply_runtime(trainer, {"btc_pulse": "on"})
    assert pulse.frozen is False


def test_apply_runtime_wont_unfreeze_unsafe_pulse():
    pulse = SimpleNamespace(frozen=True, enabled_flag=True, safety={"passed": False})
    trainer = SimpleNamespace(btc_pulse=pulse)
    out = control.apply_runtime(trainer, {"btc_pulse": "on"})
    assert pulse.frozen is True
    assert "cannot_unfreeze" in out["btc_pulse"]


def test_read_overrides_missing_file_is_empty(tmp_path):
    assert control.read_overrides(tmp_path) == {}


# --- API + board overlay ----------------------------------------------------
def test_control_overrides_endpoint_lists_catalog():
    data = _client().get("/api/control/overrides").json()
    assert data["mode"] == "paper"
    keys = {c["key"] for c in data["controllable"]}
    assert {"btc_pulse", "news", "grok", "polymarket"} <= keys


def test_post_control_sets_override_and_board_reflects():
    c = _client()
    r = c.post("/api/control/btc_pulse/off")
    assert r.status_code == 200 and r.json()["ok"] is True
    # board overlay shows the subsystem off + controllable metadata
    sysd = c.get("/api/running-status").json()
    bp = next(s for s in sysd["systems"] if s["key"] == "btc_pulse")
    assert bp["controllable"] is True
    assert bp["override"] == "off"
    assert bp["state"] == "off"
    # reset to auto so other tests are unaffected
    c.post("/api/control/btc_pulse/auto")


def test_post_control_rejects_unknown_key():
    r = _client().post("/api/control/not_a_system/off")
    assert r.status_code == 400


def test_post_control_auto_clears():
    c = _client()
    c.post("/api/control/news/on")
    assert _client().get("/api/control/overrides").json()["overrides"].get("news") == "on"
    c.post("/api/control/news/auto")
    assert "news" not in _client().get("/api/control/overrides").json()["overrides"]

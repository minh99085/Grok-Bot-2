"""GrokBrain activation self-heal (PAPER ONLY, research-only).

Reproduces the deploy race where the xAI/Grok key is injected into the container
(docker env_file) AFTER the brain object was constructed: the dashboard showed
"GROK BRAIN OFF — add an API key" even though the key was present in the env. The
brain must self-heal on the next status() poll and the ON toggle must re-read the
key. Grok stays research-only; no live/order path is ever enabled.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.brain import GrokBrain, read_grok_key

_GROK_ENV = ("XAI_API_KEY", "GROK_API_KEY", "RESEARCH_MODE", "GROK_BRAIN_ONLINE")


@pytest.fixture(autouse=True)
def _clean_grok_env(monkeypatch):
    for k in _GROK_ENV:
        monkeypatch.delenv(k, raising=False)
    yield


def _brain(tmp_path):
    return GrokBrain(SimpleNamespace(data_dir=str(tmp_path), stance="balanced"))


def test_brain_self_heals_when_key_injected_after_construction(tmp_path, monkeypatch):
    b = _brain(tmp_path)
    assert b.enabled is False and b.grok_source == "disabled"
    # docker env_file injects the key into the env AFTER the brain was built
    monkeypatch.setenv("XAI_API_KEY", "x" * 84)
    monkeypatch.setenv("GROK_BRAIN_ONLINE", "1")
    st = b.status()                      # dashboard poll self-heals
    assert st["enabled"] is True
    assert st["grok_source"] == "online_research"


def test_online_paper_mode_enables_without_explicit_grok_brain_online(tmp_path, monkeypatch):
    b = _brain(tmp_path)
    monkeypatch.setenv("XAI_API_KEY", "x" * 84)
    monkeypatch.setenv("RESEARCH_MODE", "online_paper")   # online mode alone is enough
    st = b.status()
    assert st["enabled"] is True
    assert st["grok_source"] == "online_research"


def test_turn_on_toggle_rereads_key(tmp_path, monkeypatch):
    b = _brain(tmp_path)
    assert b.enabled is False
    monkeypatch.setenv("XAI_API_KEY", "x" * 84)
    monkeypatch.setenv("GROK_BRAIN_ONLINE", "1")
    st = b.set_active(True)              # "click to turn ON" re-reads the key
    assert st["enabled"] is True
    assert st["grok_source"] == "online_research"


def test_user_pause_is_respected_even_with_key(tmp_path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "x" * 84)
    monkeypatch.setenv("GROK_BRAIN_ONLINE", "1")
    b = _brain(tmp_path)
    assert b.enabled is True
    b.set_active(False)                  # operator explicitly pauses
    assert b.enabled is False and b.grok_source == "paused_by_user"
    # a later poll must NOT silently re-enable a user-paused brain
    assert b.status()["enabled"] is False


def test_no_key_stays_off(tmp_path):
    b = _brain(tmp_path)
    st = b.status()
    assert st["enabled"] is False
    assert st["grok_source"] == "disabled"


@pytest.mark.parametrize("raw,expected", [
    ('xai-clean', 'xai-clean'),
    ('  xai-ws  ', 'xai-ws'),
    ('"xai-dquoted"', 'xai-dquoted'),
    ("'xai-squoted'", 'xai-squoted'),
    ('  "xai-both"\n', 'xai-both'),     # quotes + whitespace + newline (the 401 trap)
    ('', ''),
])
def test_read_grok_key_sanitizes_quotes_and_whitespace(monkeypatch, raw, expected):
    # a key delivered via docker compose interpolation may keep surrounding quotes /
    # a trailing newline -> malformed Bearer header -> 401 ("suddenly stopped").
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.setenv("XAI_API_KEY", raw)
    assert read_grok_key() == expected


def test_quoted_key_in_env_still_enables_brain(tmp_path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", '"xai-quoted-key-value"')
    monkeypatch.setenv("GROK_BRAIN_ONLINE", "1")
    b = _brain(tmp_path)
    assert b.api_key == "xai-quoted-key-value"   # quotes stripped
    assert b.status()["enabled"] is True

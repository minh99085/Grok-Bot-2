"""Tests for clearing a stale stop sentinel on an explicit training start.

A leftover ``polymarket_training.stop`` in the persisted data volume must not
make a fresh start exit at tick 0 (which loops forever under docker's
``restart: unless-stopped``). PAPER ONLY behavior — only clears a stop flag.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import start_polymarket_paper_training as starter  # noqa: E402


def test_clears_stale_sentinel(tmp_path):
    sp = tmp_path / "polymarket_training.stop"
    sp.write_text("stop", encoding="utf-8")
    assert starter.clear_stale_stop_sentinel(sp) is True
    assert not sp.exists()


def test_keep_flag_preserves_sentinel(tmp_path):
    sp = tmp_path / "polymarket_training.stop"
    sp.write_text("stop", encoding="utf-8")
    assert starter.clear_stale_stop_sentinel(sp, keep=True) is False
    assert sp.exists()  # legacy opt-out keeps the sentinel


def test_noop_when_absent(tmp_path):
    sp = tmp_path / "polymarket_training.stop"
    assert starter.clear_stale_stop_sentinel(sp) is False
    assert not sp.exists()

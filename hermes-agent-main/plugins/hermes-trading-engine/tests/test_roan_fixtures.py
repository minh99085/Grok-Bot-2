"""Phase 0 Roan fixtures — validate synthetic nested violation matches Bregman stub."""

from __future__ import annotations

import json
from pathlib import Path

from engine.pulse.bregman_projection import projection_distance_nested

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_nested_implication_fixture_matches_bregman_stub():
    fx = _load("roan_nested_implication_violation.json")
    brain = fx["brain_5m"]
    hands = fx["hands_15m"]
    exp = fx["expected"]
    d = projection_distance_nested(
        hands["up_mid"], brain["up_mid"], epsilon=0.02)
    assert d["constraint_type"] == exp["constraint_type"]
    assert d["max_theoretical_profit_per_share"] == exp["violation_magnitude"]
    assert d["actionable_projection"] is exp["actionable_at_epsilon_0_02"]
    assert d["projection_distance"] > exp["bregman_projection_distance_gt"]


def test_dutch_book_fixture_declares_no_bregman():
    fx = _load("roan_dutch_book_opportunity.json")
    assert fx["expected"]["bregman_required"] is False
    assert fx["expected"]["kind"] == "buy_both"
"""Grok dependency screener validation."""

from __future__ import annotations

import json

from engine.pulse.grok_dependency import (
    parse_grok_dependency_response,
    validate_grok_proposals,
)
from engine.pulse.markets import OrderBook, PulseWindow


def test_parse_grok_json():
    raw = json.dumps({"proposals": [{
        "constraint_type": "nested_implication",
        "parent_window_key": "p",
        "child_window_keys": ["c"],
    }]})
    props = parse_grok_dependency_response(raw)
    assert len(props) == 1


def test_validate_rejects_unmapped():
    rep = validate_grok_proposals([{"constraint_type": "nested_implication",
                                      "parent_window_key": "x",
                                      "child_window_keys": ["y"]}],
                                    windows_by_id={})
    assert rep["deterministic_validated_dependencies"] == 0
    assert len(rep["rejected_dependencies"]) == 1
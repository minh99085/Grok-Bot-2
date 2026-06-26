"""Market graph for dependency discovery."""

from __future__ import annotations

from engine.pulse.arb_graph import MarketGraph
from engine.pulse.markets import PulseWindow, OrderBook


def _w(eid, ws, open_ts, label):
    return PulseWindow(
        event_id=eid, market_id="m", slug=f"btc-updown-{ws//60}m-{int(open_ts)}",
        title=label, open_ts=open_ts, close_ts=open_ts + ws,
        up_token_id="U", down_token_id="D", window_seconds=ws, series_label=label,
    )


def test_graph_nested_edges():
    t0 = 1_000_000.0
    p = _w("p15", 900, t0, "15m")
    c = _w("c5", 300, t0 + 60, "5m")
    g = MarketGraph().build_from_windows([p, c])
    rep = g.report()
    assert rep["nodes"] == 2
    assert rep["deterministic_validated_dependencies"] >= 1
    assert "nested_implication" in rep["edge_types"]


def test_grok_proposals_advisory_only():
    g = MarketGraph().build_from_windows([])
    n = g.add_grok_proposals([{
        "constraint_type": "nested_implication",
        "parent_window_key": "a",
        "child_window_keys": ["b"],
        "description": "test",
    }])
    assert n == 1
    rep = g.report()
    assert rep["dependency_proposals"] == 1
    assert rep["rejected_or_advisory_dependencies"] >= 1
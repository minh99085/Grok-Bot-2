"""Phase 6 walk-forward for dependency-arb positions (realized_profit_usd field)."""

from __future__ import annotations

from engine.pulse.walk_forward import holdout_metrics, passes_walk_forward


def test_holdout_metrics_uses_realized_profit_usd():
    positions = [
        {"status": "settled", "entry_ts": 1.0, "realized_profit_usd": 5.0},
        {"status": "settled", "entry_ts": 2.0, "realized_profit_usd": 3.0},
        {"status": "settled", "entry_ts": 3.0, "realized_profit_usd": -1.0},
    ]
    hm = holdout_metrics(positions)
    assert hm["n"] == 3
    assert hm["pnl_usd"] == 7.0
    assert hm["win_rate"] == round(2 / 3, 4)


def test_walk_forward_dep_arb_holdout_passes_on_profitable_tail():
    positions = [
        {"status": "settled", "entry_ts": float(i), "realized_profit_usd": 2.0}
        for i in range(25)
    ] + [
        {"status": "settled", "entry_ts": float(100 + i), "realized_profit_usd": 4.0}
        for i in range(10)
    ]
    r = passes_walk_forward(positions, min_holdout_n=5, min_holdout_pf=1.0)
    assert r["holdout"]["n"] >= 5
    assert r["passed"] is True
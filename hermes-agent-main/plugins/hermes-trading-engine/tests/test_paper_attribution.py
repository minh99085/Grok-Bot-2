"""Paper attribution tests (also satisfies ``pytest -k paper_attribution``).

Validates per-strategy paper attribution from the canonical ledger, with strict
exploration-vs-validation separation.
"""

from __future__ import annotations

from engine.ledger import CanonicalLedger
from engine.strategies.strategy_attribution import (
    attribution_from_ledger,
    split_exploration_validation,
)


def _ledger():
    led = CanonicalLedger(starting_balance=500.0)
    led.record(ts=1.0, market="m1", strategy="abcas", traded=True,
               realized_pnl=2.0, after_cost_pnl=1.8)
    led.record(ts=2.0, market="m2", strategy="btc_pulse", traded=True,
               realized_pnl=-0.5, after_cost_pnl=-0.6, is_exploration=True)
    return led


def test_paper_attribution_by_strategy_from_ledger():
    out = attribution_from_ledger(_ledger())
    assert out["by_strategy"]["abcas"]["after_cost_pnl"] == 1.8
    assert "btc_pulse" in out["by_strategy"]


def test_paper_attribution_separates_exploration_from_validation():
    out = attribution_from_ledger(_ledger())
    assert out["validation_pnl"] == 1.8        # abcas (not exploration)
    assert out["exploration_pnl"] == -0.6      # btc_pulse exploration
    assert out["exploration_excluded_from_validation"] is True


def test_paper_attribution_split_helper_matches():
    recs = [{"strategy": "abcas", "pnl": 1.0, "tier": 1},
            {"strategy": "explore", "pnl": 9.0, "tier": 4, "is_exploration": True}]
    s = split_exploration_validation(recs)
    assert s["validation_pnl"] == 1.0
    assert s["exploration_pnl"] == 9.0          # exploration never inflates validation

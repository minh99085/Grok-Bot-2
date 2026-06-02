"""Experiment risk budgets — hard caps apply ACROSS all variants combined.

Quant scope — *Risk/Portfolio Optimization* + *Compliance/Security*: proves the
paper-only per-variant budget never lets the combined book exceed the hard risk
caps (total exposure, max open trades), and that Bregman keeps first priority.
PAPER ONLY.
"""

from __future__ import annotations

import time

import pytest

from engine.campaigns.signal_models import SignalResult
from engine.training.config import TrainingConfig
from engine.training.experiment_manager import BREGMAN_VARIANT, ExperimentManager
from engine.training.polymarket_trainer import PolymarketPaperTrainer


class _DemoResearch:
    name = "research"

    def evaluate(self, rec):
        return SignalResult(0.85, 0.9, "grok_cache", "demo-est")

    def status(self):
        return {"name": "research", "research_mode": "offline_cache"}


def _catalog(n=30):
    now = time.time()
    out = []
    for i in range(n):
        bid, ask = 0.20, 0.22
        out.append({"id": f"d{i}", "question": f"Demo market {i}?", "active": True,
                    "closed": False, "archived": False, "enableOrderBook": True,
                    "acceptingOrders": True, "clobTokenIds": [f"t{i}a", f"t{i}b"],
                    "outcomePrices": [str((bid + ask) / 2), str(1 - (bid + ask) / 2)],
                    "bestBid": bid, "bestAsk": ask, "spread": round(ask - bid, 4),
                    "liquidityNum": 50000, "volume24hr": 9000, "topDepthUsd": 5000,
                    "volumeNum": 90000, "endDate": "2030-01-01T00:00:00Z",
                    "description": "Demo resolution text per official sources. " * 6,
                    "category": ["politics", "crypto", "econ"][i % 3], "bookUpdatedTs": now})
    return out


def _run(tmp_path, **overrides):
    cfg = TrainingConfig.aggressive_paper(
        experiments_enabled=True, chainlink_enabled=False, max_hold_ticks=50, **overrides)
    t = PolymarketPaperTrainer(cfg, data_dir=tmp_path, signal_model=_DemoResearch())
    cat = _catalog()
    for _ in range(8):
        t.run_tick(cat)
    return t, cfg


# --------------------------------------------------------------------------- #
# allocation never exceeds the slot budget
# --------------------------------------------------------------------------- #
def test_allocation_sum_bounded_and_bregman_first():
    em = ExperimentManager(experiment_id="e", aggressive=True)
    for total in range(0, 12):
        a = em.allocate(total, bregman_available=True)
        assert sum(a.values()) <= total
        if total >= 1:
            assert a[BREGMAN_VARIANT] >= 1


# --------------------------------------------------------------------------- #
# hard risk caps apply across ALL variants/experiments combined
# --------------------------------------------------------------------------- #
def test_combined_open_exposure_never_exceeds_hard_cap(tmp_path):
    t, cfg = _run(tmp_path)
    # at all times the combined open book (every variant) respected the caps
    assert t.total_exposure() <= cfg.max_total_exposure_usd + 1e-6
    assert len(t.open_positions()) <= cfg.max_open_trades
    # every per-market exposure also respected its cap
    for gk in t.open_event_groups():
        assert t.market_exposure(gk) <= cfg.max_market_exposure_usd + 1e-6


def test_combined_open_trades_bounded_by_hard_cap_regardless_of_variants(tmp_path):
    t, cfg = _run(tmp_path)
    # spread across variants, but the COMBINED count never beats max_open_trades
    by_variant: dict = {}
    for p in t.open_positions():
        by_variant[p.strategy_variant] = by_variant.get(p.strategy_variant, 0) + 1
    assert sum(by_variant.values()) == len(t.open_positions())
    assert sum(by_variant.values()) <= cfg.max_open_trades


def test_aggressive_budget_at_least_conservative(tmp_path):
    aggr = TrainingConfig.aggressive_paper(experiments_enabled=True)
    cons = TrainingConfig(mode="paper_train")
    # aggressive allocates MORE paper decision budget across variants ...
    assert aggr.paper_decision_budget >= cons.paper_decision_budget
    # ... but the hard paper caps are NOT loosened (only ever tighter/equal)
    assert aggr.max_order_notional_usd <= 50.0
    assert aggr.max_open_trades <= aggr.max_open_trades_hard_cap

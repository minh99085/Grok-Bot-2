"""Strategy-variant attribution end-to-end through the paper trainer.

Quant scope — *Signal Generation* + *Monitoring*: proves every paper decision /
trade / feedback record and the report carry an ``experiment_id`` +
``strategy_variant``, and that variant-level metrics are separated. PAPER ONLY.
"""

from __future__ import annotations

import time

import pytest

from engine.campaigns.signal_models import SignalResult
from engine.training.config import TrainingConfig
from engine.training.experiment_manager import STRATEGY_VARIANTS
from engine.training.polymarket_trainer import PolymarketPaperTrainer


class _DemoResearch:
    name = "research"

    def __init__(self, fair=0.82, conf=0.9):
        self._fair, self._conf = fair, conf

    def evaluate(self, rec):
        return SignalResult(self._fair, self._conf, "grok_cache", "demo-est")

    def status(self):
        return {"name": "research", "grok_enabled": False,
                "research_mode": "offline_cache"}


def _catalog(n=25):
    cats = ["politics", "sports", "crypto", "econ", "tech"]
    now = time.time()
    out = []
    for i in range(n):
        bid, ask = 0.28, 0.30
        out.append({"id": f"d{i}", "question": f"Demo market {i}?", "active": True,
                    "closed": False, "archived": False, "enableOrderBook": True,
                    "acceptingOrders": True, "clobTokenIds": [f"t{i}a", f"t{i}b"],
                    "outcomePrices": [str((bid + ask) / 2), str(1 - (bid + ask) / 2)],
                    "bestBid": bid, "bestAsk": ask, "spread": round(ask - bid, 4),
                    "liquidityNum": 20000, "volume24hr": 8000, "topDepthUsd": 2000,
                    "volumeNum": 40000, "endDate": "2030-01-01T00:00:00Z",
                    "description": "Demo resolution text per official sources. " * 6,
                    "category": cats[i % len(cats)], "bookUpdatedTs": now})
    return out


def _run(tmp_path, **overrides):
    cfg = TrainingConfig.aggressive_paper(
        experiments_enabled=True, chainlink_enabled=False, max_hold_ticks=2, **overrides)
    t = PolymarketPaperTrainer(cfg, data_dir=tmp_path, signal_model=_DemoResearch())
    cat = _catalog()
    for _ in range(4):
        t.run_tick(cat)
    t.finalize()
    return t


def test_aggressive_enables_experiments_by_default():
    cfg = TrainingConfig.aggressive_paper()
    assert cfg.experiments_enabled is True
    assert cfg.experiment_id


def test_every_position_is_tagged_with_experiment_and_variant(tmp_path):
    t = _run(tmp_path)
    assert t.positions, "expected the aggressive demo to open paper trades"
    for p in t.positions:
        assert getattr(p, "experiment_id", "") == t.cfg.experiment_id
        assert getattr(p, "strategy_variant", "") in STRATEGY_VARIANTS


def test_experiment_manager_recorded_every_opened_trade(tmp_path):
    t = _run(tmp_path)
    vm = t.experiments.variant_metrics()
    total_recorded = sum(v["trade_count"] for v in vm.values())
    assert total_recorded == len(t.positions)


def test_experiment_report_breaks_out_metrics_by_variant(tmp_path):
    t = _run(tmp_path)
    rep = t.experiment_report()
    assert rep["experiment_id"] == t.cfg.experiment_id
    assert "variants" in rep and "champion_challenger" in rep
    # every reported variant key is a known strategy variant with the full field set
    for variant, m in rep["variants"].items():
        assert variant in STRATEGY_VARIANTS
        for k in ("trade_count", "feedback_count", "sharpe", "brier", "ece",
                  "realized_edge", "fill_quality"):
            assert k in m


def test_feedback_records_are_variant_scoped(tmp_path):
    t = _run(tmp_path)
    vm = t.experiments.variant_metrics()
    # closed positions produced variant-scoped feedback
    closed = [p for p in t.positions if p.closed]
    total_feedback = sum(v["feedback_count"] for v in vm.values())
    assert total_feedback == len(closed)

"""Campaign uses REAL collected evidence from the running paper engine.

Quant scope — *Data Acquisition & Ingestion* + *Live Trading & Monitoring*: the
campaign controller is fed real trainer evidence (decisions, paper trades, live
orders), not synthetic numbers, and the trainer exposes a campaign report.
"""

from __future__ import annotations

import time

from engine.campaigns.signal_models import SignalResult
from engine.training.config import TrainingConfig
from engine.training.polymarket_trainer import PolymarketPaperTrainer


class _Demo:
    name = "research"

    def evaluate(self, rec):
        return SignalResult(0.82, 0.9, "grok_cache", "e")

    def status(self):
        return {"name": "research", "research_mode": "offline_cache"}


def _catalog(n=10):
    now = time.time()
    return [{"id": f"d{i}", "question": f"Demo {i}?", "active": True, "closed": False,
             "archived": False, "enableOrderBook": True, "acceptingOrders": True,
             "clobTokenIds": [f"t{i}a", f"t{i}b"], "outcomePrices": ["0.29", "0.71"],
             "bestBid": 0.28, "bestAsk": 0.30, "spread": 0.02, "liquidityNum": 20000,
             "volume24hr": 8000, "topDepthUsd": 2000, "volumeNum": 40000,
             "endDate": "2030-01-01T00:00:00Z",
             "description": "Demo resolution text per official sources. " * 6,
             "category": "politics", "bookUpdatedTs": now} for i in range(n)]


def _trainer(tmp_path):
    cfg = TrainingConfig.aggressive_paper(campaign_enabled=True, algorithm_freeze_mode=True,
                                          chainlink_enabled=False, max_hold_ticks=2)
    return PolymarketPaperTrainer(cfg, data_dir=tmp_path, signal_model=_Demo())


def test_trainer_campaign_report_uses_real_counts(tmp_path):
    t = _trainer(tmp_path)
    for _ in range(3):
        t.run_tick(_catalog())
    t.finalize()
    rep = t.campaign_report()
    assert rep is not None
    ev = rep["evidence"]
    assert ev["decisions"] == t.decision_count
    assert ev["paper_trades"] == t.pnl_summary()["trades_opened"]
    assert ev["live_orders"] == 0
    assert rep["no_live_orders"] is True


def test_status_includes_training_campaign_block(tmp_path):
    t = _trainer(tmp_path)
    t.run_tick(_catalog())
    st = t.status()
    assert "training_campaign" in st
    assert st["training_campaign"]["verdict"]["live_trading_enabled"] is False


def test_short_run_is_not_micro_canary_ready(tmp_path):
    t = _trainer(tmp_path)
    for _ in range(2):
        t.run_tick(_catalog())
    t.finalize()
    rep = t.campaign_report()
    assert rep["verdict"]["state"] != "micro_canary_ready"
    # the campaign state file is persisted in the data dir
    assert (tmp_path / "polymarket_training_campaign.json").exists()


def test_campaign_disabled_yields_no_block(tmp_path):
    cfg = TrainingConfig.aggressive_paper(campaign_enabled=False, chainlink_enabled=False,
                                          max_hold_ticks=2)
    t = PolymarketPaperTrainer(cfg, data_dir=tmp_path, signal_model=_Demo())
    t.run_tick(_catalog())
    rep = t.campaign_report()
    assert rep is None or rep.get("enabled") is False

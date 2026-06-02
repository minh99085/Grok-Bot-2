"""Aggressive-learning monitoring dashboard.

Quant scope — *Live Monitoring* + *Statistical Modeling*: proves the dashboard
exposes whether aggressive paper mode is learning faster (paper trades/hour,
useful feedback/hour, labels resolved/day, calibration improvement, Brier/ECE
trend, Bregman + Chainlink performance, exploration budget, drawdown, loss
streak, stale-data rejections). PAPER ONLY — read-only metrics.
"""

from __future__ import annotations

import time

import pytest

from engine.campaigns.signal_models import SignalResult
from engine.training.config import TrainingConfig
from engine.training.monitoring import (build_dashboard, loss_streak, metric_trend,
                                        per_day, per_hour)
from engine.training.polymarket_trainer import PolymarketPaperTrainer

_REQUIRED = (
    "paper_trades_per_hour", "useful_feedback_per_hour", "labels_resolved_per_day",
    "calibration_improvement", "brier", "brier_trend", "ece", "ece_trend",
    "bregman_opportunities", "certified_bregman_profit", "bregman_false_positive_rate",
    "chainlink_linked_performance", "exploration_budget_used", "drawdown",
    "loss_streak", "stale_data_rejections")


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #
def test_rate_helpers():
    assert per_hour(4, 1800) == pytest.approx(8.0)     # 4 in 30min -> 8/hr
    assert per_day(2, 43200) == pytest.approx(4.0)     # 2 in 12h -> 4/day
    assert per_hour(5, 0) == 0.0


def test_loss_streak_counts_trailing_losses():
    assert loss_streak([1.0, -1.0, -2.0, -0.5]) == 3
    assert loss_streak([1.0, 2.0]) == 0
    assert loss_streak([]) == 0


def test_metric_trend_last_minus_first():
    hist = [{"brier": 0.30}, {"brier": 0.25}, {"brier": 0.20}]
    assert metric_trend(hist, "brier") == pytest.approx(-0.10)
    assert metric_trend([{"brier": 0.2}], "brier") == 0.0


# --------------------------------------------------------------------------- #
# dashboard assembly
# --------------------------------------------------------------------------- #
def _raw(**kw):
    base = dict(
        trades_opened=4, useful_feedback=4, labels_resolved=4,
        calibration_error=0.05, brier=0.18, ece=0.03,
        bregman={"opportunities": 3, "certified_profit": 0.9, "false_positive_rate": 0.0},
        chainlink_linked_performance={"trades": 2, "win_rate": 0.5, "pnl": 1.0},
        exploration_budget_used=4.0, drawdown=-2.0, loss_streak=1,
        stale_data_rejections=1, stale_data_rejection_rate=0.05, partial_fill_rate=0.1,
        avg_spread=0.02, label_suppression_rate=0.05, ambiguous_rate=0.02,
        learner_rollbacks=0, profile="aggressive")
    base.update(kw)
    return base


def test_build_dashboard_has_all_required_metrics():
    d = build_dashboard(_raw(), runtime_seconds=1800,
                        history=[{"brier": 0.25, "ece": 0.06, "calibration_error": 0.10}])
    for k in _REQUIRED:
        assert k in d, k


def test_build_dashboard_computes_rates_and_trends():
    d = build_dashboard(_raw(trades_opened=4, useful_feedback=4, labels_resolved=4,
                             brier=0.18, ece=0.03, calibration_error=0.05),
                        runtime_seconds=1800,
                        history=[{"brier": 0.28, "ece": 0.08, "calibration_error": 0.12}])
    assert d["paper_trades_per_hour"] == pytest.approx(8.0)
    assert d["useful_feedback_per_hour"] == pytest.approx(8.0)
    assert d["labels_resolved_per_day"] == pytest.approx(192.0)  # 4 in 0.5h -> /day
    # trend = current - first(history); improvement = first_calib - current_calib
    assert d["brier_trend"] == pytest.approx(0.18 - 0.28)
    assert d["ece_trend"] == pytest.approx(0.03 - 0.08)
    assert d["calibration_improvement"] == pytest.approx(0.12 - 0.05)


# --------------------------------------------------------------------------- #
# trainer integration
# --------------------------------------------------------------------------- #
class _Demo:
    name = "research"

    def evaluate(self, rec):
        return SignalResult(0.82, 0.9, "grok_cache", "e")

    def status(self):
        return {"name": "research", "research_mode": "offline_cache"}


def _catalog(n=12):
    now = time.time()
    return [{"id": f"d{i}", "question": f"Demo {i}?", "active": True, "closed": False,
             "archived": False, "enableOrderBook": True, "acceptingOrders": True,
             "clobTokenIds": [f"t{i}a", f"t{i}b"],
             "outcomePrices": ["0.29", "0.71"], "bestBid": 0.28, "bestAsk": 0.30,
             "spread": 0.02, "liquidityNum": 20000, "volume24hr": 8000,
             "topDepthUsd": 2000, "volumeNum": 40000, "endDate": "2030-01-01T00:00:00Z",
             "description": "Demo resolution text per official sources. " * 6,
             "category": ["politics", "crypto"][i % 2], "bookUpdatedTs": now}
            for i in range(n)]


def test_trainer_exposes_aggressive_dashboard(tmp_path):
    cfg = TrainingConfig.aggressive_paper(chainlink_enabled=False, max_hold_ticks=2)
    t = PolymarketPaperTrainer(cfg, data_dir=tmp_path, signal_model=_Demo())
    cat = _catalog()
    for _ in range(3):
        t.run_tick(cat)
    t.finalize()
    d = t.aggressive_dashboard()
    for k in _REQUIRED:
        assert k in d, k
    # status carries the monitoring + kill-switch blocks
    st = t.status()
    assert "monitoring" in st and "kill_switch" in st

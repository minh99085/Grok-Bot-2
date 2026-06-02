"""No live escalation without durable evidence (the hard safety invariant).

Quant scope — *Compliance/Security/Operational Excellence*: proves a strategy can
NEVER be marked live-ready using optimistic fills, unresolved labels, insufficient
sample size, stale Chainlink, stale order books, or negative after-cost
expectancy — and that the trainer's readiness verdict never flips a live flag.
"""

from __future__ import annotations

import time

import pytest

from engine.campaigns.signal_models import SignalResult
from engine.training.config import TrainingConfig
from engine.training.live_readiness import (
    ReadinessCriteria, ReadinessState, capital_preservation_report,
    evaluate_live_readiness)
from engine.training.polymarket_trainer import PolymarketPaperTrainer


def _bregman(**kw):
    b = dict(opportunities=10, false_positive_rate=0.0, worst_case_pnl=0.5,
             full_hedge_validated=True, all_leg_fill_feasible=True,
             partial_fill_hedge_break=False)
    b.update(kw)
    return b


def _strong(**kw):
    e = dict(samples=1200, after_cost_expectancy=0.02, realistic_fill_expectancy=0.015,
             oos_sharpe=2.0, oos_sortino=2.2, oos_calmar=1.0, max_drawdown_pct=0.08,
             calibration_error=0.04, ece=0.05, label_suppression_rate=0.05,
             unresolved_rate=0.05, ambiguous_rate=0.05, stale_data_rejection_rate=0.02,
             chainlink_stale=False, stale_book=False, risk_violations=0,
             downgraded=False, bregman=_bregman())
    e.update(kw)
    return e


# --------------------------------------------------------------------------- #
# the forbidden-evidence matrix — none may reach a live-ready state
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("label,override", [
    ("optimistic_only_fills", {"realistic_fill_expectancy": -0.005}),
    ("unresolved_labels", {"unresolved_rate": 0.7}),
    ("insufficient_samples", {"samples": 40}),
    ("stale_chainlink", {"chainlink_stale": True}),
    ("stale_order_books", {"stale_book": True}),
    ("negative_after_cost_expectancy", {"after_cost_expectancy": -0.001}),
])
def test_forbidden_evidence_never_live_ready(label, override):
    v = evaluate_live_readiness(_strong(**override), ReadinessCriteria())
    assert v.state not in ReadinessState.LIVE_READY, label
    assert v.allows_live_escalation is False
    # and capital preservation gives ZERO allowed live notional
    rep = capital_preservation_report(v, bankroll=5000.0)
    assert rep["max_initial_live_notional"] == 0.0
    assert rep["allowed"] is False


def test_optimistic_fill_profit_alone_is_not_enough():
    # great optimistic after-cost expectancy, but realistic fills lose money
    v = evaluate_live_readiness(
        _strong(after_cost_expectancy=0.05, realistic_fill_expectancy=-0.02),
        ReadinessCriteria())
    assert v.state == ReadinessState.BLOCKED
    assert any("realistic" in b for b in v.blockers)


# --------------------------------------------------------------------------- #
# the trainer's verdict never enables live trading
# --------------------------------------------------------------------------- #
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


def test_trainer_readiness_is_paper_and_never_enables_live(tmp_path):
    cfg = TrainingConfig.aggressive_paper(chainlink_enabled=False, max_hold_ticks=2)
    t = PolymarketPaperTrainer(cfg, data_dir=tmp_path, signal_model=_Demo())
    for _ in range(3):
        t.run_tick(_catalog())
    t.finalize()
    rep = t.live_readiness_report()
    # a short paper run can never be live-ready (insufficient sample size)
    assert rep["verdict"]["state"] not in ReadinessState.LIVE_READY
    assert rep["capital_preservation"]["max_initial_live_notional"] == 0.0
    assert rep["verdict"]["live_trading_enabled"] is False
    # safety preflight stays clean: no live execution was ever enabled
    assert t.preflight()["live_detected"] is False
    assert t.cfg.is_paper_only is True
    # the verdict is surfaced in status without flipping any live control
    assert "live_readiness" in t.status()

"""Tier-1: historical dataset (point-in-time, no look-ahead) + walk-forward backtest +
out-of-sample calibration + learner warm-start. All offline (synthetic resolved markets).
"""

from __future__ import annotations

import random

import pytest

from engine.training.historical_dataset import (build_observations, market_outcome,
                                                 ResolvedObservation)
from engine.training.backtest import (BacktestConfig, time_split, calibration_report,
                                       directional_backtest, walk_forward_validate)
from engine.training.online_learner import OnlineLearner


def _resolved_market(mid, *, yes_won, last, change_1w, change_1d=None, change_1mo=None,
                     resolved_ts=1_000_000.0, status="resolved", category="crypto"):
    raw = {"id": mid, "question": f"q{mid}", "closed": True,
           "umaResolutionStatus": status, "category": category,
           "outcomePrices": ["1", "0"] if yes_won else ["0", "1"],
           "lastTradePrice": last, "oneWeekPriceChange": change_1w,
           "closedTime": resolved_ts}
    if change_1d is not None:
        raw["oneDayPriceChange"] = change_1d
    if change_1mo is not None:
        raw["oneMonthPriceChange"] = change_1mo
    return raw


# ---------------- dataset: point-in-time + clean-resolution ----------------

def test_market_outcome_clean_only():
    assert market_outcome(_resolved_market("a", yes_won=True, last=0.99, change_1w=0.4)) == 1
    assert market_outcome(_resolved_market("b", yes_won=False, last=0.01, change_1w=-0.4)) == 0
    # not closed -> skip
    open_raw = _resolved_market("c", yes_won=True, last=0.5, change_1w=0.0); open_raw["closed"] = False
    assert market_outcome(open_raw) is None
    # ambiguous settled price -> skip (never fabricate)
    amb = _resolved_market("d", yes_won=True, last=0.5, change_1w=0.0); amb["outcomePrices"] = ["0.5", "0.5"]
    assert market_outcome(amb) is None
    # unresolved status -> skip
    unr = _resolved_market("e", yes_won=True, last=0.99, change_1w=0.4, status="proposed")
    assert market_outcome(unr) is None


def test_observation_reconstructs_past_price_no_lookahead():
    # YES won (last ~0.99); a week before, price was last - change = 0.99 - 0.49 = 0.50
    m = _resolved_market("m1", yes_won=True, last=0.99, change_1w=0.49)
    obs = build_observations([m], leads=("1w",))
    assert len(obs) == 1
    o = obs[0]
    assert o.outcome == 1
    assert abs(o.observed_prob - 0.50) < 1e-6      # reconstructed past price (the FEATURE)
    assert o.observed_ts < o.resolved_ts            # feature strictly precedes the label


def test_observations_chronological_and_multi_lead():
    m = _resolved_market("m2", yes_won=False, last=0.02, change_1d=-0.1, change_1w=-0.3,
                          change_1mo=-0.5)
    obs = build_observations([m], leads=("1d", "1w", "1mo"))
    assert {o.lead_label for o in obs} == {"1d", "1w", "1mo"}
    assert all(o.outcome == 0 for o in obs)
    assert [o.observed_ts for o in obs] == sorted(o.observed_ts for o in obs)


# ---------------- walk-forward split + calibration ----------------

def test_time_split_no_leakage():
    obs = [ResolvedObservation("m", "c", "1w", 0.5, 0, 100.0 + i, float(i)) for i in range(10)]
    train, test = time_split(obs, train_frac=0.7)
    assert len(train) == 7 and len(test) == 3
    assert max(o.observed_ts for o in train) <= min(o.observed_ts for o in test)


def test_calibration_report_perfect_predictions():
    preds = [0.0] * 50 + [1.0] * 50
    outs = [0] * 50 + [1] * 50
    rep = calibration_report(preds, outs)
    assert rep["n"] == 100 and rep["brier"] == 0.0 and rep["ece"] == 0.0


# ---------------- directional backtest ----------------

def test_directional_backtest_profits_when_signal_beats_market():
    # market priced 0.5 but everything resolved YES; a signal that says 0.9 should buy YES
    # and profit (+0.5 per share, minus cost)
    obs = [ResolvedObservation(f"m{i}", "c", "1w", 0.5, 1, 100.0, float(i)) for i in range(40)]
    bt = directional_backtest(obs, signal=lambda p: 0.9, edge_threshold=0.0,
                              cost_per_trade=0.01)
    assert bt["trades"] == 40 and bt["sides"]["yes"] == 40
    assert bt["expectancy"] > 0.0 and bt["hit_rate"] == 1.0


def test_directional_backtest_no_trades_when_no_edge():
    obs = [ResolvedObservation(f"m{i}", "c", "1w", 0.5, 1, 100.0, float(i)) for i in range(40)]
    # signal == market -> zero edge -> with positive cost, nothing clears the threshold
    bt = directional_backtest(obs, signal=lambda p: p, edge_threshold=0.0,
                              cost_per_trade=0.01)
    assert bt["trades"] == 0


# ---------------- full walk-forward validation ----------------

def test_walk_forward_validate_structure_and_no_lookahead_flags():
    rng = random.Random(7)
    obs = []
    for i in range(400):
        p = round(rng.uniform(0.1, 0.9), 3)
        outcome = 1 if rng.random() < p else 0          # a CALIBRATED market
        obs.append(ResolvedObservation(f"m{i}", "crypto", "1w", p, outcome,
                                        1_000_000.0 + i, float(i)))
    rep = walk_forward_validate(obs, cfg=BacktestConfig(train_frac=0.7, cost_per_trade=0.01))
    assert rep["status"] == "ok"
    assert rep["no_look_ahead"] is True and rep["live_trading_enabled"] is False
    assert rep["train_n"] + rep["test_n"] == 400
    assert "raw_market_oos_calibration" in rep and "calibrated_model_backtest" in rep
    # a calibrated market => OOS Brier is sane and no free directional edge after cost
    assert rep["raw_market_oos_calibration"]["brier"] is not None


def test_walk_forward_insufficient_samples():
    obs = [ResolvedObservation(f"m{i}", "c", "1w", 0.5, i % 2, 100.0 + i, float(i))
           for i in range(5)]
    rep = walk_forward_validate(obs, cfg=BacktestConfig(min_calibration_samples=20))
    assert rep["status"] == "insufficient_samples" and rep["promotable"] is False


# ---------------- learner warm-start ----------------

def test_learner_warm_start_makes_calibration_measurable(tmp_path):
    learner = OnlineLearner(path=tmp_path / "state.json")
    assert learner.calibration_error() == 0.0          # cold
    rng = random.Random(3)
    obs = []
    for i in range(300):
        p = round(rng.uniform(0.05, 0.95), 3)
        outcome = 1 if rng.random() < p else 0
        obs.append(ResolvedObservation(f"m{i}", "crypto", "1w", p, outcome, 100.0, float(i)))
    n = learner.warm_start(obs)
    assert n == 300 and learner.warm_start_samples == 300
    # calibration buckets are now populated (a real, auditable calibration state)
    assert learner.calibration_table()
    assert learner.category_samples("crypto") == 300


def test_learner_warm_start_accepts_tuples(tmp_path):
    learner = OnlineLearner(path=tmp_path / "s.json")
    n = learner.warm_start([(0.8, 1, "politics"), (0.2, 0, "politics"), (0.6, 1)])
    assert n == 3 and learner.category_samples("politics") == 2

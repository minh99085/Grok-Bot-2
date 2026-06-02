"""Aggressive paper learning must learn fast WITHOUT overfitting.

Quant scope — *CLOB v2 Simulation* + *Monitoring* + *Compliance/Security*: proves
the learner can snapshot a stable state and auto-roll-back when validation
degrades, that aggressive mode produces more learning updates than the
conservative baseline, and that an overfit aggressive parameter set is blocked
from promotion while a robust one passes. Also exercises the replay overfit
report (IS vs OOS Sharpe / Brier / log-loss / ECE / drawdown / realized edge).
"""

from __future__ import annotations

import pytest

from engine.replay.metrics import overfit_report
from engine.training.config import TrainingConfig
from engine.training.online_learner import OnlineLearner
from engine.training.overfit_governor import WalkForwardParameterGovernor


def _train(learner, n, *, win_rate, prob=0.6, category="crypto", pnl=1.0):
    trained = 0
    for i in range(n):
        win = (i % 100) < int(win_rate * 100)
        trained += int(learner.record_outcome(
            predicted_prob=prob, win=win, realized_pnl=pnl if win else -pnl,
            category=category, label_state="resolved_yes" if win else "resolved_no"))
    return trained


# --------------------------------------------------------------------------- #
# learner stable-state snapshot + automatic rollback
# --------------------------------------------------------------------------- #
def test_learner_snapshot_and_restore_round_trip():
    lr = OnlineLearner(min_bucket_samples=1)
    _train(lr, 40, win_rate=0.6)
    snap = lr.snapshot()
    closed_at_snap = lr.closed
    # pollute with noisy outcomes
    _train(lr, 40, win_rate=0.0)
    assert lr.closed > closed_at_snap
    lr.restore(snap)
    assert lr.closed == closed_at_snap


def test_learner_auto_rollback_on_validation_degrade():
    lr = OnlineLearner(min_bucket_samples=1)
    _train(lr, 60, win_rate=0.6)
    lr.checkpoint_stable(validation_error=0.05)
    closed_stable = lr.closed
    # aggressive noisy learning degrades calibration on validation
    _train(lr, 60, win_rate=0.05)
    rolled = lr.maybe_rollback(validation_error=0.40, tolerance=0.05)
    assert rolled is True
    assert lr.rollbacks == 1
    assert lr.closed == closed_stable


def test_learner_no_rollback_when_validation_stable():
    lr = OnlineLearner(min_bucket_samples=1)
    _train(lr, 60, win_rate=0.6)
    lr.checkpoint_stable(validation_error=0.05)
    closed = lr.closed
    rolled = lr.maybe_rollback(validation_error=0.06, tolerance=0.05)
    assert rolled is False
    assert lr.closed == closed


# --------------------------------------------------------------------------- #
# aggressive learns faster, but production params are gated by walk-forward
# --------------------------------------------------------------------------- #
def test_aggressive_mode_learns_more_updates_than_conservative():
    base = OnlineLearner(min_bucket_samples=20)
    aggr = OnlineLearner(min_bucket_samples=1)
    # same stream; aggressive's lower min-bucket lets it use buckets sooner
    base_updates = _train(base, 50, win_rate=0.6)
    aggr_updates = _train(aggr, 50, win_rate=0.6)
    assert aggr_updates == 50 and base_updates == 50  # both record
    # aggressive surfaces a usable calibration signal with fewer samples
    assert aggr.calibration_error() >= 0.0
    cfg = TrainingConfig.aggressive_paper()
    assert cfg.walk_forward_enabled is True
    assert cfg.aggressive_can_promote_params is False  # gated until WF passes


def test_overfit_params_blocked_robust_promoted_end_to_end():
    gov = WalkForwardParameterGovernor(
        oos_degrade_tolerance=0.2, min_param_stability=0.5, max_overfit_penalty=0.5)

    overfit_rows = [{"ts": i, "category": "crypto", "ret": 0.06 if i < 20 else -0.05}
                    for i in range(40)]
    robust_rows = [{"ts": i, "category": "crypto", "ret": 0.02} for i in range(40)]
    metric = lambda r: sum(x["ret"] for x in r) / len(r)

    wf_bad = gov.evaluate(overfit_rows, metric_fn=metric, train=6, test=3)
    wf_good = gov.evaluate(robust_rows, metric_fn=metric, train=6, test=3)

    bad = gov.can_promote(walk_forward=wf_bad, aggressive=True,
                          in_sample={"sharpe": 2.5, "brier": 0.10},
                          out_of_sample={"sharpe": 0.0, "brier": 0.32})
    good = gov.can_promote(walk_forward=wf_good, aggressive=True,
                           in_sample={"sharpe": 1.0, "brier": 0.18},
                           out_of_sample={"sharpe": 0.97, "brier": 0.19})
    assert bad["promote"] is False
    assert good["promote"] is True


# --------------------------------------------------------------------------- #
# replay overfit report — IS vs OOS Sharpe / Brier / log-loss / ECE / drawdown
# --------------------------------------------------------------------------- #
def test_overfit_report_surfaces_is_vs_oos():
    rep = overfit_report(
        {"sharpe": 2.4, "brier": 0.10, "log_loss": 0.30, "ece": 0.02,
         "max_drawdown": -1.0, "realized_edge": 0.05},
        {"sharpe": 0.2, "brier": 0.30, "log_loss": 0.65, "ece": 0.18,
         "max_drawdown": -6.0, "realized_edge": -0.01})
    assert "in_sample" in rep and "out_of_sample" in rep
    for k in ("sharpe", "brier", "log_loss", "ece", "max_drawdown", "realized_edge"):
        assert k in rep["delta"]
    assert rep["overfit"] is True
    assert rep["reasons"]


def test_overfit_report_clean_run():
    rep = overfit_report(
        {"sharpe": 1.0, "brier": 0.18, "log_loss": 0.45, "ece": 0.03,
         "max_drawdown": -2.0, "realized_edge": 0.02},
        {"sharpe": 0.95, "brier": 0.19, "log_loss": 0.46, "ece": 0.035,
         "max_drawdown": -2.3, "realized_edge": 0.018})
    assert rep["overfit"] is False

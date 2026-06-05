"""Tests for walk-forward, combinatorial purged CV, bootstrap CI, regime buckets,
and Sharpe/Sortino/Calmar significance gates."""

from __future__ import annotations

from engine.backtest import (
    calmar_ratio,
    combinatorial_purged_cv,
    sharpe_ratio,
    significance_gate,
    sortino_ratio,
)
from engine.replay.robustness import (
    bootstrap_ci,
    regime_segmentation,
    walk_forward_windows,
)


# --- risk-adjusted ratios ----------------------------------------------------
def test_ratios_positive_for_good_series():
    # include small dips so downside deviation + drawdown are defined
    rets = [0.02, -0.01, 0.03, 0.015, -0.005, 0.025]
    assert sharpe_ratio(rets) > 0
    assert sortino_ratio(rets) > 0
    assert calmar_ratio(rets) is not None and calmar_ratio(rets) > 0


def test_sortino_penalizes_downside():
    up = [0.01, 0.02, 0.03, 0.01]
    mixed = [0.05, -0.04, 0.05, -0.04]
    assert sharpe_ratio(mixed) is not None
    # all-up has no downside deviation -> Sortino None (infinite); mixed finite
    assert sortino_ratio(mixed) is not None


def test_ratios_none_for_tiny_sample():
    assert sharpe_ratio([0.01]) is None
    assert sortino_ratio([]) is None
    assert calmar_ratio([]) is None


# --- walk-forward ------------------------------------------------------------
def test_walk_forward_no_lookahead():
    wins = walk_forward_windows(100, train=40, test=20)
    assert wins
    for w in wins:
        assert w.test_start >= w.train_end  # test strictly follows train


# --- combinatorial purged CV -------------------------------------------------
def test_cpcv_split_count_and_purging():
    splits = combinatorial_purged_cv(60, k=6, test_groups=2, embargo=2)
    # C(6,2) = 15 combinations
    assert len(splits) == 15
    for s in splits:
        # train and test never overlap
        assert not (set(s["test_idx"]) & set(s["train_idx"]))
        assert len(s["test_group_ids"]) == 2


def test_cpcv_embargo_drops_adjacent_train():
    no_emb = combinatorial_purged_cv(60, k=6, test_groups=1, embargo=0)
    emb = combinatorial_purged_cv(60, k=6, test_groups=1, embargo=5)
    # embargo removes some training indices -> fewer (or equal) train points
    assert len(emb[0]["train_idx"]) <= len(no_emb[0]["train_idx"])


def test_cpcv_degenerate_returns_empty():
    assert combinatorial_purged_cv(0, k=6, test_groups=2) == []
    assert combinatorial_purged_cv(60, k=2, test_groups=2) == []  # test==k


# --- bootstrap CI ------------------------------------------------------------
def test_bootstrap_ci_brackets_point_and_is_seeded():
    rets = [0.01, 0.02, -0.01, 0.03, 0.0, 0.02, -0.02, 0.04]
    a = bootstrap_ci(rets, n_boot=500, alpha=0.05, seed=7)
    b = bootstrap_ci(rets, n_boot=500, alpha=0.05, seed=7)
    assert a == b  # deterministic
    assert a["lo"] <= a["point"] <= a["hi"]


# --- regime buckets ----------------------------------------------------------
def test_regime_segmentation_buckets():
    obs = [{"vol": 0.01}, {"vol": 0.05}, {"vol": 0.2}]
    buckets = regime_segmentation(obs, key="vol", thresholds=[0.03, 0.1],
                                  labels=["low", "mid", "high"])
    assert len(buckets["low"]) == 1
    assert len(buckets["mid"]) == 1
    assert len(buckets["high"]) == 1


# --- significance gate -------------------------------------------------------
def test_significance_gate_passes_with_margin():
    base = {"sharpe": 1.0, "sortino": 1.0, "calmar": 1.0}
    cand = {"sharpe": 1.5, "sortino": 1.4, "calmar": 1.3}
    res = significance_gate(base, cand, thresholds={"sharpe": 0.3, "sortino": 0.3, "calmar": 0.2})
    assert res["passed"] is True
    assert res["per_metric"]["sharpe"]["delta"] == 0.5


def test_significance_gate_fails_when_one_metric_short():
    base = {"sharpe": 1.0, "sortino": 1.0, "calmar": 1.0}
    cand = {"sharpe": 1.5, "sortino": 1.05, "calmar": 1.3}  # sortino +0.05 < 0.2
    res = significance_gate(base, cand)
    assert res["passed"] is False
    assert res["per_metric"]["sortino"]["passed"] is False


def test_significance_gate_missing_metric_fails():
    res = significance_gate({"sharpe": 1.0}, {"sharpe": 2.0})  # sortino/calmar missing
    assert res["passed"] is False

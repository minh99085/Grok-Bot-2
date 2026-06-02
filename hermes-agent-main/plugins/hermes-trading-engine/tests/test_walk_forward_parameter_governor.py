"""Walk-forward parameter governor (anti-overfitting).

Quant scope — *Backtesting & Simulation* + *Strategy Optimization*: proves the
walk-forward evaluation, the time/category split, the parameter-stability score,
and the promotion gate that stops an overfit aggressive parameter set from ever
being promoted to production-like parameters.
"""

from __future__ import annotations

import pytest

from engine.training.overfit_governor import (
    WalkForwardParameterGovernor, WalkForwardResult, parameter_stability_score,
    time_category_split, walk_forward_evaluate)


def _obs(n: int, *, categories=("crypto", "politics"), start_ts: int = 0,
         ret: float = 0.01):
    rows = []
    for i in range(n):
        rows.append({"ts": start_ts + i, "category": categories[i % len(categories)],
                     "ret": ret})
    return rows


# --------------------------------------------------------------------------- #
# train/validation/test split by time AND market category
# --------------------------------------------------------------------------- #
def test_time_category_split_is_chronological_and_no_leakage():
    obs = _obs(30)
    split = time_category_split(obs, train_frac=0.6, val_frac=0.2)
    # every observation lands in exactly one split
    assert len(split.train) + len(split.validation) + len(split.test) == 30
    # within each category, train precedes validation precedes test in TIME
    for cat in ("crypto", "politics"):
        tr = [o["ts"] for o in split.train if o["category"] == cat]
        va = [o["ts"] for o in split.validation if o["category"] == cat]
        te = [o["ts"] for o in split.test if o["category"] == cat]
        assert tr and va and te, cat
        assert max(tr) < min(va) <= max(va) < min(te), cat


def test_time_category_split_covers_every_category():
    obs = _obs(40, categories=("a", "b", "c", "d"))
    split = time_category_split(obs)
    cov = split.coverage()
    for cat in ("a", "b", "c", "d"):
        assert cov[cat]["train"] >= 1
        assert cov[cat]["validation"] >= 1
        assert cov[cat]["test"] >= 1


def test_time_category_split_handles_tiny_categories_gracefully():
    obs = _obs(20) + [{"ts": 999, "category": "rare", "ret": 0.5}]
    split = time_category_split(obs)
    # the single-sample category does not crash and is assigned to exactly one split
    placed = (sum(o["category"] == "rare" for o in split.train)
              + sum(o["category"] == "rare" for o in split.validation)
              + sum(o["category"] == "rare" for o in split.test))
    assert placed == 1


# --------------------------------------------------------------------------- #
# parameter stability score
# --------------------------------------------------------------------------- #
def test_parameter_stability_score_constant_is_max():
    assert parameter_stability_score([0.3, 0.3, 0.3]) == pytest.approx(1.0)


def test_parameter_stability_score_monotone_in_dispersion():
    stable = parameter_stability_score([0.30, 0.31, 0.29, 0.30])
    jumpy = parameter_stability_score([0.05, 0.55, 0.10, 0.50])
    assert 0.0 <= jumpy < stable <= 1.0


def test_parameter_stability_score_single_value():
    assert parameter_stability_score([0.42]) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# walk-forward evaluation
# --------------------------------------------------------------------------- #
def test_walk_forward_evaluate_robust_series():
    # stable positive edge everywhere -> IS ~= OOS, low penalty, high stability
    obs = _obs(40, ret=0.02)
    wf = walk_forward_evaluate(obs, metric_fn=lambda rows: sum(r["ret"] for r in rows) / len(rows),
                               train=6, test=3)
    assert isinstance(wf, WalkForwardResult)
    assert wf.n_windows >= 3
    assert wf.mean_oos == pytest.approx(0.02, abs=1e-9)
    assert wf.oos_is_ratio == pytest.approx(1.0, abs=1e-9)
    assert wf.overfit_penalty <= 0.05
    assert wf.stability >= 0.9


def test_walk_forward_evaluate_overfit_series_degrades_oos():
    # great in-sample (early), poor out-of-sample (later): edge decays over time
    rows = [{"ts": i, "category": "crypto", "ret": 0.05 if i < 20 else -0.04}
            for i in range(40)]

    def metric(window):
        return sum(r["ret"] for r in window) / len(window)

    wf = walk_forward_evaluate(rows, metric_fn=metric, train=6, test=3)
    # OOS materially worse than IS -> high overfit penalty
    assert wf.mean_oos < wf.mean_is
    assert wf.overfit_penalty > 0.3


# --------------------------------------------------------------------------- #
# promotion gate — overfit parameters can NEVER be promoted
# --------------------------------------------------------------------------- #
def test_governor_promotes_robust_parameters():
    gov = WalkForwardParameterGovernor()
    obs = _obs(40, ret=0.02)
    wf = gov.evaluate(obs, metric_fn=lambda r: sum(x["ret"] for x in r) / len(r),
                      train=6, test=3)
    assert gov.passes(wf)
    decision = gov.can_promote(walk_forward=wf,
                               in_sample={"sharpe": 1.2, "brier": 0.18},
                               out_of_sample={"sharpe": 1.1, "brier": 0.19})
    assert decision["promote"] is True
    assert decision["walk_forward_passed"] is True


def test_governor_blocks_overfit_parameters():
    gov = WalkForwardParameterGovernor()
    rows = [{"ts": i, "category": "crypto", "ret": 0.05 if i < 20 else -0.04}
            for i in range(40)]
    wf = gov.evaluate(rows, metric_fn=lambda r: sum(x["ret"] for x in r) / len(r),
                      train=6, test=3)
    assert not gov.passes(wf)
    decision = gov.can_promote(walk_forward=wf,
                               in_sample={"sharpe": 2.5, "brier": 0.10},
                               out_of_sample={"sharpe": 0.1, "brier": 0.30})
    # FAIL if an overfit parameter set is ever promoted
    assert decision["promote"] is False
    assert decision["reasons"]


def test_aggressive_cannot_promote_without_walk_forward_pass():
    gov = WalkForwardParameterGovernor()
    rows = [{"ts": i, "category": "crypto", "ret": 0.05 if i < 20 else -0.04}
            for i in range(40)]
    wf = gov.evaluate(rows, metric_fn=lambda r: sum(x["ret"] for x in r) / len(r),
                      train=6, test=3)
    decision = gov.can_promote(walk_forward=wf, aggressive=True,
                               in_sample={"sharpe": 2.5}, out_of_sample={"sharpe": 0.1})
    assert decision["promote"] is False


def test_aggressive_may_promote_when_walk_forward_passes():
    gov = WalkForwardParameterGovernor()
    obs = _obs(40, ret=0.02)
    wf = gov.evaluate(obs, metric_fn=lambda r: sum(x["ret"] for x in r) / len(r),
                      train=6, test=3)
    decision = gov.can_promote(walk_forward=wf, aggressive=True,
                               in_sample={"sharpe": 1.1, "brier": 0.18},
                               out_of_sample={"sharpe": 1.05, "brier": 0.19})
    assert decision["promote"] is True

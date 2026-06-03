"""With-news vs without-news ablation + per-market news diagnostics.

Quant scope — *Strategy Optimization & Robustness*: measures whether news
improves calibration (Brier / log-loss / ECE) and after-cost edge by category,
and records per-market news diagnostics. Advisory analytics only — no trades.
"""

from __future__ import annotations

from engine.training.metrics import (
    news_ablation_report, news_conditioned_diagnostics)


def test_diagnostics_record_probabilities_edges_decisions():
    d = news_conditioned_diagnostics(
        prob_without_news=0.55, prob_with_news=0.62, p_market=0.50,
        outcome=1, min_edge=0.03)
    assert d["probability_without_news"] == 0.55
    assert d["probability_with_news"] == 0.62
    assert d["probability_delta_from_news"] == 0.07
    assert d["edge_without_news"] >= 0.0
    assert d["decision_with_news"] in ("yes", "no", "no_trade", "no_market")
    # news moved probability toward realized YES outcome -> helped
    assert d["news_helped_outcome"] is True
    assert d["news_hurt_outcome"] is False


def test_diagnostics_detect_hurt_outcome():
    d = news_conditioned_diagnostics(
        prob_without_news=0.55, prob_with_news=0.40, p_market=0.50, outcome=1)
    assert d["news_hurt_outcome"] is True
    assert d["news_helped_outcome"] is False


def test_veto_forces_no_trade_decision():
    d = news_conditioned_diagnostics(
        prob_without_news=0.7, prob_with_news=0.7, p_market=0.5,
        news_veto_applied=True)
    assert d["decision_with_news"] == "no_trade"
    assert d["news_veto_applied"] is True


def test_ablation_report_computes_with_and_without_metrics():
    # news consistently nudges toward the realized outcome -> better Brier
    rows = []
    for i in range(20):
        y = i % 2
        pwo = 0.5
        pwn = 0.6 if y == 1 else 0.4
        rows.append({"probability_without_news": pwo, "probability_with_news": pwn,
                     "outcome": y, "category": "sports"})
    rep = news_ablation_report(rows)
    assert rep["n_rows"] == 20
    assert rep["n_resolved"] == 20
    assert rep["ensemble_with_news_brier"] < rep["ensemble_without_news_brier"]
    assert rep["news_helped_count"] >= rep["news_hurt_count"]
    # a category where news helped should get a positive recommended weight
    assert rep["recommended_news_weight_by_category"]["sports"] > 0.0


def test_ablation_zero_weight_when_news_hurts():
    rows = []
    for i in range(20):
        y = i % 2
        pwo = 0.6 if y == 1 else 0.4     # already good
        pwn = 0.4 if y == 1 else 0.6     # news makes it worse
        rows.append({"probability_without_news": pwo, "probability_with_news": pwn,
                     "outcome": y, "category": "politics"})
    rep = news_ablation_report(rows)
    assert rep["ensemble_with_news_brier"] > rep["ensemble_without_news_brier"]
    assert rep["recommended_news_weight_by_category"]["politics"] == 0.0
    assert rep["news_hurt_count"] >= rep["news_helped_count"]


def test_ablation_handles_unresolved_rows():
    rows = [{"probability_without_news": 0.5, "probability_with_news": 0.55,
             "category": "crypto"}]   # no outcome
    rep = news_ablation_report(rows)
    assert rep["n_rows"] == 1
    assert rep["n_resolved"] == 0
    assert rep["news_neutral_count"] == 1
    assert rep["recommended_news_weight_by_category"]["crypto"] == 0.0

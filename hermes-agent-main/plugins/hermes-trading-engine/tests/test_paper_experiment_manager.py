"""Paper experiment manager — controlled strategy-variant experiments.

Quant scope — *Monitoring* + *Strategy Optimization* + *Compliance/Security*:
proves variant classification, paper-only budget allocation across variants
(Bregman first when certified opportunities exist), variant-level metric
separation, and champion/challenger reporting. PAPER ONLY — the manager only
ever distributes evaluation/trade SLOTS; it never sizes orders or relaxes a cap.
"""

from __future__ import annotations

import pytest

from engine.training.experiment_manager import (
    BREGMAN_VARIANT, STRATEGY_VARIANTS, ExperimentManager, classify_variant)


# --------------------------------------------------------------------------- #
# variant classification
# --------------------------------------------------------------------------- #
def test_classify_variant_covers_every_strategy():
    assert classify_variant(strategy="bregman_arbitrage") == "bregman"
    assert classify_variant(strategy="bregman") == "bregman"
    assert classify_variant(strategy="directional", exploration=True) == "exploration"
    assert classify_variant(strategy="directional", chainlink_linked=True) == "chainlink_edge"
    assert classify_variant(strategy="statistical_mispricing") == "statistical_edge"
    assert classify_variant(strategy="directional") == "directional_edge"
    # bregman + exploration: bregman wins (priority-1 strategy)
    assert classify_variant(strategy="bregman", exploration=True) == "bregman"
    for v in (classify_variant(strategy=s) for s in
              ("bregman", "statistical_mispricing", "directional")):
        assert v in STRATEGY_VARIANTS


# --------------------------------------------------------------------------- #
# paper-only budget allocation across variants
# --------------------------------------------------------------------------- #
def test_allocation_never_exceeds_total_slots():
    em = ExperimentManager(experiment_id="e1")
    for total in (0, 1, 3, 7, 20):
        alloc = em.allocate(total, bregman_available=True)
        assert sum(alloc.values()) <= total
        assert all(v >= 0 for v in alloc.values())


def test_bregman_gets_first_budget_priority_when_available():
    em = ExperimentManager(experiment_id="e1")
    # a single slot goes to Bregman when a certified opportunity exists
    alloc1 = em.allocate(1, bregman_available=True)
    assert alloc1[BREGMAN_VARIANT] == 1
    assert sum(v for k, v in alloc1.items() if k != BREGMAN_VARIANT) == 0
    # with several slots, Bregman still reserved first, others share the rest
    alloc = em.allocate(8, bregman_available=True)
    assert alloc[BREGMAN_VARIANT] >= 1
    assert sum(alloc.values()) <= 8


def test_no_bregman_budget_when_no_certified_opportunity():
    em = ExperimentManager(experiment_id="e1")
    alloc = em.allocate(8, bregman_available=False)
    assert alloc[BREGMAN_VARIANT] == 0
    assert sum(alloc.values()) <= 8
    # the non-Bregman variants still receive the slots
    assert sum(v for k, v in alloc.items() if k != BREGMAN_VARIANT) == sum(alloc.values())


def test_aggressive_spreads_budget_across_more_variants():
    base = ExperimentManager(experiment_id="b", aggressive=False)
    aggr = ExperimentManager(experiment_id="a", aggressive=True)
    a_alloc = aggr.allocate(8, bregman_available=False)
    # aggressive mode gives coverage to more distinct variants
    a_nonzero = sum(1 for k, v in a_alloc.items() if v > 0 and k != BREGMAN_VARIANT)
    assert a_nonzero >= 3
    # but the combined allocation still never exceeds the slot budget (hard cap)
    assert sum(a_alloc.values()) <= 8
    assert sum(base.allocate(8, bregman_available=False).values()) <= 8


# --------------------------------------------------------------------------- #
# recording + metric separation
# --------------------------------------------------------------------------- #
def test_records_are_tagged_and_separated_by_variant():
    em = ExperimentManager(experiment_id="exp42", starting_bankroll=100.0)
    # directional: two winning trades
    for _ in range(2):
        em.record_trade("directional_edge", notional=5.0)
        em.record_fill("directional_edge", filled=True)
        em.record_feedback("directional_edge", predicted_prob=0.7, win=True,
                           realized_pnl=2.0, net_edge=0.05, cost=5.0)
    # statistical: two losing trades
    for _ in range(2):
        em.record_trade("statistical_edge", notional=5.0)
        em.record_fill("statistical_edge", filled=True)
        em.record_feedback("statistical_edge", predicted_prob=0.7, win=False,
                           realized_pnl=-2.0, net_edge=0.05, cost=5.0)

    vm = em.variant_metrics()
    assert vm["directional_edge"]["trade_count"] == 2
    assert vm["statistical_edge"]["trade_count"] == 2
    assert vm["directional_edge"]["feedback_count"] == 2
    # separation: opposite realized edge by variant
    assert vm["directional_edge"]["realized_edge"] > 0
    assert vm["statistical_edge"]["realized_edge"] < 0
    # variant with no activity reports zeroed metrics, not someone else's
    assert vm["chainlink_edge"]["trade_count"] == 0


def test_variant_metrics_have_full_quant_field_set():
    em = ExperimentManager(experiment_id="e", starting_bankroll=100.0)
    for i in range(6):
        em.record_trade("directional_edge", notional=5.0)
        em.record_fill("directional_edge", filled=(i % 2 == 0))
        em.record_feedback("directional_edge", predicted_prob=0.6,
                           win=(i % 2 == 0), realized_pnl=1.0 if i % 2 == 0 else -1.0,
                           net_edge=0.03, cost=5.0)
    m = em.variant_metrics()["directional_edge"]
    for k in ("trade_count", "feedback_count", "sharpe", "sortino", "calmar",
              "max_drawdown", "brier", "log_loss", "ece", "realized_edge",
              "fill_quality"):
        assert k in m
    assert 0.0 <= m["fill_quality"] <= 1.0  # 3 of 6 fills


# --------------------------------------------------------------------------- #
# champion / challenger
# --------------------------------------------------------------------------- #
def test_champion_challenger_ranks_by_performance():
    em = ExperimentManager(experiment_id="e", starting_bankroll=100.0)
    for _ in range(5):
        em.record_trade("directional_edge", notional=5.0)
        em.record_feedback("directional_edge", predicted_prob=0.7, win=True,
                           realized_pnl=3.0, net_edge=0.06, cost=5.0)
        em.record_trade("statistical_edge", notional=5.0)
        em.record_feedback("statistical_edge", predicted_prob=0.7, win=False,
                           realized_pnl=-3.0, net_edge=0.06, cost=5.0)
    cc = em.champion_challenger()
    assert cc["champion"] == "directional_edge"
    assert "statistical_edge" in cc["challengers"]
    assert cc["ranking"][0] == "directional_edge"


def test_champion_none_without_feedback():
    em = ExperimentManager(experiment_id="e")
    assert em.champion_challenger()["champion"] is None

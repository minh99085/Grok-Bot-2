"""Exploration budget + diversity + gate-safety controls.

Aggressive paper mode must trade MORE without (a) exceeding the strict paper
exploration budget, (b) over-trading one event/category, or (c) EVER selecting a
hard-gated market (stale book / invalid / chainlink-stale / risk cap). PAPER-ONLY.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.training.active_learning import ActiveLearningSelector


def _cfg(**kw):
    base = dict(active_learning_enabled=True, exploration_split=1.0,
                exploration_min_edge=-0.05, exploration_notional_usd=2.0,
                exploration_budget_usd=6.0, category_sample_target=50,
                max_explore_per_category=2, max_explore_per_event=1)
    base.update(kw)
    return SimpleNamespace(**base)


def _fb(mid, *, cat="crypto", group=None, fv=0.5):
    return {"market_id": mid, "category": cat, "group_key": group or mid,
            "edge_reason": "edge_too_low", "net_edge": 0.0, "feedback_value": fv}


def test_exploration_budget_is_strict():
    # 10 eligible feedback candidates, budget only allows 3 @ $2 = $6.
    pool = [_fb(f"m{i}", cat=f"c{i}", group=f"g{i}", fv=0.9 - i * 0.01) for i in range(10)]
    res = ActiveLearningSelector(_cfg(exploration_budget_usd=6.0,
                                      max_explore_per_category=10)).select(pool, budget=50)
    assert res.diagnostics["selected_for_feedback"] == 3
    assert res.diagnostics["exploration_budget_used"] <= 6.0 + 1e-9
    assert res.diagnostics["exploration_budget_used"] == pytest.approx(6.0)


def test_per_event_diversity_cap():
    # 4 candidates in the SAME event group; max_explore_per_event=1.
    pool = [_fb(f"m{i}", cat=f"c{i}", group="same_event", fv=0.9 - i * 0.01) for i in range(4)]
    res = ActiveLearningSelector(_cfg(max_explore_per_event=1, max_explore_per_category=10,
                                      exploration_budget_usd=100.0)).select(pool, budget=50)
    assert res.diagnostics["selected_for_feedback"] == 1


def test_per_category_diversity_cap():
    # 5 candidates in the SAME category; max_explore_per_category=2.
    pool = [_fb(f"m{i}", cat="crypto", group=f"g{i}", fv=0.9 - i * 0.01) for i in range(5)]
    res = ActiveLearningSelector(_cfg(max_explore_per_category=2, max_explore_per_event=1,
                                      exploration_budget_usd=100.0)).select(pool, budget=50)
    assert res.diagnostics["selected_for_feedback"] == 2


def test_over_target_category_deprioritized():
    # Two equal-feedback candidates; one category is already over its sample
    # target -> the under-target one is preferred when only one slot remains.
    pool = [_fb("under", cat="rare", group="g1", fv=0.6),
            _fb("over", cat="common", group="g2", fv=0.6)]
    res = ActiveLearningSelector(_cfg(category_sample_target=50, exploration_budget_usd=2.0)).select(
        pool, budget=50, category_counts={"common": 999, "rare": 0})
    assert res.diagnostics["selected_for_feedback"] == 1
    assert res.selected[0]["market_id"] == "under"


def test_hard_gate_markets_never_selected_even_with_high_value():
    # Every dirty/hard-gated reason must be rejected, never explored.
    bad = [
        _fb("stale", fv=0.99), _fb("invalid", fv=0.99), _fb("clstale", fv=0.99),
        _fb("riskcap", fv=0.99),
    ]
    bad[0]["edge_reason"] = "no_fresh_book"
    bad[1]["edge_reason"] = "no_executable_price"
    bad[2]["edge_reason"] = "chainlink_stale_or_irrelevant"
    bad[3]["edge_reason"] = "risk_rejected"
    res = ActiveLearningSelector(_cfg(exploration_budget_usd=100.0)).select(bad, budget=50)
    assert res.selected == []
    assert res.diagnostics["rejected_by_hard_gate"] == 4
    # explicit safety assertion: none of the hard-gated ids leaked into selection
    selected_ids = {s["market_id"] for s in res.selected}
    assert selected_ids.isdisjoint({"stale", "invalid", "clstale", "riskcap"})


def test_exploration_notional_never_exceeds_paper_cap():
    # Even if a huge exploration size is requested, it is clamped to the paper
    # order-notional ceiling (cannot bypass risk caps).
    pool = [_fb("m0", fv=0.9)]
    res = ActiveLearningSelector(_cfg(exploration_notional_usd=999.0,
                                      max_order_notional_usd=5.0,
                                      exploration_budget_usd=100.0)).select(pool, budget=5)
    assert res.selected[0]["notional"] <= 5.0

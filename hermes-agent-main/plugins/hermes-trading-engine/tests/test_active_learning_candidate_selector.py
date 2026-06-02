"""Active-learning candidate selection — fills unused PAPER budget with the
highest-feedback-value near-miss trades WITHOUT bypassing any risk gate.

Bregman arbitrage (P1) is reserved first; edge trades (exploitation) next;
remaining slots are filled by feedback value (exploration). Hard-gate rejects
(stale book / invalid market / chainlink-stale / thin depth / risk cap) can
NEVER be selected. PAPER-ONLY.
"""

from __future__ import annotations

from types import SimpleNamespace

from engine.training.active_learning import ActiveLearningSelector
from engine.training.edge_engine import (
    HARD_GATE_REASONS,
    NEAR_MISS_REASONS,
    is_hard_gate_reason,
    is_near_miss,
)


def _cfg(**kw):
    base = dict(active_learning_enabled=True, exploration_split=0.5,
                exploration_min_edge=-0.05, exploration_notional_usd=2.0,
                exploration_budget_usd=20.0, category_sample_target=50,
                max_explore_per_category=3, max_explore_per_event=1)
    base.update(kw)
    return SimpleNamespace(**base)


def _cand(mid, reason, *, cat="crypto", group=None, net_edge=0.0, fv=0.5, bregman=False):
    return {"market_id": mid, "category": cat, "group_key": group or mid,
            "edge_reason": reason, "net_edge": net_edge, "feedback_value": fv,
            "bregman": bregman}


def test_edge_reason_taxonomy_is_coherent():
    assert NEAR_MISS_REASONS == frozenset({"edge_too_low", "uncertainty_too_high"})
    assert "no_fresh_book" in HARD_GATE_REASONS
    assert "chainlink_stale_or_irrelevant" in HARD_GATE_REASONS
    assert "depth_too_thin" in HARD_GATE_REASONS
    assert is_hard_gate_reason("no_fresh_book")
    assert is_near_miss("edge_too_low")
    assert not is_hard_gate_reason("trade")
    assert not is_near_miss("trade")


def test_hard_gate_candidates_never_selected():
    cands = [
        _cand("m1", "no_fresh_book", fv=0.99),
        _cand("m2", "chainlink_stale_or_irrelevant", fv=0.99),
        _cand("m3", "depth_too_thin", fv=0.99),
        _cand("m4", "risk_rejected", fv=0.99),
    ]
    res = ActiveLearningSelector(_cfg()).select(cands, budget=10)
    assert res.selected == []
    assert res.diagnostics["rejected_by_hard_gate"] == 4
    assert res.diagnostics["selected_for_feedback"] == 0


def test_edge_trades_selected_for_exploitation():
    cands = [_cand("e1", "trade", net_edge=0.06), _cand("e2", "trade", net_edge=0.04)]
    res = ActiveLearningSelector(_cfg()).select(cands, budget=10)
    modes = {s["market_id"]: s["mode"] for s in res.selected}
    assert modes == {"e1": "edge", "e2": "edge"}
    assert res.diagnostics["selected_for_edge"] == 2


def test_near_miss_filled_by_feedback_value():
    cands = [
        _cand("f_lo", "edge_too_low", group="ga", fv=0.30),
        _cand("f_hi", "uncertainty_too_high", group="gb", fv=0.90),
        _cand("f_mid", "edge_too_low", group="gc", fv=0.60),
    ]
    res = ActiveLearningSelector(_cfg(max_explore_per_category=5)).select(cands, budget=2)
    fb = [s for s in res.selected if s["mode"] == "feedback"]
    # highest feedback value first, capped by budget slots (2)
    assert [s["market_id"] for s in fb] == ["f_hi", "f_mid"]
    assert res.diagnostics["selected_for_feedback"] == 2


def test_bregman_reserved_first_and_counted():
    cands = [_cand("b1", "trade", bregman=True), _cand("e1", "trade", net_edge=0.05),
             _cand("f1", "edge_too_low", fv=0.8, group="gz")]
    res = ActiveLearningSelector(_cfg(max_explore_per_category=5)).select(
        cands, budget=2, bregman_selected=1)
    # budget 2, bregman reserves 1 slot -> only 1 more selectable (the edge trade)
    assert res.diagnostics["selected_for_bregman"] == 1
    assert len(res.selected) == 1
    assert res.selected[0]["market_id"] == "e1"


def test_diagnostics_keys_present():
    res = ActiveLearningSelector(_cfg()).select([_cand("x", "trade")], budget=3)
    for k in ("candidates_skipped", "selected_for_edge", "selected_for_feedback",
              "selected_for_bregman", "rejected_by_hard_gate",
              "exploration_budget_used", "slots", "slots_used"):
        assert k in res.diagnostics


def test_disabled_active_learning_skips_feedback():
    cands = [_cand("e1", "trade", net_edge=0.05), _cand("f1", "edge_too_low", fv=0.9)]
    res = ActiveLearningSelector(_cfg(active_learning_enabled=False)).select(cands, budget=10)
    assert res.diagnostics["selected_for_feedback"] == 0
    assert res.diagnostics["selected_for_edge"] == 1   # exploitation still works


def test_below_exploration_min_edge_skipped():
    cands = [_cand("f1", "edge_too_low", net_edge=-0.20, fv=0.9)]  # below min edge
    res = ActiveLearningSelector(_cfg(exploration_min_edge=-0.05)).select(cands, budget=5)
    assert res.diagnostics["selected_for_feedback"] == 0
    assert res.diagnostics["candidates_skipped"] >= 1

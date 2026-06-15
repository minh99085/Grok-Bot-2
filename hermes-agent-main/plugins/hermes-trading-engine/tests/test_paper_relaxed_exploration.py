"""PAPER_RELAXED_EXPLORATION lane (PAPER ONLY) — hour/day rate limits + report metrics.

This lane is the same $1-capped, real-CLOB, positive-after-cost paper-exploration lane
as ``tests/test_paper_micro_exploration.py`` (which covers the stale/missing-ask/
synthetic-NO/reference/negative-edge rejections, PnL separation, and live-disabled
invariants). Here we prove the NEW requirements: per-hour and per-day caps, the
``paper_relaxed_*`` report metrics, real-CLOB requirement, and exact zero-trade blocker.
"""

import time

from engine.training import PolymarketPaperTrainer, TrainingConfig
from engine.markets import universe_manager as um
from tests._pmtrain_helpers import clean_live_env, market

_NOW = 1_792_000_000.0


def _trainer(tmp_path, monkeypatch, **cfg):
    clean_live_env(monkeypatch, tmp_path)
    return PolymarketPaperTrainer(
        TrainingConfig(mode="paper_train", max_open_trades=8, **cfg), data_dir=tmp_path)


def _books(yes_ask=0.45, no_ask=0.50, *, age=2.0):
    ts = str(_NOW - age)
    return {"tok0a": {"asks": [{"price": str(yes_ask), "size": "22"}],
                      "bids": [{"price": str(round(yes_ask - 0.01, 4)), "size": "30"}],
                      "timestamp": ts},
            "tok0b": {"asks": [{"price": str(no_ask), "size": "20"}],
                      "bids": [{"price": str(round(no_ask - 0.01, 4)), "size": "30"}],
                      "timestamp": ts}}


def _rec(mid=0):
    raw = market(mid, bid=0.44, ask=0.45, depth=10, now=_NOW)
    return um.MarketRecord.from_raw(raw, now=_NOW)


def _enable(t, books=None):
    t.enable_clob_hydration(book_fetcher=lambda tok: (books or _books()).get(tok),
                            max_book_age_s=120.0)


# --------------------------------------------------------------------------- #
# Allowed + report metrics
# --------------------------------------------------------------------------- #
def test_relaxed_trade_allowed_and_metrics_present(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    _enable(t)
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    assert m["paper_relaxed_exploration_enabled"] is True
    assert m["paper_relaxed_max_notional"] == 1.0
    assert m["paper_relaxed_max_trades_per_hour"] == 3
    assert m["paper_relaxed_max_trades_per_day"] == 30
    assert m["paper_relaxed_candidates_seen"] >= 1
    assert m["paper_relaxed_trades_opened"] >= 1
    assert m["paper_relaxed_after_cost_positive_seen"] >= 1
    assert m["paper_relaxed_real_clob_book_seen"] >= 1
    assert m["paper_relaxed_readiness_pnl_excluded"] is True
    assert m["bregman_clob_hydration_coverage_rate"] >= 0.0
    assert m["zero_trade_blocker_if_any"] == ""
    # trade is tagged exploration and excluded from readiness PnL
    assert [p for p in t.positions if p.exploration]
    rep = t.paper_realism_report()
    assert rep["readiness_pnl"] == 0.0


def test_relaxed_requires_real_clob_book(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    # no hydration -> NO leg synthetic -> not a real CLOB book -> no relaxed trade
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    assert m["paper_relaxed_trades_opened"] == 0
    assert not [p for p in t.positions if p.exploration]


def test_relaxed_negative_edge_blocked_with_durable_reason(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    _enable(t, _books(0.55, 0.50))                      # YES+NO = 1.05 -> negative edge
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    assert m["paper_relaxed_trades_opened"] == 0
    assert m["paper_relaxed_after_cost_positive_seen"] == 0
    assert "no_positive_after_cost" in m["zero_trade_blocker_if_any"]


# --------------------------------------------------------------------------- #
# Rate limits
# --------------------------------------------------------------------------- #
def test_per_hour_cap_enforced(tmp_path, monkeypatch):
    # 5 distinct fresh real-book opportunities in one tick (same _NOW => same hour),
    # hour cap = 2 => at most 2 open.
    t = _trainer(tmp_path, monkeypatch, paper_relaxed_max_trades_per_hour=2)
    books = {}
    recs = []
    for i in range(5):
        b = _books()
        books[f"tok{i}a"] = dict(b["tok0a"]); books[f"tok{i}b"] = dict(b["tok0b"])
        recs.append(_rec(i))
    t.enable_clob_hydration(book_fetcher=lambda tok: books.get(tok), max_book_age_s=120.0)
    t._run_bregman(recs, _NOW)
    assert t._micro_exploration_trades_total <= 2
    assert t.bregman_exec_metrics["paper_relaxed_trades_opened"] <= 2


def test_per_day_cap_enforced(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, paper_relaxed_max_trades_per_hour=100,
                 paper_relaxed_max_trades_per_day=2)
    books = {}
    recs = []
    for i in range(5):
        b = _books()
        books[f"tok{i}a"] = dict(b["tok0a"]); books[f"tok{i}b"] = dict(b["tok0b"])
        recs.append(_rec(i))
    t.enable_clob_hydration(book_fetcher=lambda tok: books.get(tok), max_book_age_s=120.0)
    t._run_bregman(recs, _NOW)
    assert t._micro_exploration_trades_total <= 2


def test_hour_budget_resets_after_window(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, paper_relaxed_max_trades_per_hour=1,
                 paper_relaxed_max_trades_per_day=30)
    # distinct markets per tick (a re-used market is deduped as already-open)
    books = {}
    for i in range(3):
        b = _books()
        books[f"tok{i}a"] = dict(b["tok0a"]); books[f"tok{i}b"] = dict(b["tok0b"])
    # large freshness window so the simulated >1h time jump tests ONLY the rate limit
    t.enable_clob_hydration(book_fetcher=lambda tok: books.get(tok), max_book_age_s=1_000_000.0)
    t._run_bregman([_rec(0)], _NOW)
    assert t._micro_exploration_trades_total == 1
    # same hour, different market -> still capped at 1 (hour cap = 1)
    t._run_bregman([_rec(1)], _NOW + 60)
    assert t._micro_exploration_trades_total == 1
    # >1h later -> the hour budget frees up, another trade allowed (day cap still ok)
    t._run_bregman([_rec(2)], _NOW + 3700)
    assert t._micro_exploration_trades_total == 2


def test_relaxed_disabled_flag_blocks_lane(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, paper_relaxed_exploration_enabled=False)
    _enable(t)
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    assert m["paper_relaxed_exploration_enabled"] is False
    assert m["paper_relaxed_trades_opened"] == 0
    assert not [p for p in t.positions if p.exploration]


def test_relaxed_candidate_stream_metrics_present(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    _enable(t)
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    # real-book candidate STREAM (not only certified bundles) is surfaced
    assert m["paper_relaxed_real_book_candidates_seen"] >= 1
    assert m["paper_relaxed_positive_real_book_candidates_seen"] >= 1
    assert isinstance(m["paper_relaxed_candidate_source_counts"], dict)
    assert m["paper_relaxed_candidate_source_counts"].get("binary_yes_no", 0) >= 1
    assert m["paper_relaxed_best_real_book_candidate"].get("after_cost_edge", 0) > 0
    assert isinstance(m["paper_relaxed_candidates_blocked_by_reason"], dict)


def test_relaxed_negative_edge_records_blocked_reason_and_example(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    _enable(t, _books(0.55, 0.50))                     # negative after-cost edge
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    assert m["paper_relaxed_real_book_candidates_seen"] >= 1     # it IS on the stream
    assert m["paper_relaxed_positive_real_book_candidates_seen"] == 0
    assert m["paper_relaxed_candidates_blocked_by_reason"].get("negative_after_cost_edge", 0) >= 1
    assert "not_real_clob_book" not in m["paper_relaxed_candidates_blocked_by_reason"]
    assert m["paper_relaxed_best_reject_example"].get("reject_reason") == "negative_after_cost_edge"
    assert "real_book_candidates_but_no_positive_after_cost_edge" in m["zero_trade_blocker_if_any"]


def test_durable_per_candidate_records_written(tmp_path, monkeypatch):
    import json
    t = _trainer(tmp_path, monkeypatch)
    _enable(t)
    t._run_bregman([_rec()], _NOW)
    path = tmp_path / "metrics" / "paper_relaxed_candidates.jsonl"
    assert path.is_file()
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    assert rows
    r = rows[0]
    # full audit fields per the spec
    for k in ("market_ids", "token_ids", "outcomes", "book_age_s", "best_asks",
              "best_bids", "depth_for_1usd", "est_costs", "after_cost_edge",
              "gate_result", "reject_reason", "is_real_book", "ts"):
        assert k in r


def test_diagnostic_not_contradictory_when_real_books_seen(tmp_path, monkeypatch):
    # real CLOB books seen, no positive candidate -> blocker must NOT be
    # not_real_clob_book and best_after_cost_edge must be consistent (negative).
    t = _trainer(tmp_path, monkeypatch)
    _enable(t, _books(0.55, 0.50))
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    assert m["paper_relaxed_real_book_candidates_seen"] >= 1
    blocker = m["zero_trade_blocker_if_any"]
    assert "not_real_clob_book" not in blocker
    assert "not_real_clob_book" not in m["paper_relaxed_candidates_blocked_by_reason"]
    # best edge in the blocker is negative (consistent with "no positive")
    assert "best_after_cost_edge=-" in blocker


def test_opened_trade_example_marks_exploration_paper(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    _enable(t)
    t._run_bregman([_rec()], _NOW)
    ex = t.bregman_exec_metrics["paper_relaxed_opened_trade_examples"]
    assert ex and ex[0]["exploration_paper"] is True
    assert ex[0]["notional_usd"] <= 1.0 and ex[0]["paper_order_id"]


def test_pipeline_scanned_metric_present(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    _enable(t)
    t._run_bregman([_rec()], _NOW)
    assert t.bregman_exec_metrics["paper_relaxed_pipeline_scanned"] >= 1


def test_missing_no_leg_is_not_a_positive_real_book_candidate(tmp_path, monkeypatch):
    """Regression for the '0.999 + not_real_clob_book' contradiction: a group whose NO
    book is missing (NO leg stays synthetic, not hydrated) must NOT count as a positive
    real-book candidate, and the blocker must be non-contradictory (no positive edge,
    no not_real_clob_book in the candidate-stream blocker)."""
    t = _trainer(tmp_path, monkeypatch)
    # only the YES token has a real book; NO token book is absent -> NO leg synthetic
    books = {"tok0a": {"asks": [{"price": "0.001", "size": "9999999"}],
                       "bids": [{"price": "0.0009", "size": "9999"}], "timestamp": str(_NOW - 2)}}
    t.enable_clob_hydration(book_fetcher=lambda tok: books.get(tok), max_book_age_s=120.0)
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    # not a positive real-book candidate; no fake 0.999 edge; nothing traded
    assert m["paper_relaxed_positive_real_book_candidates_seen"] == 0
    assert m["paper_relaxed_trades_opened"] == 0
    blocker = m["zero_trade_blocker_if_any"]
    # non-contradictory: a positive edge is never claimed while saying not_real_clob_book
    assert not ("not_real_clob_book" in blocker and "best_after_cost_edge=0.99" in blocker)
    assert "0.999" not in blocker                     # the misleading projected edge is gone


def test_relaxed_opens_even_when_certification_finds_zero(tmp_path, monkeypatch):
    """Root-blocker-1 regression: the relaxed $1 paper lane is computed DIRECTLY from
    the hydrated real-CLOB book and must open even when FULL Bregman certification
    certifies ZERO opportunities (no certifier_disagreed block)."""
    from engine.training import bregman_execution as bx
    t = _trainer(tmp_path, monkeypatch)
    _enable(t)
    # Force certification to find ZERO full opportunities (reject every group).
    orig = bx.BregmanArbitrageEngine.certify

    def _always_reject(self, group, **kw):
        opp = orig(self, group, **kw)
        opp.certified = False
        opp.profit_lower_bound = 0.0           # is_opportunity -> False
        return opp
    monkeypatch.setattr(bx.BregmanArbitrageEngine, "certify", _always_reject)
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    assert m["certified_opportunities"] == 0           # certification found nothing
    assert m["paper_relaxed_real_book_candidates_seen"] >= 1
    assert m["paper_relaxed_positive_real_book_candidates_seen"] >= 1
    assert m["paper_relaxed_candidates_seen"] >= 1
    assert m["paper_relaxed_trades_opened"] >= 1        # ...but the paper lane still traded
    assert [p for p in t.positions if p.exploration]
    # the removed certifier gate must never reappear as a reject reason
    assert "certifier_disagreed" not in m["paper_relaxed_reject_reasons"]


def test_full_readiness_gates_not_loosened(tmp_path, monkeypatch):
    # The relaxed lane must not turn a thin/sub-margin opportunity into a CERTIFIED
    # readiness opportunity: certified_opportunities stays 0 while the lane still trades.
    t = _trainer(tmp_path, monkeypatch)
    _enable(t)
    t._run_bregman([_rec()], _NOW)
    m = t.bregman_exec_metrics
    assert m["certified_opportunities"] == 0          # full readiness path unchanged
    assert m["paper_relaxed_trades_opened"] >= 1       # but the paper lane traded
    rep = t.paper_realism_report()
    assert rep["readiness_pnl"] == 0.0                # readiness PnL excludes exploration


def test_positive_candidates_rejected_before_open_have_exact_reasons(tmp_path, monkeypatch):
    """Regression for the contradictory relaxed blocker: when positive real-book
    candidates exist (e.g. 6) but were REJECTED before opening (incomplete_event_family),
    the zero-trade blocker must carry the EXACT stream-level reject reasons (never an empty
    dict), must name the dominant reason, and must NOT mislabel them as 'unfilled'. Bregman
    incomplete_event_family stays strict — this asserts reporting only."""
    t = _trainer(tmp_path, monkeypatch)
    # simulate the uploaded-report state: positive real-book candidates seen, but every
    # one rejected at the candidate-STREAM stage (incomplete_event_family) so NONE reached
    # the open path (GATE_TRADABLE == 0) and the open-time reject dict is empty.
    t._relaxed_real_book_seen = 48015
    t._relaxed_positive_real_book_seen = 6
    t._relaxed_blocked_by_reason = {"incomplete_event_family": 6}
    t._relaxed_best_reject = {"reject_reason": "incomplete_event_family", "after_cost_edge": 0.02}
    t._micro_exploration_candidates_total = 0          # nothing reached GATE_TRADABLE
    t._micro_exploration_reject_reasons = {}           # open-time dict legitimately empty

    t._update_micro_metrics(enabled=True)
    blocker = t.bregman_exec_metrics["zero_trade_blocker_if_any"]

    # exact reasons are surfaced (no empty reject_reasons when positive candidates exist)
    assert "incomplete_event_family" in blocker
    assert "reject_reasons={}" not in blocker
    assert "dominant_reject_reason=incomplete_event_family" in blocker
    # rejected BEFORE the open path -> must NOT be called 'unfilled'
    assert "positive_candidates_rejected_before_open" in blocker
    assert "positive_candidates_found_but_unfilled" not in blocker


def test_positive_candidates_unfilled_at_open_still_reported(tmp_path, monkeypatch):
    """If positive candidates DID reach the open path (GATE_TRADABLE > 0) but failed at
    open time, the open-time reject reasons are surfaced and the 'unfilled' label is used."""
    t = _trainer(tmp_path, monkeypatch)
    t._relaxed_real_book_seen = 100
    t._relaxed_positive_real_book_seen = 3
    t._relaxed_blocked_by_reason = {}
    t._micro_exploration_candidates_total = 3          # reached the open path
    t._micro_exploration_reject_reasons = {"missing_executable_ask": 3}

    t._update_micro_metrics(enabled=True)
    blocker = t.bregman_exec_metrics["zero_trade_blocker_if_any"]
    assert "positive_candidates_found_but_unfilled" in blocker
    assert "missing_executable_ask" in blocker
    assert "reject_reasons={}" not in blocker

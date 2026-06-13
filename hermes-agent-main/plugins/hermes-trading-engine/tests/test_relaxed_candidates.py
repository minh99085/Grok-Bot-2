"""Unit tests for the decoupled relaxed real-book candidate evaluator.

The candidate stream is computed DIRECTLY from hydrated books (no Bregman
certification dependency). These prove each hard gate, the positive-edge path, the
incomplete-family (positive-but-not-tradable) path, and the non-contradictory
diagnostics (un-hydrated groups are NOT counted as candidate rejections).
"""

from engine.training.bregman_grouping import SimplexGroup, SimplexLeg
from engine.training import relaxed_candidates as rc

_NOW = 1_795_000_000.0


def _leg(outcome, ask, bid, *, real=True, fresh=True, stale=False, depth=50.0,
         synthetic=False, tok="t"):
    return SimplexLeg(market_id="m", outcome=outcome, token_id=tok, ask=ask, bid=bid,
                      depth_usd=depth, visible_ask_depth_usd=depth, fresh_book=fresh,
                      stale=stale, synthetic_price=synthetic, hydrated_from_clob=real,
                      book_age_s=2.0)


def _binary(yes_ask=0.45, no_ask=0.50, **legkw):
    legs = [_leg("YES", yes_ask, yes_ask - 0.01, tok="ta", **legkw),
            _leg("NO", no_ask, no_ask - 0.01, tok="tb", **legkw)]
    return SimplexGroup("g", "binary_yes_no", legs, mutually_exclusive=True, exhaustive=True)


def _ev(*, now=_NOW):
    return dict(now=now, max_notional_usd=1.0, min_depth_usd=1.0, slippage_bps=25.0,
                fee_bps=0.0, max_book_age_s=20.0)


# --------------------------------------------------------------------------- #
# Positive / tradable
# --------------------------------------------------------------------------- #
def test_positive_real_book_is_tradable():
    r = rc.evaluate_relaxed_group(_binary(0.45, 0.50), **_ev())
    assert r["is_real_book"] and r["positive"] and r["tradable"]
    assert r["gate_result"] == rc.GATE_TRADABLE
    assert r["after_cost_edge"] > 0 and r["reject_reason"] == ""
    # durable audit fields present
    for k in ("market_ids", "token_ids", "outcomes", "book_age_s", "best_asks",
              "best_bids", "depth_for_1usd", "est_costs", "source_strategy"):
        assert k in r


# --------------------------------------------------------------------------- #
# Hard rejects (NEVER loosened) — all are real-book candidates that BLOCK
# --------------------------------------------------------------------------- #
def test_reject_negative_after_cost_edge():
    r = rc.evaluate_relaxed_group(_binary(0.55, 0.50), **_ev())
    assert r["is_real_book"] and not r["tradable"]
    assert r["reject_reason"] == rc.R_NEG_EDGE and r["after_cost_edge"] <= 0


def test_reject_stale_book():
    r = rc.evaluate_relaxed_group(_binary(0.45, 0.50, stale=True, fresh=False), **_ev())
    assert r["is_real_book"] and r["reject_reason"] == rc.R_STALE and not r["tradable"]


def test_reject_missing_ask():
    g = _binary(0.45, 0.50)
    g.legs[1].ask = None
    r = rc.evaluate_relaxed_group(g, **_ev())
    assert r["is_real_book"] and r["reject_reason"] == rc.R_MISSING_ASK


def test_reject_synthetic_no():
    g = _binary(0.45, 0.50)
    g.legs[1].synthetic_price = True
    r = rc.evaluate_relaxed_group(g, **_ev())
    assert r["is_real_book"] and r["reject_reason"] == rc.R_SYNTHETIC_NO


def test_reject_depth_insufficient():
    r = rc.evaluate_relaxed_group(_binary(0.45, 0.50, depth=0.2), **_ev())
    assert r["is_real_book"] and r["reject_reason"] == rc.R_DEPTH


# --------------------------------------------------------------------------- #
# Not on the stream (un-hydrated) is NOT a candidate rejection
# --------------------------------------------------------------------------- #
def test_unhydrated_group_is_not_on_stream():
    r = rc.evaluate_relaxed_group(_binary(0.45, 0.50, real=False), **_ev())
    assert r["is_real_book"] is False
    assert r["gate_result"] == rc.GATE_NOT_ON_STREAM
    assert r["reject_reason"] == rc.R_NOT_REAL_BOOK


def test_incomplete_family_positive_but_not_tradable():
    g = _binary(0.45, 0.50)
    g.exhaustive = False                              # incomplete event family
    r = rc.evaluate_relaxed_group(g, **_ev())
    assert r["is_real_book"] and r["positive"] and not r["tradable"]
    assert r["gate_result"] == rc.GATE_POSITIVE_NOT_TRADABLE
    assert r["reject_reason"] == rc.R_INCOMPLETE_FAMILY


# --------------------------------------------------------------------------- #
# summarize(): diagnostics are non-contradictory (no not_real_clob_book in blocks)
# --------------------------------------------------------------------------- #
def test_summarize_excludes_unhydrated_from_block_reasons():
    recs = [
        rc.evaluate_relaxed_group(_binary(0.45, 0.50), **_ev()),            # tradable
        rc.evaluate_relaxed_group(_binary(0.55, 0.50), **_ev()),            # neg edge
        rc.evaluate_relaxed_group(_binary(0.45, 0.50, real=False), **_ev()),  # not on stream
        rc.evaluate_relaxed_group(_binary(0.45, 0.50, real=False), **_ev()),  # not on stream
    ]
    s = rc.summarize(recs)
    assert s["pipeline_scanned"] == 4
    assert s["real_book_candidates_seen"] == 2        # only the 2 hydrated
    assert s["positive_real_book_candidates_seen"] == 1
    assert s["tradable_candidates"] == 1
    # block reasons NEVER include the un-hydrated noise
    assert "not_real_clob_book" not in s["blocked_by_reason"]
    assert s["blocked_by_reason"].get(rc.R_NEG_EDGE) == 1
    assert s["best_real_book_candidate"]["after_cost_edge"] > 0
    assert s["best_reject_example"]["reject_reason"] == rc.R_NEG_EDGE


def test_summarize_best_edge_is_signed_consistent():
    recs = [rc.evaluate_relaxed_group(_binary(0.55, 0.50), **_ev())]   # only negative
    s = rc.summarize(recs)
    assert s["positive_real_book_candidates_seen"] == 0
    assert s["best_after_cost_edge"] < 0              # matches "no positive" (non-contradictory)

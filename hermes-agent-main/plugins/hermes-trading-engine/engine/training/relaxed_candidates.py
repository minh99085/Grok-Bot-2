"""Relaxed paper-exploration candidate stream (PAPER ONLY).

The relaxed candidate stream is computed DIRECTLY from hydrated real-CLOB books — it
does NOT depend on full Bregman certification. Bregman certification may reject a
*bundle* (e.g. incomplete event family, sub-margin ROI), but it must never prevent a
valid real-book, fresh, executable, positive-after-cost paper candidate from being
counted, diagnosed, and (optionally) paper-opened.

Each group is evaluated into a durable, auditable candidate record. Hard rejects are
NEVER loosened: stale book, missing ask, synthetic-NO execution, reference/fake fill,
negative after-cost edge, and live trading all still block a paper trade. Only a group
whose legs are ALL hydrated from the live order book counts as a *real-book candidate*;
un-hydrated groups are simply NOT on the stream (``on_stream=False``) and must never be
reported as a candidate rejection.
"""

from __future__ import annotations

from typing import Optional

# gate-result vocabulary
GATE_NOT_ON_STREAM = "not_on_stream"     # not a real-book candidate (no live book)
GATE_BLOCKED = "blocked"                 # real-book candidate, failed a hard gate
GATE_POSITIVE_NOT_TRADABLE = "positive_not_tradable"   # +edge but not a full hedge
GATE_TRADABLE = "tradable"               # +edge, full hedge, all hard gates pass

# hard reject reasons (NEVER loosened)
R_NOT_REAL_BOOK = "not_real_clob_book"
R_MISSING_ASK = "missing_ask"
R_SYNTHETIC_NO = "synthetic_no_execution"
R_STALE = "stale_book"
R_DEPTH = "depth_insufficient_for_1usd"
R_NEG_EDGE = "negative_after_cost_edge"
R_INCOMPLETE_FAMILY = "incomplete_event_family"


def _legs(group) -> list:
    return list(getattr(group, "legs", None) or [])


def _is_real_book(group) -> bool:
    """True iff EVERY leg was hydrated from a live CLOB book (real executable data)."""
    legs = _legs(group)
    return bool(legs) and all(bool(getattr(l, "hydrated_from_clob", False)) for l in legs)


def evaluate_relaxed_group(group, *, now: float, max_notional_usd: float = 1.0,
                           min_depth_usd: float = 1.0, slippage_bps: float = 25.0,
                           fee_bps: float = 0.0, max_book_age_s: float = 20.0) -> dict:
    """Evaluate one group into a durable, auditable relaxed-candidate record. Pure +
    deterministic; never raises. The record carries everything needed to audit WHY a
    real-book opportunity was or was not paper-tradable."""
    from engine.execution.slippage import drag_breakdown

    legs = _legs(group)
    payout = float(getattr(group, "payout", 1.0) or 1.0)
    book_ages = [float(getattr(l, "book_age_s", 0.0) or 0.0) for l in legs]
    rec = {
        "group_id": getattr(group, "group_id", ""),
        "group_type": getattr(group, "group_type", "unknown"),
        "source_strategy": "bregman_" + str(getattr(group, "group_type", "unknown")),
        "market_ids": [getattr(l, "market_id", "") for l in legs],
        "token_ids": [getattr(l, "token_id", "") for l in legs],
        "outcomes": [getattr(l, "outcome", "") for l in legs],
        "n_legs": len(legs),
        "book_age_s": (round(max(book_ages), 3) if book_ages else None),
        "best_asks": [getattr(l, "ask", None) for l in legs],
        "best_bids": [getattr(l, "bid", None) for l in legs],
        "exploration_paper": False,
        "paper_order_id": "",
        "is_real_book": False,
        "positive": False,
        "tradable": False,
        "after_cost_edge": None,
        "est_costs": None,
        "depth_for_1usd": None,
        "gate_result": GATE_NOT_ON_STREAM,
        "reject_reason": "",
    }

    # 1) real-book gate — un-hydrated groups are NOT on the candidate stream.
    if not _is_real_book(group):
        rec["reject_reason"] = R_NOT_REAL_BOOK
        return rec
    rec["is_real_book"] = True

    # 2) hard rejects (NEVER loosened). These DO count as real-book candidate blocks.
    if any((getattr(l, "ask", None) is None or float(getattr(l, "ask", 0) or 0) <= 0.0)
           for l in legs):
        rec["gate_result"] = GATE_BLOCKED
        rec["reject_reason"] = R_MISSING_ASK
        return rec
    if any(bool(getattr(l, "synthetic_price", False)) for l in legs):
        rec["gate_result"] = GATE_BLOCKED
        rec["reject_reason"] = R_SYNTHETIC_NO
        return rec
    # Freshness: trust the hydrator's authoritative fresh/stale flags (set from its
    # configured book-age window) so the relaxed gate matches the hydration policy.
    if any((not bool(getattr(l, "fresh_book", True))) or bool(getattr(l, "stale", False))
           for l in legs):
        rec["gate_result"] = GATE_BLOCKED
        rec["reject_reason"] = R_STALE
        return rec

    # depth: enough top-of-book ask notional for a <= $1 order on EVERY leg.
    depths = [float(getattr(l, "visible_ask_depth_usd", None)
                    or getattr(l, "depth_usd", 0.0) or 0.0) for l in legs]
    depth_for_1 = min(depths) if depths else 0.0
    rec["depth_for_1usd"] = round(depth_for_1, 4)
    if depth_for_1 < float(min_depth_usd):
        rec["gate_result"] = GATE_BLOCKED
        rec["reject_reason"] = R_DEPTH
        return rec

    # 3) after-cost edge — computed DIRECTLY from the real books (no certifier needed).
    exec_sum = 0.0
    drag_sum = 0.0
    for l in legs:
        b = drag_breakdown(float(l.ask), getattr(l, "bid", None),
                           float(getattr(l, "tick_size", 0.0) or 0.0),
                           slippage_bps=slippage_bps, fee_bps=fee_bps)
        exec_sum += float(b["exec_price"])
        drag_sum += (float(b["tick_rounding"]) + float(b["slippage"])
                     + float(b["fee"]) + float(b["half_spread"]))
    after_cost_edge = round(payout - exec_sum, 6)
    rec["after_cost_edge"] = after_cost_edge
    rec["est_costs"] = round(drag_sum, 6)
    if after_cost_edge <= 0.0:
        rec["gate_result"] = GATE_BLOCKED
        rec["reject_reason"] = R_NEG_EDGE
        return rec
    rec["positive"] = True

    # 4) a paper trade only OPENS on a complete hedge (mutually exclusive + exhaustive).
    full_hedge = bool(getattr(group, "mutually_exclusive", False)
                      and getattr(group, "exhaustive", False))
    if not full_hedge:
        rec["gate_result"] = GATE_POSITIVE_NOT_TRADABLE
        rec["reject_reason"] = R_INCOMPLETE_FAMILY
        return rec
    rec["gate_result"] = GATE_TRADABLE
    rec["tradable"] = True
    return rec


def summarize(records: list) -> dict:
    """Aggregate per-candidate records into the relaxed-stream report metrics. Block
    reasons are counted ONLY for real-book candidates (never the un-hydrated noise)."""
    pipeline = len(records)
    real_book = [r for r in records if r.get("is_real_book")]
    positive = [r for r in real_book if r.get("positive")]
    tradable = [r for r in real_book if r.get("tradable")]
    blocked_by_reason: dict = {}
    source_counts: dict = {}
    for r in real_book:
        source_counts[r["group_type"]] = source_counts.get(r["group_type"], 0) + 1
        if not r.get("tradable") and r.get("reject_reason"):
            blocked_by_reason[r["reject_reason"]] = \
                blocked_by_reason.get(r["reject_reason"], 0) + 1

    def _edge(r):
        return r.get("after_cost_edge") if r.get("after_cost_edge") is not None else -1e9
    best_candidate = max(positive, key=_edge, default=None)
    rejected = [r for r in real_book if not r.get("tradable")]
    best_reject = max(rejected, key=_edge, default=None)

    def _ex(r):
        if not r:
            return {}
        return {"group_id": r["group_id"], "group_type": r["group_type"],
                "after_cost_edge": r.get("after_cost_edge"),
                "reject_reason": r.get("reject_reason"),
                "depth_for_1usd": r.get("depth_for_1usd"), "n_legs": r["n_legs"]}

    return {
        "pipeline_scanned": pipeline,
        "real_book_candidates_seen": len(real_book),
        "positive_real_book_candidates_seen": len(positive),
        "tradable_candidates": len(tradable),
        "blocked_by_reason": blocked_by_reason,
        "source_counts": source_counts,
        "best_real_book_candidate": _ex(best_candidate),
        "best_reject_example": _ex(best_reject),
        "best_after_cost_edge": (best_candidate.get("after_cost_edge")
                                 if best_candidate else
                                 (best_reject.get("after_cost_edge") if best_reject else None)),
    }

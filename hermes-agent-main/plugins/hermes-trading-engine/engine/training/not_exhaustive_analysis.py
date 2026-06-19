"""Decompose ``not_exhaustive`` Bregman near-misses into ACTIONABLE subtypes + per-candidate
conversion attribution (PAPER / RESEARCH ONLY, pure/read-only).

``not_exhaustive`` is the dominant Bregman blocker, but it lumps together fundamentally
different failures — most apparent alpha dies here. This splits it so we know how many
positive-projected near-misses are FIXABLE by better family discovery vs genuinely
untradeable, and ranks the high-lower-bound, one-fix-away families to target for completion.
Never trades; never loosens certification — it only explains WHY each family failed.
"""

from __future__ import annotations

# Subtypes, most-fixable first.
SUB_MISSING_SIBLING = "missing_sibling_discoverable"   # declared > observed; fetch siblings
SUB_NO_DECLARED = "no_declared_outcome_count"          # completeness undeterminable (need metadata)
SUB_TRULY_INCOMPLETE = "truly_incomplete_or_other"     # declared == observed yet unproven / other


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _is_not_exhaustive(nm: dict) -> bool:
    comp = nm.get("completeness", {}) or {}
    return (str(nm.get("reject_reason", "")) == "not_exhaustive"
            or (comp and not comp.get("completeness_proven", True)))


def _subtype(nm: dict) -> str:
    comp = nm.get("completeness", {}) or {}
    declared = comp.get("declared_expected_count")
    observed = comp.get("observed_count")
    if declared is None:
        return SUB_NO_DECLARED
    try:
        if int(declared) > int(observed or 0):
            return SUB_MISSING_SIBLING
    except (TypeError, ValueError):
        return SUB_NO_DECLARED
    return SUB_TRULY_INCOMPLETE


def analyze_not_exhaustive(near_misses: list, *, top_n: int = 20) -> dict:
    """Decompose not_exhaustive near-misses + rank fixable, positive-lower-bound candidates.

    A candidate is FIXABLE (high-value to target for family completion) when its only
    remaining blocker is exhaustiveness (``one_fix_away``), it has a positive after-cost
    lower bound, and its missing siblings are discoverable (a declared outcome count exists,
    i.e. subtype ``missing_sibling_discoverable``). Returns subtype counts + the ranked
    target list. Read-only."""
    nx = [nm for nm in (near_misses or []) if isinstance(nm, dict) and _is_not_exhaustive(nm)]
    sub_counts: dict = {SUB_MISSING_SIBLING: 0, SUB_NO_DECLARED: 0, SUB_TRULY_INCOMPLETE: 0}
    positive_lb = 0
    fixable: list = []
    for nm in nx:
        sub = _subtype(nm)
        sub_counts[sub] = sub_counts.get(sub, 0) + 1
        alb = _f(nm.get("after_cost_lower_bound"))
        comp = nm.get("completeness", {}) or {}
        blockers = nm.get("remaining_blockers", nm.get("blockers", [])) or []
        only_exhaustive = bool(nm.get("one_fix_away")) and (
            len(blockers) <= 1)
        if alb is not None and alb > 0:
            positive_lb += 1
        declared = comp.get("declared_expected_count")
        observed = comp.get("observed_count")
        missing = None
        try:
            if declared is not None:
                missing = max(0, int(declared) - int(observed or 0))
        except (TypeError, ValueError):
            missing = None
        is_fixable = (only_exhaustive and (alb is not None and alb > 0)
                      and sub == SUB_MISSING_SIBLING)
        if is_fixable:
            fixable.append({
                "group_key": nm.get("group_key", ""),
                "market_ids": list(nm.get("market_ids", []) or [])[:12],
                "after_cost_lower_bound": round(alb, 6),
                "observed_count": observed, "declared_expected_count": declared,
                "missing_outcome_count": missing,
                "near_miss_score": _f(nm.get("near_miss_score")) or 0.0,
                "expected_outcome_family": comp.get("expected_outcome_family"),
            })
    fixable.sort(key=lambda c: c["after_cost_lower_bound"], reverse=True)
    return {
        "schema": "not_exhaustive_analysis/1.0", "paper_only": True,
        "not_exhaustive_total": len(nx),
        "positive_lower_bound_count": positive_lb,
        "subtype_counts": sub_counts,
        "fixable_positive_lb_count": len(fixable),
        "top_fixable_candidates": fixable[:top_n],
        "best_fixable_lower_bound": (fixable[0]["after_cost_lower_bound"] if fixable else 0.0),
        # the headline: how many dominant-blocker families are realistically convertible by
        # better family discovery (vs structurally untradeable) — never by loosening a gate.
        "conversion_note": ("fixable = one-fix-away (only exhaustiveness) + positive after-cost"
                            " lower bound + discoverable missing siblings (declared count known)"),
    }

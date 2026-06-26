"""Grok advisory dependency screener (Bible DeepSeek pattern).

Grok proposes candidate constraints from market titles; deterministic LCMM code validates before
any paper trade. Grok never authorizes execution. PAPER ONLY.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from engine.pulse.dependency_arb import DependencyViolation, validate_violation


_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}|\[[\s\S]*\]")


def parse_grok_dependency_response(raw: str) -> list[dict]:
    """Extract structured dependency proposals from Grok JSON (fail-open → [])."""
    if not raw or not str(raw).strip():
        return []
    text = str(raw).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("proposals") or data.get("dependencies") or [data]
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict)]
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        if isinstance(data, dict):
            data = data.get("proposals") or data.get("dependencies") or [data]
        return [p for p in (data or []) if isinstance(p, dict)]
    except json.JSONDecodeError:
        return []


def proposal_to_violation(proposal: dict, *, windows_by_id: dict) -> Optional[DependencyViolation]:
    """Convert one Grok proposal into a DependencyViolation if windows exist."""
    ctype = str(proposal.get("constraint_type") or proposal.get("type") or "")
    if ctype not in ("nested_implication",):
        return None
    pid = str(proposal.get("parent_window_key") or proposal.get("parent_id") or "")
    cids = proposal.get("child_window_keys") or proposal.get("child_ids") or []
    if not pid or not cids:
        return None
    parent = windows_by_id.get(pid)
    child = windows_by_id.get(str(cids[0]))
    if parent is None or child is None:
        return None
    p_mid = getattr(getattr(parent, "up_book", None), "mid", None)
    c_mid = getattr(getattr(child, "up_book", None), "mid", None)
    if p_mid is None or c_mid is None:
        return None
    mag = float(c_mid) - float(p_mid)
    return DependencyViolation(
        constraint_type="nested_implication",
        parent_window_key=pid,
        child_window_keys=[str(cids[0])],
        description=str(proposal.get("description") or "grok_proposed_nested_implication"),
        parent_up_mid=round(float(p_mid), 6),
        child_up_mids=[round(float(c_mid), 6)],
        implied_bound=round(float(c_mid), 6),
        violation_magnitude=round(mag, 6),
        actionable=False,
        reason="grok_proposal_unvalidated",
    )


def validate_grok_proposals(
    proposals: list[dict],
    *,
    windows_by_id: dict,
) -> dict:
    """Validate Grok proposals deterministically; return accepted/rejected lists."""
    accepted, rejected = [], []
    for p in proposals or []:
        v = proposal_to_violation(p, windows_by_id=windows_by_id)
        if v is None:
            rejected.append({"proposal": p, "reason": "unmapped_or_unsupported"})
            continue
        ok, reason = validate_violation(v)
        if ok:
            accepted.append(v.to_dict())
        else:
            rejected.append({"proposal": p, "reason": reason, "violation": v.to_dict()})
    return {
        "dependency_proposals": len(proposals or []),
        "deterministic_validated_dependencies": len(accepted),
        "rejected_dependencies": rejected,
        "accepted_dependencies": accepted,
    }


GROK_DEPENDENCY_PROMPT = """You are a Polymarket dependency screener (ADVISORY ONLY).
Given BTC/ETH up/down window titles and ids, propose ONLY machine-checkable linear constraints.
Output JSON: {"proposals": [{"constraint_type": "nested_implication", "parent_window_key": "...",
"child_window_keys": ["..."], "description": "..."}]}
Rules: nested_implication only when a shorter window is logically nested inside a longer window.
Do NOT propose trades. Do NOT invent window ids not in the input list."""
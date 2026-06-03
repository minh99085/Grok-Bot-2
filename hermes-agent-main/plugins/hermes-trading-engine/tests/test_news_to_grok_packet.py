"""Bounded, sanitized news packet handed to the Grok prompt.

Quant scope — *Compliance / Operational Excellence*: the packet that reaches the
model is capped (max items + snippet length), allow-listed (no execution/sizing
fields), contains no full articles / HTML / scripts, carries source_url + title
for audit, and the prompt explicitly marks news as UNTRUSTED and Grok as not a
trader. No secrets ever enter the prompt.
"""

from __future__ import annotations

import json

from engine.research.news_ranker import build_packet
from engine.research.news_schemas import NewsEvidenceItem, _GROK_VIEW_FIELDS
from engine.research.prompts import SYSTEM_PROMPT, build_messages, build_user_prompt

_NOW = 1_700_000_000_000

_CTX = {
    "venue": "polymarket", "market_id": "m1", "outcome": "YES",
    "question": "Will team A win?", "resolution_source": "league results",
    "asset_keywords": ["team", "a"],
}


def _packet(n=12, snippet=None):
    snippet = snippet or ("team A won the match decisively per league results. " * 30)
    items = [NewsEvidenceItem(
        market_id="m1", query="team a", title=f"Team A result {i}",
        snippet=snippet, source_name="Wire", source_url=f"https://w/{i}",
        source_type="wire", published_ts=_NOW - 3600_000,
        direction="supports_yes") for i in range(n)]
    return build_packet(items, market_ctx=_CTX, now_ms=_NOW, max_items=8,
                        max_snippet_chars=500, min_relevance=0.0)


def test_packet_capped_to_max_items():
    pkt = _packet(20)
    assert len(pkt.items) <= 8
    assert len(pkt.grok_items()) <= 8


def test_snippet_truncated_to_max_chars():
    pkt = _packet(3)
    for gi in pkt.grok_items():
        assert len(gi["snippet"]) <= 501   # 500 + ellipsis char


def test_grok_view_is_allow_listed_only():
    pkt = _packet(2)
    for gi in pkt.grok_items():
        assert set(gi.keys()) == set(_GROK_VIEW_FIELDS)
        # never any execution/sizing field
        for forbidden in ("order_size", "size", "submit", "approve", "notional",
                          "leverage", "stake", "execute"):
            assert forbidden not in gi


def _extract_ctx_json(user: str) -> dict:
    start = user.index("{")
    end = user.rindex("}") + 1
    return json.loads(user[start:end])


def test_build_messages_includes_news_and_untrusted_marker():
    pkt = _packet(3)
    messages = build_messages(_CTX, None, pkt)
    assert messages[0]["role"] == "system"
    assert "UNTRUSTED" in messages[0]["content"]
    assert "NOT a trader" in messages[0]["content"]
    user = messages[1]["content"]
    payload = _extract_ctx_json(user)
    assert "news_evidence" in payload
    assert len(payload["news_evidence"]) == len(pkt.items)
    # audit fields preserved
    assert all("source_url" in e and "title" in e for e in payload["news_evidence"])


def test_no_news_packet_is_backward_compatible():
    user = build_user_prompt(_CTX, None, None)
    payload = _extract_ctx_json(user)
    assert payload["news_evidence"] == []


def test_packet_carries_no_html_or_script():
    pkt = _packet(2, snippet="<script>x()</script> <b>team A</b> won the match.")
    for gi in pkt.grok_items():
        assert "<script" not in gi["snippet"].lower()
        assert "<b>" not in gi["snippet"].lower()

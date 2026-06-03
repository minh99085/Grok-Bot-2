"""News evidence scoring, ranking, and deduplication.

Quant scope — *Data Preprocessing & Feature Engineering*: source credibility,
recency, relevance to question + resolution source, contradiction across
sources, freshness vs market close, directness, and dedup by URL / title /
snippet / normalized-claim hash. Scores only ever weight advisory evidence.
"""

from __future__ import annotations

from engine.research.news_ranker import (
    contradiction_score_for, credibility_score, dedupe, directness_score,
    freshness_vs_close, build_packet, rank_items, recency_score,
    relevance_score, settlement_relevance_score)
from engine.research.news_schemas import NewsEvidenceItem, normalized_claim

_NOW = 1_700_000_000_000
_DAY = 86_400_000

_CTX = {
    "market_id": "m1",
    "question": "Will the Lakers win the NBA championship in 2026?",
    "resolution_source": "NBA official results",
    "close_ts_ms": _NOW + 7 * _DAY,
    "asset_keywords": ["lakers", "nba"],
}


def _item(**kw):
    base = dict(market_id="m1", query="lakers nba", title="Lakers win title",
                snippet="The Lakers won the 2026 NBA championship per NBA results.",
                source_name="AP", source_url="https://ap.com/1",
                source_type="wire", published_ts=_NOW - _DAY)
    base.update(kw)
    return NewsEvidenceItem(**base)


def test_credibility_prior_orders_sources():
    assert credibility_score("official") > credibility_score("news")
    assert credibility_score("news") > credibility_score("social")
    assert credibility_score("unknown") < credibility_score("wire")


def test_recency_decays_and_missing_is_zero():
    fresh = recency_score(_NOW - 3600_000, _NOW)
    old = recency_score(_NOW - 30 * _DAY, _NOW)
    assert fresh > old
    assert recency_score(None, _NOW) == 0.0     # missing ts cannot count fresh


def test_freshness_after_close_is_discounted():
    before = freshness_vs_close(_NOW - _DAY, _NOW + _DAY, _NOW)
    after = freshness_vs_close(_NOW + 2 * _DAY, _NOW + _DAY, _NOW)
    assert before > after


def test_relevance_and_settlement_overlap():
    q_tokens = {"lakers", "nba", "championship", "2026"}
    on = relevance_score({"lakers", "championship"}, q_tokens)
    off = relevance_score({"weather", "rain"}, q_tokens)
    assert on > off
    res = {"nba", "official", "results"}
    s_on = settlement_relevance_score({"nba", "results"}, res)
    s_off = settlement_relevance_score({"random"}, res)
    assert s_on > s_off


def test_directness_rewards_concrete_claims():
    concrete = directness_score("Lakers won", "Officially confirmed 4-2 series win.")
    vague = directness_score("Lakers", "They might possibly win, reportedly.")
    assert concrete > vague


def test_contradiction_between_opposing_directions():
    yes1 = _item(direction="supports_yes", source_url="https://a/1")
    yes1.credibility_score = 0.9
    no1 = _item(direction="supports_no", source_url="https://a/2")
    no1.credibility_score = 0.9
    items = [yes1, no1]
    c = contradiction_score_for(yes1, items)
    assert c > 0.0
    # neutral item has no directional contradiction
    neu = _item(direction="neutral", source_url="https://a/3")
    assert contradiction_score_for(neu, items) == 0.0


def test_dedupe_by_url_title_snippet_and_claim():
    a = _item(source_url="https://dup.com/x")
    b = _item(source_url="https://dup.com/x", title="different title")  # same URL
    c = _item(source_url="https://other.com/y")                        # same claim
    out = dedupe([a, b, c])
    assert len(out) == 1            # b dup-by-url, c dup-by-claim/title/snippet
    assert out[0] is a


def test_normalized_claim_is_stable_and_order_independent():
    n1 = normalized_claim("Lakers win title", "championship NBA 2026")
    n2 = normalized_claim("title win Lakers", "2026 NBA championship")
    assert n1 == n2


def test_rank_orders_by_composite_quality():
    strong = _item(source_type="official", source_url="https://o/1",
                   published_ts=_NOW - 3600_000)
    weak = _item(source_type="social", source_url="https://s/1",
                 title="rumor", snippet="maybe lakers could possibly win someday",
                 published_ts=_NOW - 60 * _DAY)
    ranked = rank_items([weak, strong], market_ctx=_CTX, now_ms=_NOW)
    assert ranked[0] is strong
    assert ranked[0].rank_score >= ranked[1].rank_score


def test_build_packet_caps_items_and_filters_low_quality():
    items = [_item(source_url=f"https://o/{i}", source_type="official",
                   title=f"Lakers win game {i}",
                   snippet=f"NBA results report the Lakers won championship game {i}.",
                   published_ts=_NOW - 3600_000) for i in range(12)]
    # one irrelevant low-cred item that must be filtered
    items.append(_item(source_url="https://x/junk", source_type="social",
                       title="weather", snippet="it rained in seattle today"))
    pkt = build_packet(items, market_ctx=_CTX, now_ms=_NOW, max_items=8,
                       min_relevance=0.05, min_credibility=0.3)
    assert pkt.used <= 8
    assert pkt.fetched == len(items)
    # the social/irrelevant junk should be rejected
    assert all(it.source_type != "social" for it in pkt.items)

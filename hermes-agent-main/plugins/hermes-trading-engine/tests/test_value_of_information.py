"""Value-of-information targeting (#5): spend Grok's bounded compute where the edge is
most uncertain + actionable + liquid. Research-only; never trades/sizes/gates."""

from __future__ import annotations

from engine.research.value_of_information import actionability, voi_score, rank_voi
from engine.research.advisory_targets import select_advisory_target


def test_actionability_peaks_at_threshold():
    assert actionability(0.01, 0.01, band=0.03) == 1.0          # right at threshold
    assert actionability(0.04, 0.01, band=0.03) == 0.0          # one band away
    assert 0.0 < actionability(0.025, 0.01, band=0.03) < 1.0    # halfway


def test_voi_rewards_uncertain_actionable_liquid():
    near = voi_score(disagreement=0.4, edge=0.01, min_edge=0.01, liquidity_usd=2000)
    far = voi_score(disagreement=0.4, edge=0.20, min_edge=0.01, liquidity_usd=2000)
    certain = voi_score(disagreement=0.0, edge=0.01, min_edge=0.01, liquidity_usd=2000)
    thin = voi_score(disagreement=0.4, edge=0.01, min_edge=0.01, liquidity_usd=0)
    assert near > far                  # near the threshold beats far
    assert near > certain              # uncertain beats certain
    assert near > thin                 # liquid beats illiquid


def test_rank_voi_orders_and_drops_zero():
    items = [{"market_id": "a", "voi": 0.0}, {"market_id": "b", "voi": 0.3},
             {"market_id": "c", "voi": 0.1}]
    ranked = rank_voi(items, top_n=10)
    assert [r["market_id"] for r in ranked] == ["b", "c"]       # 'a' dropped, sorted


def test_advisory_prefers_high_voi_over_news_and_liquidity():
    voi = [{"market_id": "m_voi", "voi": 0.4, "ensemble_disagreement": 0.5,
            "question": "uncertain market"}]
    news = {"items": [{"market_id": "m_news", "relevance_score": 0.9}]}
    watch = [{"market_id": "m_liq", "depth_usd": 100000}]
    sel = select_advisory_target(voi_targets=voi, news_packet=news, watch_markets=watch)
    assert sel["target_kind"] == "value_of_information"
    assert sel["market_ctx"]["market_id"] == "m_voi"


def test_advisory_voi_below_threshold_falls_through_to_news():
    voi = [{"market_id": "m_voi", "voi": 0.01}]                 # weak
    news = {"items": [{"market_id": "m_news", "relevance_score": 0.9}]}
    sel = select_advisory_target(voi_targets=voi, news_packet=news, min_voi=0.05)
    assert sel["target_kind"] == "news_linked_market"


def test_near_miss_still_outranks_voi():
    near = [{"group_key": "nm1", "near_miss_score": 0.9, "market_ids": ["m1"],
             "completeness": {"completeness_proven": True}}]
    voi = [{"market_id": "m_voi", "voi": 0.9}]
    sel = select_advisory_target(near_misses=near, voi_targets=voi)
    assert sel["target_kind"] == "bregman_near_miss"           # Bregman discovery first

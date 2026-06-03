"""News keeps Grok strictly advisory — it can adjust the research estimate but
never size/approve/submit/bypass.

Quant scope — *Signal Generation* + *Risk Management*: news only haircuts
confidence, bumps ambiguity, applies a tiny bounded probability nudge, or
triggers a no-trade veto. It can never approve/size a trade, bypass the
EdgeEngine/RiskEngine, or override Bregman certification.
"""

from __future__ import annotations

from engine.research.news_ranker import build_packet, news_adjustment
from engine.research.news_schemas import _GROK_VIEW_FIELDS, NewsEvidenceItem
from engine.research.probability import ProbabilityEstimator
from engine.research.schemas import GrokProbabilityOutput

_NOW = 1_700_000_000_000

_CTX = {"market_id": "m1", "question": "Will team A win?",
        "resolution_source": "league", "asset_keywords": ["team", "a"],
        "outcome": "YES"}

_FORBIDDEN = ("order_size", "size", "notional", "stake", "leverage", "submit",
              "approve", "execute", "cancel", "place_order", "position_size",
              "arm", "go_live", "enable_live")


def _output(p=0.7, conf=0.7, amb=0.1):
    return GrokProbabilityOutput(
        market_id="m1", outcome="YES", fair_probability=p, confidence=conf,
        ambiguity_score=amb, source_coverage_score=0.6,
        no_trade_recommendation=False, no_trade_reason=None,
        evidence=[{"claim": "team A leads", "source_type": "news",
                   "direction": "supports_yes", "weight": 0.6,
                   "credibility": 0.8, "relevance": 0.8},
                  {"claim": "team A favored", "source_type": "news",
                   "direction": "supports_yes", "weight": 0.5,
                   "credibility": 0.7, "relevance": 0.7}],
        key_assumptions=[], resolution_notes="", do_not_trade_if=[],
        expected_update_triggers=[])


def _item(direction, **kw):
    base = dict(market_id="m1", query="team a", title="Team A news",
                snippet="team A won the match per league results",
                source_name="Wire", source_url="https://w/1", source_type="wire",
                published_ts=_NOW - 3600_000, direction=direction)
    base.update(kw)
    return NewsEvidenceItem(**base)


def _packet(items):
    return build_packet(items, market_ctx=_CTX, now_ms=_NOW, min_relevance=0.0)


def test_news_view_has_no_execution_fields():
    for f in _GROK_VIEW_FIELDS:
        assert f not in _FORBIDDEN


def test_news_adjustment_never_increases_confidence():
    pkt = _packet([_item("supports_yes"), _item("supports_no",
                                                source_url="https://w/2")])
    adj = news_adjustment(pkt)
    assert adj["confidence_factor"] <= 1.0    # only ever a haircut


def test_news_nudge_is_bounded():
    pkt = _packet([_item("supports_yes", source_url=f"https://w/{i}")
                   for i in range(5)])
    adj = news_adjustment(pkt, max_prob_delta=0.05)
    assert abs(adj["prob_delta"]) <= 0.05 + 1e-9


def test_news_does_not_change_p_when_absent():
    est = ProbabilityEstimator()
    base = est.estimate(_output(), p_market=0.5, ts_ms=_NOW)
    with_none = est.estimate(_output(), p_market=0.5, ts_ms=_NOW, news_packet=None)
    assert base.p_ensemble == with_none.p_ensemble


def test_news_adjusts_research_bundle_only():
    est = ProbabilityEstimator()
    pkt = _packet([_item("supports_yes", source_url=f"https://w/{i}")
                   for i in range(4)])
    base = est.estimate(_output(), p_market=0.5, ts_ms=_NOW)
    with_news = est.estimate(_output(), p_market=0.5, ts_ms=_NOW, news_packet=pkt)
    diag = with_news.diagnostics.get("news")
    assert diag is not None
    assert "prob_without_news" in diag and "prob_with_news" in diag
    # bounded effect; news never makes the ensemble jump arbitrarily
    assert abs(with_news.p_ensemble - base.p_ensemble) <= 0.05 + 1e-9
    # no execution field ever appears on the bundle diagnostics
    blob = str(with_news.diagnostics).lower()
    for bad in ("order_size", "submit_order", "place_order"):
        assert bad not in blob


def test_contradictory_news_can_veto_but_not_approve():
    # strongly contradictory, high-credibility opposing claims -> veto
    items = [
        _item("supports_yes", source_url="https://a/1", source_type="official",
              title="Team A wins"),
        _item("supports_no", source_url="https://a/2", source_type="official",
              title="Team A loses",
              snippet="team A lost the match per league results"),
    ]
    pkt = _packet(items)
    est = ProbabilityEstimator()
    bundle = est.estimate(_output(), p_market=0.5, ts_ms=_NOW, news_packet=pkt)
    diag = bundle.diagnostics.get("news") or {}
    if diag.get("news_veto_applied"):
        assert bundle.no_trade_reason is not None   # veto => do not trade
    # news can never produce a positive trade authorization field
    assert not hasattr(bundle, "order_size")

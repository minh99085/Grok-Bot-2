"""Replay safety for the news scanner — no future leakage, no live calls.

Quant scope — *Backtesting & Simulation*: in replay, the scanner never calls a
live provider, only keeps evidence timestamped at/before the replay timestamp,
and fails closed on missing or future-dated evidence. Deterministic.
"""

from __future__ import annotations

from engine.research.news_providers import FixtureProvider, LiveReadOnlyProvider
from engine.research.news_scanner import NewsEvidenceScanner
from engine.research.news_schemas import NewsEvidenceItem

_NOW = 1_700_000_000_000
_REPLAY_TS = _NOW
_DAY = 86_400_000

_CTX = {"market_id": "m1", "question": "Will it resolve YES?",
        "asset_keywords": ["foo"]}


def _item(pub, **kw):
    tag = kw.get("source_url", str(pub)).rsplit("/", 1)[-1]
    base = dict(market_id="m1", query="foo", title=f"foo news {tag}",
                snippet=f"foo happened per source {tag}", source_name="Wire",
                source_url="https://w/" + str(pub), source_type="wire",
                published_ts=pub, direction="supports_yes")
    base.update(kw)
    return NewsEvidenceItem(**base)


def test_past_evidence_kept_future_dropped():
    items = [
        _item(_REPLAY_TS - _DAY, source_url="https://w/past"),    # before -> keep
        _item(_REPLAY_TS, source_url="https://w/exact"),          # at -> keep
        _item(_REPLAY_TS + _DAY, source_url="https://w/future"),  # after -> drop
    ]
    scanner = NewsEvidenceScanner(FixtureProvider(items), now_ms=lambda: _NOW)
    res = scanner.scan(_CTX, now_ms=_NOW, replay_ts_ms=_REPLAY_TS)
    urls = {it.source_url for it in res.packet.items}
    assert "https://w/past" in urls
    assert "https://w/exact" in urls
    assert "https://w/future" not in urls
    assert res.rejected >= 1


def test_missing_timestamp_dropped_in_replay():
    items = [_item(None, source_url="https://w/nots"),
             _item(_REPLAY_TS - _DAY, source_url="https://w/ok")]
    # ensure published_ts None and fetched_ts None survive into the filter
    for it in items:
        if it.source_url.endswith("nots"):
            it.fetched_ts = None
    scanner = NewsEvidenceScanner(FixtureProvider(items), now_ms=lambda: _NOW)
    res = scanner.scan(_CTX, now_ms=_NOW, replay_ts_ms=_REPLAY_TS)
    urls = {it.source_url for it in res.packet.items}
    assert "https://w/nots" not in urls   # missing ts -> fail closed (dropped)
    assert "https://w/ok" in urls


def test_live_provider_forbidden_in_replay():
    live = LiveReadOnlyProvider(fetch=lambda q, ctx: [], enabled=True)
    scanner = NewsEvidenceScanner(live, now_ms=lambda: _NOW)
    res = scanner.scan(_CTX, now_ms=_NOW, replay_ts_ms=_REPLAY_TS)
    assert res.provider_ok is False
    assert res.provider_error == "live_provider_forbidden_in_replay"
    assert res.packet.is_empty()


def test_live_provider_not_called_in_replay():
    called = {"n": 0}

    def _fetch(q, ctx):
        called["n"] += 1
        return []

    live = LiveReadOnlyProvider(fetch=_fetch, enabled=True)
    scanner = NewsEvidenceScanner(live, now_ms=lambda: _NOW)
    scanner.scan(_CTX, now_ms=_NOW, replay_ts_ms=_REPLAY_TS)
    assert called["n"] == 0               # never reached the live provider


def test_replay_does_not_use_cache_path():
    # A fresh cache entry must not bypass the replay timestamp filter.
    cache = {"m1": (_NOW, [_item(_REPLAY_TS + _DAY, source_url="https://w/future")])}
    scanner = NewsEvidenceScanner(FixtureProvider([_item(_REPLAY_TS - _DAY,
                                                         source_url="https://w/past")]),
                                  cache=cache, now_ms=lambda: _NOW)
    res = scanner.scan(_CTX, now_ms=_NOW, replay_ts_ms=_REPLAY_TS)
    urls = {it.source_url for it in res.packet.items}
    assert "https://w/future" not in urls

"""Controlled market-news scanner — acquisition, queries, caching, budget.

Quant scope — *Data Acquisition & Ingestion*: deterministic query building from
market metadata, provider abstraction (offline_cache default / fixture), rate +
budget limits, timestamped caching, and the guarantee that no secret / wallet /
position / order state is ever sent to a provider. Read-only; never trades.
"""

from __future__ import annotations

from engine.research.news_providers import (
    FixtureProvider, OfflineCacheProvider, get_provider, safe_market_context)
from engine.research.news_scanner import NewsEvidenceScanner
from engine.research.news_schemas import NewsEvidenceItem

_NOW = 1_700_000_000_000

_CTX = {
    "market_id": "0xabc",
    "question": "Will BTC close above $100k on Dec 31?",
    "slug": "btc-100k-dec-31",
    "category": "crypto",
    "description": "Resolves YES if BTC/USD spot >= 100000 at 23:59 ET.",
    "resolution_source": "Coinbase BTC-USD spot",
    "close_ts_ms": _NOW + 86_400_000,
    "outcome": "YES",
    "asset_keywords": ["bitcoin", "btc"],
    # secret-ish fields that must NEVER be forwarded to a provider
    "wallet_address": "0xdeadbeef",
    "positions": [{"size": 1000}],
    "api_key": "xai-shouldnotleak",
}


def _item(**kw):
    base = dict(market_id="0xabc", query="q", title="BTC nears 100k",
                snippet="Bitcoin rallied toward 100000 on Coinbase.",
                source_name="Reuters", source_url="https://r.com/a",
                source_type="wire", published_ts=_NOW - 3600_000)
    base.update(kw)
    return NewsEvidenceItem(**base)


def test_build_queries_deterministic_and_capped():
    scanner = NewsEvidenceScanner(FixtureProvider([]), max_queries=3)
    q1 = scanner.build_queries(_CTX)
    q2 = scanner.build_queries(_CTX)
    assert q1 == q2                      # deterministic
    assert 1 <= len(q1) <= 3             # capped
    assert any("btc" in q.lower() or "bitcoin" in q.lower() for q in q1)


def test_offline_cache_is_default_provider():
    scanner = NewsEvidenceScanner()
    assert isinstance(scanner.provider, OfflineCacheProvider)
    assert scanner.provider_mode == "offline_cache"


def test_scan_fixture_returns_scored_packet():
    prov = FixtureProvider([_item(), _item(source_url="https://r.com/b",
                                           title="BTC dips", direction="supports_no")])
    scanner = NewsEvidenceScanner(prov, now_ms=lambda: _NOW)
    res = scanner.scan(_CTX, now_ms=_NOW)
    assert res.provider_ok is True
    assert res.fetched >= 1
    assert res.used >= 1
    assert not res.packet.is_empty()
    for it in res.packet.items:
        assert it.fetched_ts is not None
        assert 0.0 <= it.rank_score <= 1.0


def test_safe_market_context_strips_secrets_and_account_state():
    safe = safe_market_context(_CTX)
    for forbidden in ("wallet_address", "positions", "api_key"):
        assert forbidden not in safe
    assert safe["market_id"] == "0xabc"
    assert "question" in safe


def test_provider_never_receives_secrets(monkeypatch):
    seen = {}

    class _Spy(FixtureProvider):
        def search(self, query, market_context):
            seen.update(market_context)
            return super().search(query, market_context)

    scanner = NewsEvidenceScanner(_Spy([_item()]), now_ms=lambda: _NOW)
    scanner.scan(_CTX, now_ms=_NOW)
    assert "wallet_address" not in seen
    assert "positions" not in seen
    assert "api_key" not in seen


def test_budget_limits_provider_calls():
    calls = {"n": 0}

    class _Counting(FixtureProvider):
        def search(self, query, market_context):
            calls["n"] += 1
            return super().search(query, market_context)

    scanner = NewsEvidenceScanner(_Counting([_item()]), max_queries=3,
                                  budget_max_calls=1, now_ms=lambda: _NOW)
    scanner.scan(_CTX, now_ms=_NOW)
    assert calls["n"] == 1               # budget hard-capped at 1 call


def test_results_are_cached_with_timestamp():
    cache: dict = {}
    calls = {"n": 0}

    class _Counting(FixtureProvider):
        def search(self, query, market_context):
            calls["n"] += 1
            return super().search(query, market_context)

    scanner = NewsEvidenceScanner(_Counting([_item()]), cache=cache,
                                  cache_ttl_seconds=3600, now_ms=lambda: _NOW)
    scanner.scan(_CTX, now_ms=_NOW)
    first = calls["n"]
    scanner.scan(_CTX, now_ms=_NOW)      # served from cache; no new calls
    assert calls["n"] == first
    assert "0xabc" in cache
    stored_ts, _items = cache["0xabc"]
    assert stored_ts == _NOW


def test_provider_failure_is_fail_closed():
    scanner = NewsEvidenceScanner(FixtureProvider([_item()], fail=True),
                                  now_ms=lambda: _NOW)
    res = scanner.scan(_CTX, now_ms=_NOW)
    assert res.provider_ok is False
    assert res.packet.is_empty()         # nothing leaks through on failure


def test_get_provider_factory_modes():
    assert get_provider("offline_cache").mode == "offline_cache"
    assert get_provider("fixture").mode == "fixture"
    assert get_provider("live_read_only").mode == "live_read_only"
    assert get_provider("bogus").mode == "offline_cache"   # fail-safe default

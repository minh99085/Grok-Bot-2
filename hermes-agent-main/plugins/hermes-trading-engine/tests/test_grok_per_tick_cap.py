"""Hot-path guard: the research signal model bounds LIVE Grok calls per tick so a single
tick can never stall on serial live research (which stalled the loop -> stale training file
-> unhealthy). Uncached markets beyond the cap fall back to cache/stub FAST and are
researched on later ticks (coverage still grows)."""

from __future__ import annotations

import time

import pytest

from engine.campaigns.signal_models import ResearchSignalModel
from engine.markets import universe_manager as um


class _Res:
    p_ensemble = 0.6
    confidence = 0.7
    estimate_id = "x"
    conviction = None
    uncertainty = None
    asof_ts = None
    news_half_life_s = None
    key_evidence = None


class _Client:
    def __init__(self):
        self.calls = 0

    def research(self, ctx):
        self.calls += 1
        return _Res()


def _model(cap, monkeypatch):
    monkeypatch.setenv("GROK_MAX_LIVE_CALLS_PER_TICK", str(cap))
    m = ResearchSignalModel()
    m.grok_online = True
    m._client = _Client()
    return m


def _recs(n):
    now = time.time()
    return [um.MarketRecord.from_raw(
        {"id": f"m{i}", "question": "q", "bestBid": "0.50", "bestAsk": "0.52"}, now=now)
        for i in range(n)]


def test_live_calls_capped_per_tick(monkeypatch):
    m = _model(3, monkeypatch)
    m.begin_tick()
    srcs = [m.evaluate(r).source for r in _recs(20)]
    assert m._client.calls == 3                      # only 3 live calls this tick
    assert srcs.count("grok_online") == 3
    assert len(srcs) - srcs.count("grok_online") == 17   # rest fell back fast


def test_begin_tick_resets_budget(monkeypatch):
    m = _model(2, monkeypatch)
    m.begin_tick()
    for r in _recs(5):
        m.evaluate(r)
    assert m._client.calls == 2
    m.begin_tick()                                    # new tick -> budget refreshed
    for r in _recs(5):                                # different uncached markets... but
        m.evaluate(um.MarketRecord.from_raw(
            {"id": f"n{r.market_id}", "question": "q", "bestBid": "0.5", "bestAsk": "0.52"},
            now=time.time()))
    assert m._client.calls == 4                        # +2 more on the new tick


def test_cap_zero_disables_limit(monkeypatch):
    m = _model(0, monkeypatch)
    m.begin_tick()
    for r in _recs(8):
        m.evaluate(r)
    assert m._client.calls == 8                        # 0 -> uncapped (legacy behaviour)

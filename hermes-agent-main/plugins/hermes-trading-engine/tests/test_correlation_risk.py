"""Pass-7: cluster/correlation risk is an active hard gate + capital allocator.

Duplicate market/condition/event/cluster exposure is blocked or size-capped;
unknown clusters become shadow-only; directional/exploration cannot collide with
open Bregman bundles; Bregman blocks duplicate/overlapping bundles. Preserves
Pass 2-6. PAPER ONLY.
"""

from __future__ import annotations

from types import SimpleNamespace

from engine.markets import universe_manager as um
from engine.training import PolymarketPaperTrainer, TrainingConfig
from engine.training.correlation_risk import (
    ALLOW, ALLOW_WITH_SIZE_CAP, REJECT, SHADOW_ONLY,
    CorrelationRiskGate, OpenExposureIndex, correlation_keys, normalize_question,
)

from tests._pmtrain_helpers import clean_live_env, market

_NOW = 1_000_000.0


def _rec(mid="m0", *, question="Will event 0 resolve YES?", event=None, condition=None,
         category="crypto"):
    raw = market(0, now=_NOW, group=event, category=category)
    raw["id"] = mid
    raw["question"] = question
    if condition:
        raw["conditionId"] = condition
    rec = um.MarketRecord.from_raw(raw, now=_NOW)
    rec.market_id = mid
    return rec


def _pos(mid, *, cluster="", event="", group="corr:crypto:x", condition="",
         strategy="directional", entry=0.40, qty=10.0):
    return SimpleNamespace(market_id=mid, cluster_id=cluster, group_key=event,
                           correlation_group=group, condition_id=condition,
                           strategy=strategy, entry_price=entry, qty=qty)


# --- normalization + keys ---------------------------------------------------

def test_normalize_question_groups_near_duplicates():
    a = normalize_question("Will BTC hit $120k by June 30?")
    b = normalize_question("Bitcoin to reach 120,000 before Jun 30?")
    assert "btc" in a and "btc" in b and "120000" in a and "120000" in b


def test_correlation_keys_present():
    keys = correlation_keys(_rec("m1", event="elect"))
    for f in ("market_key", "event_key", "condition_key", "semantic_cluster_id",
              "cluster_id", "correlation_group", "normalized_question"):
        assert f in keys
    assert "elect" in keys["event_key"] and not keys["event_key"].startswith("market:")


def test_unknown_cluster_flagged_when_no_question_and_standalone():
    keys = correlation_keys(_rec("m2", question="", event=None))
    assert keys["unknown_cluster"] is True


# --- gate decisions ---------------------------------------------------------

def _gate(**over):
    cfg = TrainingConfig(mode="paper_train", **over)
    return CorrelationRiskGate(cfg)


def test_same_market_duplicate_rejected():
    idx = OpenExposureIndex.from_positions([_pos("m0", cluster="sem:x", event="market:m0")])
    keys = correlation_keys(_rec("m0"))
    d = _gate().evaluate(keys, strategy="directional", size_usd=5.0, index=idx)
    assert d.decision == REJECT and d.collision_type == "same_market"


def test_same_event_duplicate_rejected():
    ek = correlation_keys(_rec("mA", event="elect"))["event_key"]
    idx = OpenExposureIndex.from_positions([_pos("mA", cluster=ek, event=ek)])
    keys = correlation_keys(_rec("mB", event="elect"))   # different market, same event
    d = _gate().evaluate(keys, strategy="directional", size_usd=5.0, index=idx)
    assert d.decision == REJECT and d.collision_type == "same_event"


def test_same_cluster_duplicate_rejected():
    # two standalone near-duplicate questions share a semantic cluster
    keys_open = correlation_keys(_rec("m1", question="Will BTC hit $120k by June 30?"))
    idx = OpenExposureIndex.from_positions(
        [_pos("m1", cluster=keys_open["cluster_id"], event="market:m1")])
    keys_new = correlation_keys(_rec("m2", question="Bitcoin to reach 120,000 before Jun 30?"))
    assert keys_new["cluster_id"] == keys_open["cluster_id"]
    d = _gate().evaluate(keys_new, strategy="directional", size_usd=5.0, index=idx)
    assert d.decision == REJECT and d.collision_type in ("same_cluster", "same_market")


def test_unknown_cluster_becomes_shadow_only():
    keys = correlation_keys(_rec("m9", question="", event=None))
    d = _gate(unknown_cluster_policy="shadow").evaluate(
        keys, strategy="directional", size_usd=5.0, index=OpenExposureIndex())
    assert d.decision == SHADOW_ONLY and d.collision_type == "unknown_cluster_conservative_block"


def test_unknown_cluster_reject_policy():
    keys = correlation_keys(_rec("m9", question="", event=None))
    d = _gate(unknown_cluster_policy="reject").evaluate(
        keys, strategy="directional", size_usd=5.0, index=OpenExposureIndex())
    assert d.decision == REJECT


def test_size_capped_by_cluster_exposure():
    # cluster already holds $23 of a $25 cap -> a $5 candidate is capped to $2
    idx = OpenExposureIndex.from_positions(
        [_pos("mX", cluster="event:elect", event="ev:other", group="corr:z",
              entry=1.0, qty=23.0)])
    # put the open exposure on the SAME cluster as the candidate
    keys = correlation_keys(_rec("mNew", event="elect"))
    idx.by_cluster[keys["cluster_id"]] = idx.by_cluster.pop("event:elect")
    d = _gate(max_cluster_exposure_usd=25.0, max_event_exposure_usd=1000.0,
              max_correlation_group_exposure_usd=1000.0, max_open_per_event=99,
              max_open_per_cluster=99).evaluate(
        keys, strategy="directional", size_usd=5.0, index=idx)
    assert d.decision == ALLOW_WITH_SIZE_CAP and round(d.size_cap, 4) == 2.0


def test_clean_independent_candidate_allowed():
    keys = correlation_keys(_rec("fresh", event="lonely"))
    d = _gate().evaluate(keys, strategy="directional", size_usd=5.0, index=OpenExposureIndex())
    assert d.decision == ALLOW


# --- Bregman collision ------------------------------------------------------

def test_directional_blocked_on_bregman_market():
    idx = OpenExposureIndex.from_positions([_pos("bm0", event="event:e", strategy="bregman")])
    keys = correlation_keys(_rec("bm0", event="e"))
    d = _gate().evaluate(keys, strategy="directional", size_usd=5.0, index=idx)
    assert d.decision == REJECT and d.collision_type == "bregman_market_collision"


def test_directional_blocked_on_bregman_event():
    ek = correlation_keys(_rec("bm0", event="e"))["event_key"]
    idx = OpenExposureIndex.from_positions([_pos("bm0", event=ek, strategy="bregman")])
    keys = correlation_keys(_rec("other", event="e"))   # same event, different market
    d = _gate().evaluate(keys, strategy="directional", size_usd=5.0, index=idx)
    assert d.decision == REJECT and d.collision_type == "bregman_event_collision"


# --- trainer integration ----------------------------------------------------

def _trainer(tmp_path, monkeypatch, **cfg):
    clean_live_env(monkeypatch, tmp_path)
    cfg.setdefault("max_open_trades", 8)
    return PolymarketPaperTrainer(TrainingConfig(mode="paper_train", **cfg), data_dir=tmp_path)


def _bregman_event(asks, group="elect"):
    recs = []
    for i, a in enumerate(asks):
        raw = market(i, bid=round(a - 0.02, 4), ask=a, liq=20_000, depth=2000,
                     category="crypto", group=group, now=_NOW)
        raw["negRiskComplete"] = True
        recs.append(um.MarketRecord.from_raw(raw, now=_NOW))
    return recs


def test_duplicate_bregman_bundle_blocked(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    assert t._run_bregman(_bregman_event([0.28, 0.30, 0.30], group="elect"), _NOW) == 1
    t._begin_correlation_phase()   # index now holds the open bundle's markets/events
    # same event + same markets -> overlapping/duplicate bundle blocked
    opened2 = t._run_bregman(_bregman_event([0.28, 0.30, 0.30], group="elect"), _NOW)
    assert opened2 == 0
    assert (t.correlation_metrics["bregman_bundles_blocked_as_overlapping"]
            + t.correlation_metrics["bregman_bundles_blocked_as_duplicates"]) >= 1


def test_correlation_report_emitted(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    rep = t.correlation_risk_report()
    for key in ("correlation_gate_enabled", "candidates_with_cluster_id",
                "candidates_missing_cluster_id", "open_clusters_count", "open_events_count",
                "blocked_same_market", "blocked_same_event", "blocked_same_cluster",
                "blocked_bregman_market_collision", "size_capped_by_cluster_exposure",
                "shadowed_unknown_cluster", "directional_trades_blocked_by_correlation",
                "bregman_bundles_blocked_as_overlapping", "max_cluster_exposure_usd",
                "top_open_clusters", "real_trade_without_cluster_metadata"):
        assert key in rep
    assert rep["correlation_gate_enabled"] is True
    assert rep["real_trade_without_cluster_metadata"] == 0

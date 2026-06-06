"""Pass-2: raw-catalog ABCAS/Bregman -> certified PAPER execution.

Quant scope: verifies the Bregman/combinatorial scanner now sees the FULL
eligible catalog (not the directional shortlist), de-dupes groups, certifies
through the existing ``BregmanArbitrageEngine``, and executes certified
complete-set bundles in PAPER BEFORE directional trading — with explicit
rejection reasons for every unsafe group. PAPER ONLY: no live orders.
"""

from __future__ import annotations

from types import SimpleNamespace

from engine.markets import universe_manager as um
from engine.training import PolymarketPaperTrainer, TrainingConfig
from engine.training.market_scanner import MarketScanner

from tests._pmtrain_helpers import clean_live_env, market

_NOW = 1_000_000.0


def _leg(i, ask, *, group="elect", complete=True, depth=2000, stale=False,
         missing_ask=False):
    raw = market(i, bid=round(ask - 0.02, 4), ask=ask, liq=20_000, depth=depth,
                 category="crypto", group=group, now=_NOW)
    if complete:
        raw["negRiskComplete"] = True
    if stale:
        raw["bookUpdatedTs"] = _NOW - 10_000.0      # age >> 30s freshness window
    if missing_ask:
        raw.pop("bestAsk", None)
        raw["bestAsk"] = None
    return um.MarketRecord.from_raw(raw, now=_NOW)


def _event(asks, **kw):
    return [_leg(i, a, **kw) for i, a in enumerate(asks)]


def _trainer(tmp_path, monkeypatch, **cfg):
    clean_live_env(monkeypatch, tmp_path)
    return PolymarketPaperTrainer(
        TrainingConfig(mode="paper_train", max_open_trades=8, **cfg),
        data_dir=tmp_path)


# --- raw-catalog visibility -------------------------------------------------

def test_scan_exposes_full_eligible_catalog_beyond_shortlist(tmp_path, monkeypatch):
    """ScanResult.eligible holds ALL eligible markets, not just the shortlist."""
    clean_live_env(monkeypatch, tmp_path)
    cfg = TrainingConfig(mode="paper_train", shortlist_limit=3)
    sc = MarketScanner(cfg, learner=None)
    raw = [market(i, group=None, now=_NOW) for i in range(12)]
    res = sc.scan(raw, now=_NOW)
    assert len(res.records) <= 3            # directional shortlist is truncated
    assert len(res.eligible) > len(res.records)
    assert len(res.eligible) == res.kept    # full eligible set after safety filters


# --- certify + open the complete set ---------------------------------------

def test_complete_set_below_one_opens_certified_bundle(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    opened = t._run_bregman(_event([0.28, 0.30, 0.30]), _NOW)   # asks sum 0.88
    assert opened == 1
    assert t.bregman_sets_opened == 1
    m = t.bregman_exec_metrics
    assert m["raw_groups_discovered"] >= 1
    assert m["certified_opportunities"] >= 1
    assert m["opened_bregman_bundles"] == 1
    assert m["bregman_capital_committed"] > 0.0


def test_overround_set_rejects_no_positive_edge(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    opened = t._run_bregman(_event([0.40, 0.40, 0.40]), _NOW)   # asks sum 1.20
    assert opened == 0
    assert "no_positive_edge" in t.bregman_reject_reasons


def test_incomplete_set_rejects(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    opened = t._run_bregman(_event([0.28, 0.30, 0.30], complete=False), _NOW)
    assert opened == 0
    assert sum(t.bregman_reject_reasons.values()) >= 1


def test_one_stale_leg_rejects_group(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    recs = _event([0.28, 0.30, 0.30])
    stale = _leg(2, 0.30, stale=True)            # replace 3rd leg with stale book
    recs[2] = stale
    opened = t._run_bregman(recs, _NOW)
    assert opened == 0
    assert "stale_book" in t.bregman_reject_reasons


def test_one_missing_ask_rejects_group(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    recs = _event([0.28, 0.30, 0.30])
    recs[1] = _leg(1, 0.30, missing_ask=True)
    opened = t._run_bregman(recs, _NOW)
    assert opened == 0
    assert "no_executable_price" in t.bregman_reject_reasons


def test_one_thin_depth_leg_rejects_group(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    recs = _event([0.28, 0.30, 0.30])
    recs[0] = _leg(0, 0.28, depth=5)             # below min_depth_at_price (50)
    opened = t._run_bregman(recs, _NOW)
    assert opened == 0
    assert "depth_too_thin" in t.bregman_reject_reasons


# --- dedup ------------------------------------------------------------------

def test_duplicate_groups_deduped_once(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    g = SimpleNamespace(group_type="mutually_exclusive", legs=[
        SimpleNamespace(market_id="a", outcome="YES"),
        SimpleNamespace(market_id="b", outcome="YES")])
    dup = SimpleNamespace(group_type="mutually_exclusive", legs=[
        SimpleNamespace(market_id="b", outcome="YES"),     # same set, different order
        SimpleNamespace(market_id="a", outcome="YES")])
    other = SimpleNamespace(group_type="mutually_exclusive", legs=[
        SimpleNamespace(market_id="c", outcome="YES")])
    unique, dropped = t._dedup_bregman_groups([g, dup, other])
    assert dropped == 1
    assert len(unique) == 2


# --- synthetic binary safety ------------------------------------------------

def test_synthetic_binary_not_executable(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    # Defense-in-depth: even if a binary_yes_no group certified as an
    # opportunity, it must never open (its NO leg is a derived/synthetic price).
    binary = SimpleNamespace(group_type="binary_yes_no", profit_lower_bound=1.0,
                             required_capital=10.0, certificate=None)
    opened = t._open_bregman_sets([binary], [], _NOW, cap=None)
    assert opened == 0
    assert t.bregman_reject_reasons.get("synthetic_binary_not_executable", 0) >= 1


# --- budget caps ------------------------------------------------------------

def test_max_bundles_per_tick_caps_execution(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch, bregman_max_bundles_per_tick=1)
    recs = _event([0.28, 0.30, 0.30], group="evtA") + \
        _event([0.27, 0.29, 0.31], group="evtB")
    # re-id the second event so market ids do not collide
    for k, r in enumerate(recs[3:], start=3):
        r.market_id = f"m{k}"
    opened = t._run_bregman(recs, _NOW)
    assert opened == 1
    assert "max_bundles_per_tick" in t.bregman_reject_reasons


# --- Bregman before directional --------------------------------------------

def test_bregman_runs_before_directional_in_tick(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    raw = [market(i, group="elect", now=_NOW) for i in range(3)]
    for r in raw:
        r["negRiskComplete"] = True
        r["bestAsk"] = 0.30 if r["id"] != "m0" else 0.28
        r["outcomePrices"] = ["0.29", "0.71"]
    t.run_tick(raw, now=_NOW)
    summ = t.bregman_summary()["execution"]
    assert summ["evaluated_before_directional"] is True
    assert summ["sees_full_raw_catalog"] is True
    # a certified complete set consumed the bundle BEFORE directional trades
    assert t.bregman_sets_opened >= 1
    assert any(p.strategy == "bregman" for p in t.positions)

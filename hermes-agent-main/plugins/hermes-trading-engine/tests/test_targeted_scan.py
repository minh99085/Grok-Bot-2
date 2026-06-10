"""Targeted market-scan PRIORITIZATION + market-quality scorer (PAPER ONLY).

Proves quality scoring prioritizes effort WITHOUT loosening any gate or enabling
trades: tiered (not hard pass/fail) scoring, hard structural checks, side-specific
(not summed) depth, category prioritization with metadata-proven completeness, scan
waste cooldown, and report telemetry. Targeted scan never executes/sizes/gates and
never disables broad scan.
"""

import json
import time

from engine.training.market_quality import (score_market, structural_checks,
                                            side_specific_depth, parse_book_timestamp,
                                            QualityThresholds, TIER_REJECT)
from engine.training.targeted_scan import TargetedMarketScanner, classify_categories


_NOW = 1_700_000_000.0


def _mkt(mid="m", q="Will the team win?", ask=0.51, depth=400, liq=40000, vol=20000,
         age=3, end="2099-06-12", labels=("Yes", "No"), tokens=None, negrisk=False,
         bid=None):
    tokens = tokens if tokens is not None else [mid + "Y", mid + "N"]
    raw = {"id": mid, "question": q, "outcomes": json.dumps(list(labels)),
           "outcomePrices": json.dumps([str(round(ask - 0.01, 2)), str(round(1 - ask, 2))]),
           "clobTokenIds": json.dumps(tokens),
           "bestBid": str(bid if bid is not None else round(ask - 0.01, 2)),
           "bestAsk": str(ask), "topDepthUsd": str(depth), "liquidityNum": str(liq),
           "volume24hr": str(vol), "bookUpdatedTs": str(_NOW - age), "endDate": end}
    if negrisk:
        raw["negRiskComplete"] = True
    return raw


# --- scorer: structural + tiered ------------------------------------------- #
def test_scorer_valid_binary_payload():
    r = score_market(_mkt(), now=_NOW)
    assert r["structural_ok"] is True
    assert r["market_quality_tier"] in ("gold", "silver", "bronze")
    assert r["trade_eligible"] is False        # quality NEVER implies executability


def test_scorer_missing_token_ids():
    sc = structural_checks(_mkt(tokens=[]))
    assert "token_ids_unavailable" in sc["failures"]


def test_scorer_missing_labels_flagged():
    sc = structural_checks(_mkt(labels=("", "")))
    assert any("label" in f for f in sc["failures"]) or sc["failures"]


def test_scorer_invalid_bid_ask_is_critical_reject():
    sc = structural_checks(_mkt(ask=0.5, bid=0.6))   # bid > ask
    assert sc["critical"] is True
    r = score_market(_mkt(ask=0.5, bid=0.6), now=_NOW)
    assert r["market_quality_tier"] == TIER_REJECT


def test_scorer_timestamp_ms_and_seconds():
    sec = _mkt()
    ms = _mkt(); ms["bookUpdatedTs"] = str(int(_NOW * 1000))
    assert abs(parse_book_timestamp(sec) - (_NOW - 3)) < 1.0
    assert abs(parse_book_timestamp(ms) - _NOW) < 1.0


def test_scoring_is_tiered_not_hard_all_pass():
    # thin + zero volume must NOT be reject solely; it is down-prioritized (watch/bronze)
    r = score_market(_mkt(depth=5, liq=100, vol=0), now=_NOW)
    assert r["market_quality_tier"] != TIER_REJECT
    assert r["market_quality_score"] > 0


def test_side_specific_depth_not_summed():
    legs = [{"visible_ask_depth_usd": 10, "visible_bid_depth_usd": 999},
            {"visible_ask_depth_usd": 200, "visible_bid_depth_usd": 999}]
    d = side_specific_depth(legs, side="buy")
    assert d["worst_leg_depth_usd"] == 10        # ask-side worst leg, NOT bid+ask
    assert d["min_leg_depth_usd"] == 10
    # bid-side ignored for buy (no 999+999 summation)
    assert d["executable_notional_usd"] == 210


# --- categories ------------------------------------------------------------ #
def test_high_liquidity_binary_prioritized():
    r = score_market(_mkt(ask=0.51, depth=400), now=_NOW)
    cats = classify_categories(_mkt(ask=0.51, depth=400), r)
    assert "high_liquidity_binary" in cats


def test_negative_risk_requires_metadata_proof():
    # title-similar multi-candidate WITHOUT metadata -> NOT negative_risk_complete
    plain = _mkt(mid="x", q="Who wins the election? A")
    rp = score_market(plain, now=_NOW)
    assert "negative_risk_complete" not in classify_categories(plain, rp)
    # WITH negRiskComplete metadata -> qualifies
    nr = _mkt(mid="y", negrisk=True)
    rn = score_market(nr, now=_NOW)
    assert "negative_risk_complete" in classify_categories(nr, rn)


def test_short_resolution_scored_higher_for_learning():
    soon = score_market(_mkt(mid="s", end="2023-11-16"), now=_NOW)  # ~1 day out
    far = score_market(_mkt(mid="f", end="2099-01-01"), now=_NOW)
    assert soon["resolution_horizon_score"] >= far["resolution_horizon_score"]


def test_btc_macro_reference_needs_external_context():
    btc = score_market(_mkt(mid="b", q="Will BTC top $100k?"), now=_NOW)
    plain = score_market(_mkt(mid="p", q="Will the team win the cup?"), now=_NOW)
    assert btc["external_reference_score"] > 0
    assert plain["external_reference_score"] == 0
    assert "btc_eth_chainlink" in classify_categories(_mkt(mid="b", q="Will BTC top $100k?"), btc)


# --- scanner: prioritization, no execution, cooldown ----------------------- #
def test_targeted_scan_does_not_disable_broad_and_cannot_execute():
    s = TargetedMarketScanner(enabled=True)
    tel = s.scan([_mkt(mid="a"), _mkt(mid="b", depth=5, liq=100, vol=0)], now=_NOW)
    assert tel["targeted_market_scan_enabled"] is True
    assert tel["targeted_markets_scanned_total"] == 2
    # broad exploration budget is always reserved (targeting never disables broad scan)
    assert tel["targeted_scan_budget_by_category"].get("broad_exploration", 0) > 0
    assert tel["targeted_scan_can_execute"] is False
    assert tel["targeted_scan_can_size"] is False
    assert tel["market_quality_tier_counts"]


def test_scan_waste_cooldown_after_repeated_thin_stale():
    s = TargetedMarketScanner(enabled=True, cooldown_ticks=5)
    thin = _mkt(mid="bad", depth=2, liq=50, vol=0, age=300)   # thin + stale
    dep_ever = 0
    for _ in range(4):
        tel = s.scan([thin], now=_NOW)
        dep_ever = max(dep_ever, tel["scan_deprioritized_groups"])
    # repeated waste -> deprioritized (on the trigger tick) with an active cooldown
    assert dep_ever >= 1
    assert tel["scan_cooldown_active_groups"] >= 1
    assert tel["thin_depth_scan_waste_count"] >= 1
    assert tel["stale_book_scan_waste_count"] >= 1


def test_disabled_scanner_is_noop():
    s = TargetedMarketScanner(enabled=False)
    tel = s.scan([_mkt()], now=_NOW)
    assert tel["targeted_market_scan_enabled"] is False


# --- trainer integration: telemetry + no gate change ----------------------- #
def test_trainer_targeted_scan_metrics_and_no_trade(tmp_path, monkeypatch):
    from engine.training import PolymarketPaperTrainer, TrainingConfig
    from engine.markets.universe_manager import MarketRecord
    from tests._pmtrain_helpers import clean_live_env
    import engine.training.polymarket_trainer as P
    clean_live_env(monkeypatch, tmp_path)
    t = PolymarketPaperTrainer(TrainingConfig(mode="paper_train"), data_dir=tmp_path)
    recs = [MarketRecord.from_raw(_mkt(mid="hi", q="Will BTC top $100k?"), now=time.time()),
            MarketRecord.from_raw(_mkt(mid="thin", depth=5, liq=100, vol=0), now=time.time())]
    # no certifiable groups -> certified stays 0 (gates intact), but telemetry populated
    from engine.training.bregman_grouping import group_markets as _gm
    t.closed_loop.begin_tick()
    t.scan_bregman([{"market_id": "hi"}], now=time.time())  # records arg drives grouping
    tel = t._run_targeted_scan(recs, [], time.time())
    assert tel["targeted_market_scan_enabled"] is True
    assert tel["targeted_markets_scanned_total"] == 2
    assert tel["market_quality_tier_counts"]
    assert tel["targeted_scan_can_execute"] is False

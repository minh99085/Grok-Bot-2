"""CEX-lead latency edge (PAPER ONLY): grade the CEX-implied digital probability vs the MARKET
price per divergence bucket, and only allow a proven bucket to PROPOSE a driven entry.

Proves: signal/divergence/bucketing; grading (accuracy, Brier-vs-market, hypothetical PnL,
Wilson); promotion requires beating the market AND Wilson-confident win-rate above break-even;
shadow never drives; gated drives only on proven buckets; state round-trips.
"""

from __future__ import annotations

from engine.pulse.cex_lead import CexLeadEdge, div_bucket, _wilson_lower


def test_div_bucket_and_signal():
    edge = CexLeadEdge(min_divergence=0.04)
    assert div_bucket(None, min_divergence=0.04) == "na"
    assert div_bucket(0.01, min_divergence=0.04) == "no_signal"
    assert div_bucket(0.05, min_divergence=0.04) == "0.04-0.08"
    assert div_bucket(0.10, min_divergence=0.04) == "0.08-0.15"
    assert div_bucket(0.40, min_divergence=0.04) == ">=0.30"
    # CEX says UP more likely than the market prices -> buy UP
    sig = edge.signal(cex_p_up=0.70, poly_yes=0.55, fair=0.60)
    assert sig["has_signal"] and sig["side"] == "up" and sig["bucket"] == "0.08-0.15"
    assert sig["divergence"] == 0.15 and sig["vs_fair"] == 0.10
    # tiny divergence -> no actionable signal
    assert edge.signal(cex_p_up=0.51, poly_yes=0.50)["has_signal"] is False
    # missing inputs are safe
    assert edge.signal(cex_p_up=None, poly_yes=0.5)["has_signal"] is False


def test_proven_only_when_beats_market_and_wilson_confident():
    edge = CexLeadEdge(min_samples=40, min_divergence=0.04, confidence_z=1.64)
    # bucket where CEX is RIGHT and CONFIDENT and well-calibrated (beats the market price).
    # signal: cex_p_up=0.75 vs poly_yes=0.55 -> side up, price paid 0.55, breakeven 0.55.
    for i in range(80):
        up = i < 60                                  # 75% of windows resolve UP -> signal correct
        edge.record(bucket="0.15-0.30", side="up", cex_p_up=0.75, poly_yes=0.55,
                    fair=0.60, outcome_up=up)
    a = edge._assess("0.15-0.30")
    assert a["n"] == 80 and a["accuracy"] == 0.75
    assert a["brier_cex"] < a["brier_market"]        # CEX beats the market
    assert a["win_rate_lower_ci"] > a["breakeven"]   # Wilson-confident above break-even
    assert a["avg_pnl_per_trade"] > 0 and a["proven"] is True
    assert edge.is_proven("0.15-0.30") is True

    # a coin-flip bucket (signal right only ~half the time) is NOT proven
    edge2 = CexLeadEdge(min_samples=40, min_divergence=0.04)
    for i in range(80):
        up = i % 2 == 0
        edge2.record(bucket="0.04-0.08", side="up", cex_p_up=0.58, poly_yes=0.54,
                     fair=0.55, outcome_up=up)
    a2 = edge2._assess("0.04-0.08")
    assert a2["proven"] is False and edge2.is_proven("0.04-0.08") is False


def test_not_proven_if_right_but_worse_than_market():
    """If the signal is directionally right but its probability is LESS calibrated than the market
    price (higher Brier), it must NOT be promoted — beating the market is the bar."""
    edge = CexLeadEdge(min_samples=30, min_divergence=0.04)
    # cex_p_up wildly overconfident (0.99) while market (0.55) is closer to the true 0.65 rate
    for i in range(60):
        up = i < 39                                  # ~65% up
        edge.record(bucket="0.15-0.30", side="up", cex_p_up=0.99, poly_yes=0.55,
                    fair=0.60, outcome_up=up)
    a = edge._assess("0.15-0.30")
    assert a["accuracy"] == 0.65
    assert a["brier_cex"] > a["brier_market"]        # CEX over-confident -> worse Brier
    assert a["beats_market"] is False and a["proven"] is False


def test_below_min_samples_not_proven():
    edge = CexLeadEdge(min_samples=100, min_divergence=0.04)
    for _ in range(20):
        edge.record(bucket="0.15-0.30", side="up", cex_p_up=0.8, poly_yes=0.5, fair=0.6,
                    outcome_up=True)
    assert edge.is_proven("0.15-0.30") is False      # n < min_samples


def test_shadow_never_drives_gated_drives_only_when_proven():
    # shadow mode: decide() always None even on a proven bucket
    sh = CexLeadEdge(mode="shadow", min_samples=10, min_divergence=0.04)
    for i in range(20):
        sh.record(bucket="0.15-0.30", side="up", cex_p_up=0.8, poly_yes=0.5, fair=0.6,
                  outcome_up=(i < 18))
    assert sh.is_proven("0.15-0.30") is True
    assert sh.decide(cex_p_up=0.8, poly_yes=0.5) is None   # shadow can't drive

    # gated mode: drives on a proven bucket, abstains on an unproven one
    gd = CexLeadEdge(mode="gated", min_samples=10, min_divergence=0.04)
    for i in range(20):
        gd.record(bucket="0.15-0.30", side="up", cex_p_up=0.8, poly_yes=0.5, fair=0.6,
                  outcome_up=(i < 18))
    drive = gd.decide(cex_p_up=0.70, poly_yes=0.50)     # div 0.20 -> proven "0.15-0.30" bucket
    assert drive is not None and drive["side"] == "up" and drive["proven"] is True
    assert drive["outcome_prob"] == 0.70
    # an unproven (small-divergence, untracked) bucket -> no drive
    assert gd.decide(cex_p_up=0.505, poly_yes=0.50) is None


def test_state_roundtrip():
    edge = CexLeadEdge(min_samples=10)
    for i in range(15):
        edge.record(bucket="0.08-0.15", side="down", cex_p_up=0.3, poly_yes=0.45, fair=0.4,
                    outcome_up=(i % 3 == 0))
    st = edge.to_state()
    e2 = CexLeadEdge(min_samples=10)
    e2.load_state(st)
    assert e2._assess("0.08-0.15") == edge._assess("0.08-0.15")
    assert e2.graded == edge.graded and e2.signals_seen == edge.signals_seen


def test_wilson_lower_bounds():
    assert _wilson_lower(0, 0) is None
    lo = _wilson_lower(60, 80, 1.64)
    assert 0.0 < lo < 0.75                            # below the point estimate 0.75


# ============================ engine end-to-end =========================================== #
from engine.pulse.markets import OrderBook, PulseWindow
from engine.pulse.price import PulsePriceFeed
from engine.pulse.fair_value import RollingVol
from engine.pulse.engine import PulseEngine, PulseConfig


class _Mkt:
    def __init__(self, w):
        self._w = w

    def active_windows(self, now=None, **kw):
        return [self._w]

    def hydrate_books(self, w):
        w.up_book = OrderBook(best_bid=0.50, best_ask=0.55, ask_depth_usd=50000, bid_depth_usd=50000,
                              asks=[(0.55, 100000.0)], bids=[(0.50, 100000.0)])
        w.down_book = OrderBook(best_bid=0.44, best_ask=0.49, ask_depth_usd=49000, bid_depth_usd=44000,
                                asks=[(0.49, 100000.0)], bids=[(0.44, 100000.0)])
        return w

    def fetch_resolution(self, market_id):
        return True


def _engine(tmp_path, **over):
    t0 = 9_960_000.0
    win = PulseWindow(event_id="e1", market_id="m1", slug="s", title="BTC Up or Down",
                      open_ts=t0, close_ts=t0 + 300, up_token_id="U", down_token_id="D")
    price = {"p": 64000.0}

    def fetch():
        price["p"] += 4.0
        return price["p"]
    feed = PulsePriceFeed(fetcher=fetch, source_name="rtds_chainlink",
                          vol=RollingVol(window_s=900, min_samples=8), max_open_lag_s=20.0)
    cfg = PulseConfig(tick_seconds=1.0, size_usd=10.0, min_edge=0.02, basis_buffer=0.0,
                      min_seconds_since_open=0.0, sigma_trust_floor=0.0, min_vol_samples=2,
                      settle_grace_s=0.0, exec_max_depth_consume_frac=0.9,
                      exec_min_ev_after_slippage=0.0, data_dir=str(tmp_path), **over)
    eng = PulseEngine(cfg, market_feed=_Mkt(win), price_feed=feed)
    # inject a fresh CEX (Binance) spot far ABOVE the window open so cex_p_up diverges high from the
    # ~0.525 market mid -> a strong UP signal. Stop poll() from overwriting it.
    eng.leads.poll = lambda now=None: None
    eng.leads._latest = {"binance_btcusdt": (70000.0, t0)}
    return eng, t0


def _drive(eng, t0):
    for i in range(12):
        eng.tick(now=t0 - 12 + i)
    eng.leads._latest = {"binance_btcusdt": (70000.0, t0)}    # re-assert after warmup ticks
    for k in range(6):
        eng.tick(now=t0 + 2 + k * 5)
    eng.tick(now=t0 + 305)


def test_engine_cex_lead_shadow_grades_but_never_trades(tmp_path):
    eng, t0 = _engine(tmp_path, cex_lead_enabled=True, cex_lead_mode="shadow",
                      cex_lead_min_divergence=0.04, grok_decider_mode="shadow")
    _drive(eng, t0)
    # the signal is measured every window and graded at close, but shadow can NEVER drive a trade
    assert eng.cex_lead.signals_seen >= 1
    assert eng.cex_lead.graded >= 1
    assert eng.cex_lead.drove == 0
    rep = eng.light_report()["cex_lead_edge"]
    assert rep["mode"] == "shadow" and rep["affects_trading"] is False
    assert eng.light_report()["global_reconciled"] is True
    assert eng.status()["live_trading_enabled"] is False and eng.status()["paper_only"] is True


def test_engine_cex_lead_gated_drives_proven_bucket_via_safety_floor(tmp_path):
    eng, t0 = _engine(tmp_path, cex_lead_enabled=True, cex_lead_mode="gated",
                      cex_lead_min_samples=10, cex_lead_min_divergence=0.04,
                      grok_decider_mode="shadow")
    # pre-seed the strong-divergence bucket as Wilson-PROVEN (CEX right + beats market)
    for i in range(40):
        eng.cex_lead.record(bucket=">=0.30", side="up", cex_p_up=0.95, poly_yes=0.52,
                            fair=0.6, outcome_up=(i < 34))
    assert eng.cex_lead.is_proven(">=0.30") is True
    _drive(eng, t0)
    # the proven CEX-lead bucket proposed an entry, and (passing the safety floor) a paper trade ran
    assert eng.cex_lead.drove >= 1
    assert eng.ledger.trades >= 1
    assert eng.light_report()["global_reconciled"] is True
    assert eng.status()["live_trading_enabled"] is False and eng.status()["paper_only"] is True

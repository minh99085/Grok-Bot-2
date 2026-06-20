"""Local BTC technical / fair-value signal (PAPER ONLY) — pure-math unit tests."""

from __future__ import annotations

import math

import threading

from engine.training.btc_signal import (BtcSignalEngine, CryptoPriceSampler,
                                         directional_fair_value, fair_value_above,
                                         parse_btc_market, realized_vol_per_sec, rsi)


def test_parse_strike_above():
    p = parse_btc_market("Will the price of Bitcoin be above $66,000 on June 20?")
    assert p["kind"] == "strike" and p["direction"] == "above" and abs(p["strike"] - 66000) < 1


def test_parse_strike_k_suffix():
    p = parse_btc_market("Will Bitcoin reach $72.5k in June?")
    assert p["kind"] == "strike" and p["strike"] == 72500.0


def test_parse_directional():
    assert parse_btc_market("Bitcoin Up or Down on June 20?")["kind"] == "directional"


def test_parse_non_btc():
    assert parse_btc_market("Will the Fed cut rates?")["kind"] == "none"


def test_fair_value_above_monotonic_and_bounded():
    # higher spot vs strike -> higher P(above); deep ITM ~1, deep OTM ~0
    v = 0.0001  # per-sec vol
    tau = 3600.0
    p_atm = fair_value_above(100_000, 100_000, v, tau)
    p_itm = fair_value_above(110_000, 100_000, v, tau)
    p_otm = fair_value_above(90_000, 100_000, v, tau)
    assert 0.0 <= p_otm < p_atm < p_itm <= 1.0
    assert abs(p_atm - 0.5) < 0.05            # at-the-money ~0.5 (zero drift)


def test_realized_vol_needs_data():
    assert realized_vol_per_sec([(0, 100)]) is None
    samples = [(i, 100_000 * (1 + 0.0001 * math.sin(i))) for i in range(60)]
    assert realized_vol_per_sec(samples) is not None


def test_rsi_bounds():
    rising = list(range(1, 40))
    assert rsi(rising, 14) > 70                # straight up -> overbought
    falling = list(range(40, 1, -1))
    assert rsi(falling, 14) < 30


def _feed_engine(eng, prices, t0=1000.0, dt=1.0):
    for i, p in enumerate(prices):
        eng.observe(p, now=t0 + i * dt)


def test_engine_not_ready_until_min_samples():
    eng = BtcSignalEngine(min_samples=30)
    _feed_engine(eng, [100_000] * 10)
    assert not eng.ready
    assert eng.signal_for_market("Bitcoin Up or Down today?", end_ts=2000.0) is None


def test_engine_strike_signal_fair_value():
    eng = BtcSignalEngine(min_samples=30)
    # a gently moving price series -> a real vol estimate
    _feed_engine(eng, [100_000 * (1 + 0.0002 * math.sin(i / 3.0)) for i in range(120)])
    sig = eng.signal_for_market("Will Bitcoin be above $130,000 on date?",
                                end_ts=1000.0 + 120 + 600.0)   # far OTM, short horizon
    assert sig is not None and sig.kind == "fair_value_strike"
    assert sig.p_up < 0.2                      # far OTM -> low P(above)
    assert 0.0 <= sig.confidence <= 1.0


def test_engine_directional_signal_bounded():
    eng = BtcSignalEngine(min_samples=30, directional_max_dev=0.12)
    _feed_engine(eng, [100_000 + i * 20 for i in range(120)])   # steady uptrend
    sig = eng.signal_for_market("Bitcoin Up or Down today?", end_ts=1000.0 + 120 + 600.0)
    assert sig is not None and sig.kind in ("directional", "directional_drift")
    assert 0.5 <= sig.p_up <= 0.5 + 0.12 + 1e-9     # uptrend -> lean up, bounded
    assert sig.p_up > 0.5
    assert 0.0 <= sig.confidence <= 0.7             # directional confidence stays modest


def test_directional_fair_value_drift_sign_and_bounded():
    # positive drift -> P(up) > 0.5; negative drift -> < 0.5; both within +/- max_dev
    sig = 1e-4
    tau = 300.0
    up = directional_fair_value(5e-6, sig, tau, max_dev=0.15)
    flat = directional_fair_value(0.0, sig, tau, max_dev=0.15)
    down = directional_fair_value(-5e-6, sig, tau, max_dev=0.15)
    assert up is not None and down is not None and flat is not None
    assert down < flat <= 0.5 < up
    assert 0.35 <= down and up <= 0.65               # clamped to 0.5 +/- 0.15
    assert directional_fair_value(1e-6, 0.0, tau) is None   # no vol -> no signal


def test_drift_indicator_tracks_uptrend():
    eng = BtcSignalEngine(min_samples=10, momentum_window_s=60)
    _feed_engine(eng, [100_000 + i * 10 for i in range(60)])   # +10/sec
    ind = eng.indicators()
    assert ind["drift_per_sec"] is not None and ind["drift_per_sec"] > 0
    assert ind["momentum"] is not None and ind["momentum"] > 0


def test_engine_reads_are_thread_safe_under_concurrent_writes():
    # the background sampler appends while the main loop reads indicators(); a single list()
    # snapshot must keep reads from raising "deque mutated during iteration".
    eng = BtcSignalEngine(min_samples=5)
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            eng.observe(100_000 + (i % 50), now=1000.0 + i * 0.001)
            i += 1

    t = threading.Thread(target=writer, daemon=True)
    t.start()
    try:
        for _ in range(2000):
            ind = eng.indicators()             # must never raise
            assert "vol_per_sec" in ind
    finally:
        stop.set()
        t.join(timeout=2.0)


def test_crypto_price_sampler_feeds_per_asset_engines():
    btc = BtcSignalEngine(min_samples=3)
    eth = BtcSignalEngine(min_samples=3)
    prices = {"BTC": iter([100_000, 100_010, 100_020, 100_030]),
              "ETH": iter([3_000, 3_001, 3_002, 3_003])}
    fetchers = {"BTC": lambda: next(prices["BTC"], None),
                "ETH": lambda: next(prices["ETH"], None)}
    s = CryptoPriceSampler({"BTC": btc, "ETH": eth}, interval_s=2.0, fetchers=fetchers)
    for i in range(4):
        s.sample_once(now=1000.0 + i)
    assert btc.observations == 4 and eth.observations == 4
    assert s.samples == {"BTC": 4, "ETH": 4}
    # a fetcher returning None counts as an error, not a sample
    s2 = CryptoPriceSampler({"BTC": BtcSignalEngine()}, fetchers={"BTC": lambda: None})
    s2.sample_once(now=2000.0)
    assert s2.samples["BTC"] == 0 and s2.errors["BTC"] == 1

"""BTC Pulse Chainlink BTC/USD oracle gate (PAPER ONLY)."""

from __future__ import annotations

import types

from engine.training.btc_pulse import BtcPulsePaperTrainer
from engine.training.chainlink_oracle import ChainlinkBtcUsdOracle
from engine.training.config import TrainingConfig

_NOW_MS = 1_700_000_000_000
_NOW_S = _NOW_MS / 1000.0


def _reading(value, updated_at):
    return types.SimpleNamespace(value=value, updated_at=updated_at)


class _Source:
    def __init__(self, reading=None, *, raise_exc=False):
        self._reading = reading
        self._raise = raise_exc

    def read(self, spec, now=None):
        if self._raise:
            raise RuntimeError("rpc down")
        return self._reading

    def history(self, feed_key, now=None, limit=50):
        return [self._reading] if self._reading is not None else []


def _oracle(src):
    return ChainlinkBtcUsdOracle(src, registry={"BTC/USD": object()}, max_age_seconds=180)


def _pulse(oracle, **cfgkw):
    cfg = TrainingConfig(btc_pulse_enabled=True, btc_pulse_require_chainlink=True,
                         btc_pulse_min_ev_threshold=-1.0, **cfgkw)
    return BtcPulsePaperTrainer(cfg, clock=lambda: _NOW_MS, oracle=oracle, rng_seed=3)


def test_fresh_oracle_allows_decision_and_sets_price():
    o = _oracle(_Source(_reading(65000.0, _NOW_S - 10)))
    t = _pulse(o)
    t.tick(now_ms=_NOW_MS)
    assert t.oracle_counters["oracle_fresh"] is True
    assert t.oracle_counters["oracle_fresh_decisions"] >= 1
    assert t._price == 65000.0                       # uses the real oracle price
    assert "chainlink_stale" not in t.rejection_reasons


def test_stale_oracle_blocks_trade():
    o = _oracle(_Source(_reading(65000.0, _NOW_S - 10000)))
    t = _pulse(o)
    out = t.tick(now_ms=_NOW_MS)
    assert out["event"] == "oracle_blocked"
    assert out["reason"] == "chainlink_stale"
    assert t.paper_trades == 0
    assert t.oracle_counters["oracle_stale_skips"] >= 1


def test_provider_error_blocks_trade():
    o = _oracle(_Source(raise_exc=True))
    t = _pulse(o)
    out = t.tick(now_ms=_NOW_MS)
    assert out["event"] == "oracle_blocked"
    assert out["reason"] == "chainlink_provider_error"
    assert t.paper_trades == 0
    assert t.oracle_counters["oracle_error_skips"] >= 1


def test_missing_oracle_blocks_trade_when_required():
    t = _pulse(None)        # require_chainlink True but no oracle
    out = t.tick(now_ms=_NOW_MS)
    assert out["event"] == "oracle_blocked"
    assert out["reason"] == "chainlink_not_initialized"
    assert t.oracle_counters["oracle_missing_skips"] >= 1


def test_status_exposes_oracle_fields():
    o = _oracle(_Source(_reading(65000.0, _NOW_S - 10)))
    t = _pulse(o)
    t.tick(now_ms=_NOW_MS)
    st = t.status()
    assert st["btc_pulse_oracle_required"] is True
    assert st["btc_pulse_oracle_source"] == "chainlink"
    assert st["btc_pulse_oracle_fresh"] is True
    assert st["btc_pulse_oracle_last_price"] == 65000.0


def test_not_required_keeps_simulated_price():
    # When Chainlink is NOT required, the pulse still runs on its own price walk.
    cfg = TrainingConfig(btc_pulse_enabled=True, btc_pulse_require_chainlink=False)
    t = BtcPulsePaperTrainer(cfg, clock=lambda: _NOW_MS, price_fn=lambda: 100000.0)
    t.tick(now_ms=_NOW_MS)
    assert t.oracle_counters["oracle_required"] is False
    assert t._price == 100000.0

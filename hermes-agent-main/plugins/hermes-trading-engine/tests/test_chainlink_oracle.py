"""Chainlink BTC/USD oracle — validated, auditable, read-only (PAPER ONLY)."""

from __future__ import annotations

import types

from engine.training.chainlink_oracle import (BLOCKER_DISABLED, BLOCKER_NOT_INITIALIZED,
                                              BLOCKER_PROVIDER_ERROR, BLOCKER_STALE,
                                              ChainlinkBtcUsdOracle, ChainlinkOracleStatus,
                                              oracle_blocker)

_NOW = 1_700_000_000.0


def _reading(value, updated_at):
    return types.SimpleNamespace(value=value, updated_at=updated_at)


class _Source:
    def __init__(self, reading=None, *, raise_exc=False, history=None):
        self._reading = reading
        self._raise = raise_exc
        self._history = history if history is not None else (
            [reading] if reading is not None else [])

    def read(self, spec, now=None):
        if self._raise:
            raise RuntimeError("rpc down")
        return self._reading

    def history(self, feed_key, now=None, limit=50):
        return list(self._history)[-limit:]


def _oracle(src, **kw):
    kw.setdefault("registry", {"BTC/USD": object()})
    kw.setdefault("max_age_seconds", 180)
    return ChainlinkBtcUsdOracle(src, **kw)


def test_fresh_reading_is_valid():
    o = _oracle(_Source(_reading(65000.0, _NOW - 10)))
    st = o.read(now=_NOW)
    assert st.valid is True
    assert st.stale is False
    assert st.price == 65000.0
    assert st.age_seconds == 10.0
    assert st.consecutive_failures == 0
    assert st.last_success_at == _NOW
    assert oracle_blocker(st) is None


def test_stale_reading_is_invalid():
    o = _oracle(_Source(_reading(65000.0, _NOW - 10000)))
    st = o.read(now=_NOW)
    assert st.valid is False
    assert st.stale is True
    assert st.error == "stale"
    assert oracle_blocker(st) == BLOCKER_STALE


def test_missing_price_is_invalid():
    o = _oracle(_Source(None, history=[]))
    st = o.read(now=_NOW)
    assert st.valid is False
    assert st.error == "missing_price"
    assert st.consecutive_failures == 1


def test_zero_price_is_invalid():
    o = _oracle(_Source(_reading(0.0, _NOW - 10)))
    st = o.read(now=_NOW)
    assert st.valid is False
    assert st.error == "invalid_price"


def test_non_finite_price_is_invalid():
    o = _oracle(_Source(_reading(float("nan"), _NOW - 10)))
    st = o.read(now=_NOW)
    assert st.valid is False
    assert st.price is None
    assert st.error == "invalid_price"


def test_missing_timestamp_is_invalid():
    o = _oracle(_Source(_reading(65000.0, 0)))
    st = o.read(now=_NOW)
    assert st.valid is False
    assert st.error == "missing_timestamp"


def test_provider_error_increments_failures():
    o = _oracle(_Source(raise_exc=True))
    st1 = o.read(now=_NOW)
    st2 = o.read(now=_NOW)
    assert st1.error.startswith("provider_error")
    assert st2.consecutive_failures == 2
    assert oracle_blocker(st1) == BLOCKER_PROVIDER_ERROR


def test_consecutive_failures_reset_on_success():
    src = _Source(raise_exc=True)
    o = _oracle(src)
    o.read(now=_NOW)
    assert o.consecutive_failures == 1
    src._raise = False
    src._reading = _reading(65000.0, _NOW - 5)
    st = o.read(now=_NOW)
    assert st.valid is True
    assert st.consecutive_failures == 0


def test_disabled_oracle_blocks():
    o = ChainlinkBtcUsdOracle(_Source(_reading(65000.0, _NOW)), enabled=False,
                              registry={"BTC/USD": object()})
    st = o.read(now=_NOW)
    assert st.enabled is False
    assert oracle_blocker(st) == BLOCKER_DISABLED


def test_not_initialized_when_no_source():
    o = ChainlinkBtcUsdOracle(None, enabled=True, registry={"BTC/USD": object()})
    st = o.read(now=_NOW)
    assert st.initialized is False
    assert oracle_blocker(st) == BLOCKER_NOT_INITIALIZED


def test_status_dict_has_all_required_fields():
    o = _oracle(_Source(_reading(65000.0, _NOW - 10)))
    d = o.status(refresh=True, now=_NOW)
    for k in ("enabled", "initialized", "symbol", "source", "price", "updated_at",
              "observed_at", "age_seconds", "heartbeat_seconds", "max_age_seconds",
              "stale", "valid", "error", "consecutive_failures", "last_success_at"):
        assert k in d, k
    assert d["symbol"] == "BTC/USD"
    assert d["source"] == "chainlink"

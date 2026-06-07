"""BTC Pulse shadow-gate toggle: loosen trade frequency for training volume.

BTC_PULSE_SHADOW_GATE_ENABLED=0 (+ marginal-EV knobs) lets the paper Pulse OPEN
more paper trades for training, WITHOUT touching the hard safety gates (realistic
fill, RiskEngine, daily-loss kill switch, no live orders). PAPER ONLY.
"""

from __future__ import annotations

from engine.training.btc_pulse import BtcPulsePaperTrainer
from engine.training.config import TrainingConfig

_NOW = 1_700_000_000_000


def _run(cfg, ticks=400, seed=7):
    t = BtcPulsePaperTrainer(cfg, rng_seed=seed)
    assert not t.frozen, t.safety.get("fail_closed_reason")
    for i in range(ticks):
        t.tick(now_ms=_NOW + i * 30_000)
    return t


def _cfg(**kw):
    base = dict(mode="paper_train", btc_pulse_enabled=True, btc_pulse_require_chainlink=False,
                btc_pulse_require_realistic_fill=True)
    base.update(kw)
    return TrainingConfig(**base)


def test_shadow_gate_env_wired_and_default_on():
    import os
    # default ON
    assert TrainingConfig(mode="paper_train").btc_pulse_shadow_gate_enabled is True
    # env override OFF
    os.environ["BTC_PULSE_SHADOW_GATE_ENABLED"] = "0"
    try:
        assert TrainingConfig.from_env().btc_pulse_shadow_gate_enabled is False
    finally:
        os.environ.pop("BTC_PULSE_SHADOW_GATE_ENABLED", None)


def test_loosening_increases_paper_trade_volume():
    default = _run(_cfg())
    loosened = _run(_cfg(btc_pulse_shadow_gate_enabled=False,
                         btc_pulse_require_positive_ev=False,
                         btc_pulse_min_ev_threshold=-0.02,
                         btc_pulse_max_paper_trades_per_hour=600))
    assert default.decisions == loosened.decisions      # same number of rounds
    assert loosened.paper_trades > default.paper_trades  # but more actual paper trades
    assert loosened.paper_trades >= 2 * default.paper_trades


def test_loosening_preserves_hard_safety_gates():
    t = _run(_cfg(btc_pulse_shadow_gate_enabled=False, btc_pulse_require_positive_ev=False,
                  btc_pulse_min_ev_threshold=-0.05))
    s = t.status()
    # still paper-only, isolated, no live path — loosening only affects soft gates
    assert s["btc_pulse_enabled"] is True
    assert s["live_enabled"] is False
    assert s["legacy_autotrade_enabled"] is False
    assert t.safety["passed"] is True
    assert t.require_realistic_fill is True


def test_live_flag_still_freezes_even_when_loosened(monkeypatch):
    # loosening the trade gate must NEVER bypass the fail-closed live-trading gate
    monkeypatch.setenv("BTC_PULSE_LIVE_ENABLED", "1")
    t = BtcPulsePaperTrainer(_cfg(btc_pulse_shadow_gate_enabled=False,
                                  btc_pulse_live_enabled=True), rng_seed=7)
    assert t.frozen is True
    assert "live" in (t.safety.get("fail_closed_reason") or "")

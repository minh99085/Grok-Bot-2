"""Tests for the BTC Pulse after-cost shadow gate, regime classification,
expectancy tables, threshold learning, and drawdown throttle."""

from __future__ import annotations

from engine.strategies.btc_pulse import (
    NO_TRADE_LABELS,
    NT_CALIBRATION_DEGRADING,
    NT_CHOP_REGIME,
    NT_DISAGREEMENT_UNEXPLAINED,
    NT_DRAWDOWN_THROTTLE,
    NT_NEGATIVE_AFTER_COST_EV,
    NT_STALE_MARKET,
    NT_UNKNOWN_REGIME,
    NT_WEAK_FILL_REALISM,
    PulseGateInputs,
    PulseThresholdLearner,
    RegimeExpectancy,
    classify_regime,
    drawdown_throttle,
    evaluate_pulse_gate,
)


def _good() -> PulseGateInputs:
    return PulseGateInputs(
        regime="trending_up", expected_after_cost_value=0.05, min_after_cost_ev=0.0,
        disagreement_bps=20.0, max_disagreement_bps=150.0, market_stale_s=5.0,
        max_stale_s=120.0, fill_realism_ok=True, calibration_degrading=False,
        drawdown=0.0)


# --- the happy path: all six conditions hold -> trade -----------------------
def test_all_conditions_pass_allows_trade():
    d = evaluate_pulse_gate(_good())
    assert d.mode == "trade" and d.allow_trade is True
    assert d.reasons == [] and d.throttle == 1.0


# --- each condition individually demotes to shadow --------------------------
def test_unknown_regime_shadow():
    inp = _good(); inp.regime = "unknown"
    d = evaluate_pulse_gate(inp)
    assert d.mode == "shadow" and NT_UNKNOWN_REGIME in d.reasons


def test_chop_regime_shadow():
    inp = _good(); inp.regime = "chop"
    assert NT_CHOP_REGIME in evaluate_pulse_gate(inp).reasons


def test_negative_after_cost_ev_shadow():
    inp = _good(); inp.expected_after_cost_value = -0.01
    assert NT_NEGATIVE_AFTER_COST_EV in evaluate_pulse_gate(inp).reasons


def test_below_learned_threshold_shadow():
    inp = _good(); inp.expected_after_cost_value = 0.005; inp.min_after_cost_ev = 0.02
    d = evaluate_pulse_gate(inp)
    assert d.allow_trade is False
    assert "below_learned_threshold" in d.reasons


def test_unexplained_disagreement_shadow():
    inp = _good(); inp.disagreement_bps = 500.0
    assert NT_DISAGREEMENT_UNEXPLAINED in evaluate_pulse_gate(inp).reasons


def test_stale_market_shadow():
    inp = _good(); inp.market_stale_s = 999.0
    assert NT_STALE_MARKET in evaluate_pulse_gate(inp).reasons


def test_weak_fill_realism_shadow():
    inp = _good(); inp.fill_realism_ok = False
    assert NT_WEAK_FILL_REALISM in evaluate_pulse_gate(inp).reasons


def test_calibration_degrading_shadow():
    inp = _good(); inp.calibration_degrading = True
    assert NT_CALIBRATION_DEGRADING in evaluate_pulse_gate(inp).reasons


def test_drawdown_throttle_shadow():
    inp = _good(); inp.drawdown = 0.30
    d = evaluate_pulse_gate(inp)
    assert d.throttle == 0.0 and NT_DRAWDOWN_THROTTLE in d.reasons


def test_all_reasons_are_typed_labels():
    inp = _good(); inp.regime = "unknown"; inp.expected_after_cost_value = -1
    for r in evaluate_pulse_gate(inp).reasons:
        assert r in NO_TRADE_LABELS


# --- regime classification --------------------------------------------------
def test_classify_regime_unknown_when_few_samples():
    assert classify_regime([0.01, 0.02]) == "unknown"


def test_classify_regime_trending_up():
    assert classify_regime([0.02] * 12) == "trending_up"


def test_classify_regime_trending_down():
    assert classify_regime([-0.02] * 12) == "trending_down"


def test_classify_regime_chop():
    assert classify_regime([0.01, -0.01] * 8) == "chop"


# --- expectancy table + threshold learning ----------------------------------
def test_regime_expectancy_learns():
    t = RegimeExpectancy(alpha=0.5)
    t.update("trending_up", 1.0)
    t.update("trending_up", -1.0)
    ev = t.expected_after_cost("trending_up")
    assert ev is not None and -1.0 < ev < 1.0
    assert t.expected_after_cost("chop") is None


def test_threshold_learner_raises_after_losses():
    learn = PulseThresholdLearner(base=0.0, loss_step=0.01, max_extra=0.05)
    assert learn.threshold("trending_up") == 0.0
    learn.update("trending_up", -1.0)
    learn.update("trending_up", -1.0)
    assert learn.threshold("trending_up") > 0.0
    for _ in range(50):
        learn.update("trending_up", -1.0)
    assert learn.threshold("trending_up") <= 0.05 + 1e-9


def test_drawdown_throttle_band():
    assert drawdown_throttle(0.0) == 1.0
    assert drawdown_throttle(0.30, soft=0.1, hard=0.2) == 0.0
    assert 0.0 < drawdown_throttle(0.15, soft=0.1, hard=0.2) < 1.0

"""Grok-follow mispricing + edge/TTC + executable-margin gates."""

from __future__ import annotations

from dataclasses import dataclass

from engine.pulse.engine import PulseEngine, PulseConfig


@dataclass
class _FakeEsnap:
    stale_divergence_class: str = "insufficient_data"
    pulse_edge_score_bucket: str = "medium"


def _gate_engine(**cfg_kw) -> PulseEngine:
    defaults = {"mispricing_gate_enabled": True, "edge_ttc_gate_enabled": True}
    defaults.update(cfg_kw)
    cfg = PulseConfig(**defaults)
    eng = object.__new__(PulseEngine)
    eng.cfg = cfg
    eng._mispricing_gate_counts = {}
    return eng


def _cex_sig(**kw):
    base = {"has_signal": True, "side": "down", "divergence": -0.06, "confirmed": True}
    base.update(kw)
    return base


def test_mispricing_gate_disabled_passes():
    eng = _gate_engine(mispricing_gate_enabled=False)
    ok, _ = eng._mispricing_gate_ok(side="up", cex_sig={}, ttc_s=50.0)
    assert ok is True


def test_mispricing_gate_requires_cex_signal():
    eng = _gate_engine()
    ok, reason = eng._mispricing_gate_ok(side="down", cex_sig={"has_signal": False}, ttc_s=200.0)
    assert ok is False and reason == "misprice_no_cex_signal"


def test_mispricing_gate_requires_side_alignment_and_ttc_window():
    eng = _gate_engine()
    ok, reason = eng._mispricing_gate_ok(side="up", cex_sig=_cex_sig(side="down"), ttc_s=200.0)
    assert ok is False and reason == "misprice_side_mismatch"
    ok, reason = eng._mispricing_gate_ok(side="down", cex_sig=_cex_sig(), ttc_s=120.0)
    assert ok is False and reason == "misprice_ttc_out_of_window"
    ok, _ = eng._mispricing_gate_ok(
        side="down", cex_sig=_cex_sig(), ttc_s=210.0,
        esnap=_FakeEsnap("stale_polymarket_down"))
    assert ok is True


def test_mispricing_gate_requires_confirmation():
    eng = _gate_engine()
    ok, reason = eng._mispricing_gate_ok(
        side="down", cex_sig=_cex_sig(confirmed=False), ttc_s=200.0)
    assert ok is False and reason == "misprice_not_confirmed"


def test_mispricing_gate_down_requires_stale_polymarket_down():
    eng = _gate_engine()
    ok, reason = eng._mispricing_gate_ok(
        side="down", cex_sig=_cex_sig(), ttc_s=200.0, esnap=_FakeEsnap("not_stale"))
    assert ok is False and reason == "misprice_stale_down_required"
    ok, _ = eng._mispricing_gate_ok(
        side="down", cex_sig=_cex_sig(), ttc_s=200.0,
        esnap=_FakeEsnap("stale_polymarket_down"))
    assert ok is True


def test_edge_ttc_gate_blocks_mid_window_low_score():
    eng = _gate_engine()
    ok, reason = eng._edge_ttc_gate_ok(esnap=_FakeEsnap(pulse_edge_score_bucket="medium"),
                                       ttc_s=120.0)
    assert ok is False and reason == "edge_ttc_mid_window_low_score"
    ok, _ = eng._edge_ttc_gate_ok(esnap=_FakeEsnap(pulse_edge_score_bucket="high"), ttc_s=120.0)
    assert ok is True
    ok, _ = eng._edge_ttc_gate_ok(esnap=_FakeEsnap(pulse_edge_score_bucket="low"), ttc_s=200.0)
    assert ok is True


def test_executable_mispricing_margin():
    eng = _gate_engine(mispricing_min_executable_margin=0.03, edge_buffer=0.01)
    ok, reason = eng._executable_mispricing_ok(p_win=0.58, ask=0.55)
    assert ok is False and reason == "misprice_executable_margin_low"
    ok, _ = eng._executable_mispricing_ok(p_win=0.62, ask=0.55)
    assert ok is True


def test_mispricing_follow_entry_on_abstain():
    eng = _gate_engine(mispricing_ttc_min_s=90.0, mispricing_ttc_max_s=300.0)
    sig = {"has_signal": True, "side": "up", "divergence": 0.12, "confirmed": True,
           "cex_p_up": 0.62}
    entry = eng._mispricing_follow_entry(sig, 250.0, _FakeEsnap("stale_polymarket_up"))
    assert entry is not None and entry["side"] == "up" and entry["p_win"] == 0.62
    assert eng._mispricing_follow_entry(sig, 50.0, _FakeEsnap()) is None


def test_mispricing_follow_entry_disabled():
    eng = _gate_engine(mispricing_follow_on_abstain=False)
    sig = {"has_signal": True, "side": "up", "divergence": 0.12, "confirmed": True,
           "cex_p_up": 0.62}
    assert eng._mispricing_follow_entry(sig, 200.0) is None
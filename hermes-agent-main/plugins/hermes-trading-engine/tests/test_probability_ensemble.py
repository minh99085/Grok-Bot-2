"""Calibration-weighted probability ensemble (#4) — advisory-only.

p_raw becomes a model+market+research weighted average where each member's weight is
its base prior x MEASURED calibration. The bot leans on whichever source is measurably
most accurate. Produces a probability only — never a gate or a size.
"""

from __future__ import annotations

from engine.training.probability_ensemble import calibration_weighted_stack
from engine.training.member_calibration import MemberCalibration


# --- pure stacker -----------------------------------------------------------

def test_weighted_average_and_disagreement():
    st = calibration_weighted_stack({
        "market": {"p": 0.40, "weight": 1.0},
        "model": {"p": 0.60, "weight": 1.0},
    }, ci_k=1.0)
    assert abs(st["p_ensemble"] - 0.50) < 1e-9
    assert st["disagreement"] > 0.0
    assert st["ci_low"] < st["p_ensemble"] < st["ci_high"]
    assert st["members_used"] == 2


def test_zero_weights_fall_back_to_anchor():
    st = calibration_weighted_stack({"model": {"p": 0.9, "weight": 0.0}}, fallback=0.42)
    assert st["p_ensemble"] == 0.42 and st["members_used"] == 0


def test_higher_weight_member_dominates():
    st = calibration_weighted_stack({
        "market": {"p": 0.40, "weight": 0.2},
        "research": {"p": 0.90, "weight": 1.8},
    })
    assert st["p_ensemble"] > 0.8                     # research (heavy) dominates
    assert st["weights"]["research"] > st["weights"]["market"]


def test_agreement_gives_tight_band():
    st = calibration_weighted_stack({
        "market": {"p": 0.50, "weight": 1.0},
        "model": {"p": 0.50, "weight": 1.0},
        "research": {"p": 0.50, "weight": 1.0},
    })
    assert st["disagreement"] == 0.0 and st["ci_low"] == st["ci_high"] == 0.5


# --- per-member calibration -------------------------------------------------

def test_member_weight_rewards_calibration(tmp_path):
    c = MemberCalibration(path=str(tmp_path / "mc.json"), members=("model", "market"),
                          min_samples=10, weight_min=0.05)
    for _ in range(20):
        c.record("model", predicted_prob=0.95, won=True)     # well-calibrated
        c.record("market", predicted_prob=0.95, won=False)   # badly calibrated
    assert c.weight("model") >= 0.9
    assert c.weight("market") == 0.05                        # floored
    assert c.weight("model") > c.weight("market")


def test_member_weight_default_until_min_samples(tmp_path):
    c = MemberCalibration(path=str(tmp_path / "mc.json"), min_samples=10)
    c.record("model", predicted_prob=0.9, won=True)
    assert c.weight("model") == 1.0                          # < min_samples -> default


def test_member_persistence_round_trip(tmp_path):
    c = MemberCalibration(path=str(tmp_path / "mc.json"), min_samples=5)
    for _ in range(8):
        c.record("model", predicted_prob=0.9, won=True)
    w = c.weight("model")
    c2 = MemberCalibration(path=str(tmp_path / "mc.json"), min_samples=5)
    assert c2.sample_count("model") == 8 and c2.weight("model") == w


# --- integration: stack drives p_raw ---------------------------------------

def test_probability_stack_uses_ensemble(tmp_path, monkeypatch):
    from engine.markets import universe_manager as um
    from engine.training import TrainingConfig
    from engine.training.probability_stack import ProbabilityStack
    from engine.training.member_calibration import MemberCalibration as MC
    from tests._pmtrain_helpers import FakeResearch, market, clean_live_env
    clean_live_env(monkeypatch, tmp_path)
    now = 1_000_000.0
    raw = market(0, bid=0.39, ask=0.41, depth=2000, category="crypto", now=now)
    rec = um.MarketRecord.from_raw(raw, now=now)
    sig = FakeResearch(fair=0.80, conf=0.9, source="grok_cache")
    cfg = TrainingConfig(mode="paper_train")
    mc = MC(path=str(tmp_path / "mc.json"), members=("model", "market"))
    est = ProbabilityStack(cfg, member_calibration=mc).estimate(rec, sig, now=now)
    # ensemble blends market(0.40) + model(~0.40) + research(0.80) -> p_raw between mid
    # and the research view, strictly above the mid.
    assert est.p_market_mid <= est.p_raw <= 0.80
    assert est.p_raw > est.p_market_mid

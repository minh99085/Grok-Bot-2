"""Tests for engine.models.probability_ensemble (pure modeling layer).

Tests-first: online shrinkage, bounded evidence-only news/Grok, feature nudge,
conformal bands, leakage checks, no-trade abstain, and the Bregman
ranking-vs-depth-proof contract.
"""

from __future__ import annotations

from engine.models import probability_ensemble as pe


def _ens():
    return pe.ProbabilityEnsemble(pe.EnsembleConfig())


# --------------------------------------------------------------------------- #
# online shrinkage
# --------------------------------------------------------------------------- #
def test_thin_model_shrinks_to_market():
    est = _ens().combine(pe.EnsembleInputs(market_prob=0.5, model_prob=0.85,
                                           model_sample_size=0))
    assert est.p is not None and abs(est.p - 0.5) < 0.05  # near market when thin


def test_rich_model_dominates():
    est = _ens().combine(pe.EnsembleInputs(market_prob=0.5, model_prob=0.85,
                                           model_sample_size=100000))
    assert est.p is not None and est.p > 0.8  # near model when data-rich


# --------------------------------------------------------------------------- #
# evidence-only news / Grok
# --------------------------------------------------------------------------- #
def test_news_is_bounded_and_never_final_authority():
    cfg = pe.EnsembleConfig()
    est = _ens().combine(pe.EnsembleInputs(
        market_prob=0.20, model_prob=0.20, model_sample_size=100000,
        news_evidence_score=1.0, news_direction=1))
    # Strong "up" news cannot move a 0.20 core beyond the cap -> never near 1.0.
    assert est.p <= 0.20 + cfg.w_feature + cfg.max_news_influence + 1e-9
    assert est.p < 0.35


def test_news_direction_down():
    est = _ens().combine(pe.EnsembleInputs(
        market_prob=0.8, model_prob=0.8, model_sample_size=100000,
        news_evidence_score=1.0, news_direction=-1))
    assert est.p < 0.8 and "news_evidence" in est.reasons


# --------------------------------------------------------------------------- #
# feature nudge (bounded)
# --------------------------------------------------------------------------- #
def test_feature_nudge_bounded():
    cfg = pe.EnsembleConfig()
    of = {"fast": {"microtrend": 1.0}, "anchor": {"confidence_multiplier": 1.0},
          "cross": {"agree": True}}
    est = _ens().combine(pe.EnsembleInputs(market_prob=0.5, model_prob=0.5,
                                           model_sample_size=100000, oracle_features=of))
    assert 0.5 < est.p <= 0.5 + cfg.w_feature + 1e-9


def test_feature_nudge_reduced_on_disagreement():
    of_agree = {"fast": {"microtrend": 1.0}, "anchor": {"confidence_multiplier": 1.0},
                "cross": {"agree": True}}
    of_disagree = {"fast": {"microtrend": 1.0}, "anchor": {"confidence_multiplier": 1.0},
                   "cross": {"agree": False}}
    p_a = _ens().combine(pe.EnsembleInputs(market_prob=0.5, model_prob=0.5,
                         model_sample_size=100000, oracle_features=of_agree)).p
    p_d = _ens().combine(pe.EnsembleInputs(market_prob=0.5, model_prob=0.5,
                         model_sample_size=100000, oracle_features=of_disagree)).p
    assert p_d < p_a  # disagreement halves the nudge


# --------------------------------------------------------------------------- #
# abstain paths
# --------------------------------------------------------------------------- #
def test_no_trade_label_abstains():
    est = _ens().combine(pe.EnsembleInputs(market_prob=0.6, model_prob=0.7,
                                           no_trade_label=True))
    assert est.abstain is True and "no_trade_label" in est.reasons
    assert abs(est.p - 0.6) < 1e-9  # falls back to market


def test_no_signal_abstains():
    est = _ens().combine(pe.EnsembleInputs())
    assert est.abstain is True and est.p is None and "no_signal" in est.reasons


# --------------------------------------------------------------------------- #
# conformal bands
# --------------------------------------------------------------------------- #
def test_conformal_band_brackets_p():
    est = _ens().combine(pe.EnsembleInputs(market_prob=0.5, model_prob=0.6,
                                           model_sample_size=100))
    assert est.lo <= est.p <= est.hi


def test_conformal_band_from_residuals():
    p, lo, hi = pe.conformal_band(0.5, residuals=[0.4, 0.4, 0.4], alpha=0.1)
    assert hi - lo > 0.5  # large residuals -> wide band


def test_conformal_band_tightens_with_more_data():
    _, lo_s, hi_s = pe.conformal_band(0.5, n_eff=10)
    _, lo_l, hi_l = pe.conformal_band(0.5, n_eff=10000)
    assert (hi_l - lo_l) < (hi_s - lo_s)


# --------------------------------------------------------------------------- #
# leakage checks
# --------------------------------------------------------------------------- #
def test_detect_leakage():
    assert pe.detect_leakage(feature_ts=100, label_ts=90) is True   # feature after label
    assert pe.detect_leakage(feature_ts=80, label_ts=90) is False
    assert pe.detect_leakage(None, 90) is False


def test_leakage_scan():
    recs = [{"feature_ts": 1, "label_ts": 2}, {"feature_ts": 5, "label_ts": 4}]
    out = pe.leakage_scan(recs)
    assert out["leak_count"] == 1 and out["leakage_ok"] is False
    assert pe.leakage_scan([{"feature_ts": 1, "label_ts": 2}])["leakage_ok"] is True


# --------------------------------------------------------------------------- #
# Bregman ranking vs depth-proof contract
# --------------------------------------------------------------------------- #
def test_rank_candidates_by_calibrated_edge():
    cands = [
        {"id": "a", "calibrated_prob": 0.6, "market_prob": 0.5},
        {"id": "b", "calibrated_prob": 0.9, "market_prob": 0.5},
        {"id": "c", "calibrated_prob": 0.55, "market_prob": 0.5},
    ]
    ranked = pe.rank_candidates(cands)
    assert [r["id"] for r in ranked] == ["b", "a", "c"]


def test_calibrated_prob_ranks_but_depth_proof_gates_trading():
    top = {"id": "b", "calibrated_prob": 0.95, "market_prob": 0.5}  # best rank
    # ...but without deterministic executable-depth proof it is NOT tradeable.
    assert pe.is_tradeable(top) is False
    top_with_proof = {**top, "executable_depth_proof": True}
    assert pe.is_tradeable(top_with_proof) is True
    # explicit opt-out path
    assert pe.is_tradeable(top, require_depth_proof=False) is True


def test_quant_responsibilities_full_scope():
    for k in ("acquisition_ingestion", "preprocessing_features",
              "probabilistic_modeling", "calibration", "bregman_signal_development",
              "risk_portfolio", "backtesting", "optimization_robustness",
              "clobv2_execution", "monitoring", "compliance_security_ops"):
        assert k in pe.QUANT_RESPONSIBILITIES and pe.QUANT_RESPONSIBILITIES[k]

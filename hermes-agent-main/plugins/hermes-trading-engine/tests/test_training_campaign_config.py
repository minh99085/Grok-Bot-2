"""Campaign + algorithm-freeze config fields (PAPER ONLY).

Quant scope — *Strategy Optimization & Robustness Testing* + *Compliance*: the
campaign config freezes algorithm development (no parameter promotion) and never
touches any live/micro-live/guarded-live flag.
"""

from __future__ import annotations

from engine.training.config import TrainingConfig


def test_campaign_defaults_disabled():
    c = TrainingConfig()
    assert c.campaign_enabled is False
    assert c.algorithm_freeze_mode is False
    assert c.campaign_name == "institutional_paper_campaign"
    assert c.campaign_target_min_days == 14
    assert c.campaign_target_min_decisions == 1000
    assert c.campaign_target_min_paper_trades == 300
    assert c.campaign_target_min_resolved_labels == 100
    assert c.campaign_target_min_bregman_candidates == 50
    assert c.campaign_max_bregman_false_positives == 0


def test_freeze_forces_no_param_promotion():
    c = TrainingConfig(algorithm_freeze_mode=True, aggressive_can_promote_params=True)
    assert c.algorithm_freeze_mode is True
    assert c.aggressive_can_promote_params is False  # forced off by freeze


def test_aggressive_paper_with_freeze_cannot_promote():
    c = TrainingConfig.aggressive_paper(algorithm_freeze_mode=True)
    assert c.aggressive_can_promote_params is False
    # aggressive paper stays PAPER ONLY
    assert c.is_paper_only is True


def test_env_parsing(monkeypatch):
    monkeypatch.setenv("POLYMARKET_CAMPAIGN_ENABLED", "1")
    monkeypatch.setenv("POLYMARKET_CAMPAIGN_NAME", "inst_v2")
    monkeypatch.setenv("POLYMARKET_ALGORITHM_FREEZE_MODE", "1")
    monkeypatch.setenv("POLYMARKET_CAMPAIGN_TARGET_MIN_DAYS", "21")
    monkeypatch.setenv("POLYMARKET_CAMPAIGN_TARGET_MIN_DECISIONS", "2000")
    monkeypatch.setenv("POLYMARKET_CAMPAIGN_TARGET_MIN_PAPER_TRADES", "500")
    monkeypatch.setenv("POLYMARKET_CAMPAIGN_TARGET_MIN_RESOLVED_LABELS", "200")
    monkeypatch.setenv("POLYMARKET_CAMPAIGN_TARGET_MIN_BREGMAN_CANDIDATES", "80")
    monkeypatch.setenv("POLYMARKET_CAMPAIGN_MAX_BREGMAN_FALSE_POSITIVES", "0")
    c = TrainingConfig.from_env()
    assert c.campaign_enabled is True
    assert c.campaign_name == "inst_v2"
    assert c.algorithm_freeze_mode is True
    assert c.aggressive_can_promote_params is False  # freeze forces it off
    assert c.campaign_target_min_days == 21
    assert c.campaign_target_min_decisions == 2000
    assert c.campaign_target_min_paper_trades == 500
    assert c.campaign_target_min_resolved_labels == 200
    assert c.campaign_target_min_bregman_candidates == 80


def test_campaign_never_touches_live_flags():
    c = TrainingConfig(campaign_enabled=True, algorithm_freeze_mode=True)
    # campaign mode is still strictly paper
    assert c.is_paper_only is True
    assert c.mode in ("disabled", "observe_only", "paper_train")

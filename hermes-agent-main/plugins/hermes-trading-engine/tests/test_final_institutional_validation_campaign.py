"""Final institutional validation campaign — pass/fail across all 9 profiles.

Quant scope — every stage end-to-end: Data Acquisition/Ingestion + Preprocessing
(evidence is read-only), Statistical & Probabilistic Modeling (calibration), Signal
Generation w/ Bregman priority, Risk Management & Portfolio Optimization, Backtesting
& Simulation, Strategy Optimization & Robustness (ablations), CLOB v2 Execution
(realistic-fill), Live Trading & Monitoring (readiness verdict), Compliance/Security
(no live trading; certificate only when ALL gates pass). PAPER ONLY.
"""

from __future__ import annotations

from engine.training.validation_campaign import (
    CAMPAIGN_PROFILE_IDS, CAMPAIGN_REQUIRED_CRITERIA, campaign_markdown,
    compute_profile_metrics, default_campaign_evidence, run_campaign)

_FINAL_METRIC_KEYS = (
    "net_pnl", "after_cost_expectancy", "sharpe", "sortino", "calmar", "omega",
    "max_drawdown", "cvar", "profit_factor", "turnover", "brier", "log_loss", "ece",
    "ci_coverage", "edge_decay", "fill_quality", "slippage_bps", "markout",
    "label_quality", "bregman_fp_rate", "capital_efficiency", "readiness_state",
)


def test_campaign_has_nine_named_profiles():
    expected = {
        "conservative_baseline", "aggressive_learning", "aggressive_plus_profit_governor",
        "bregman_certified_only", "bregman_plus_chainlink", "no_research_ablation",
        "no_chainlink_ablation", "realistic_fill_validation", "micro_live_dry_run",
    }
    assert set(CAMPAIGN_PROFILE_IDS) == expected
    assert len(CAMPAIGN_PROFILE_IDS) == 9


def test_all_passing_campaign_is_ready_and_mints_certificate():
    report = run_campaign(default_campaign_evidence())
    assert report.overall_ready is True
    assert report.readiness_state in ("micro_canary_ready", "canary_ready")
    assert report.blockers == []
    assert report.certificate is not None
    # the certificate is dry-run / not-manually-enabled => never auto-enables live
    assert report.certificate.dry_run is True
    assert report.certificate.manual_enable is False


def test_one_failing_profile_blocks_and_no_certificate():
    ev = default_campaign_evidence()
    ev["aggressive_learning"]["after_cost_expectancy"] = -0.02  # negative edge
    report = run_campaign(ev)
    assert report.overall_ready is False
    assert report.certificate is None
    assert report.blockers
    assert any("after_cost_profitability" in b for b in report.blockers)


def test_required_criteria_are_all_present():
    report = run_campaign(default_campaign_evidence())
    for crit in CAMPAIGN_REQUIRED_CRITERIA:
        assert crit in report.criteria


def test_every_profile_has_full_final_metric_set():
    report = run_campaign(default_campaign_evidence())
    assert set(report.profiles.keys()) == set(CAMPAIGN_PROFILE_IDS)
    for pid, pr in report.profiles.items():
        for key in _FINAL_METRIC_KEYS:
            assert key in pr.metrics, f"{pid} missing metric {key}"


def test_report_is_machine_readable_json_and_markdown():
    report = run_campaign(default_campaign_evidence())
    d = report.to_dict()
    for key in ("overall_ready", "readiness_state", "blockers", "criteria", "profiles",
                "certificate"):
        assert key in d
    import json
    json.dumps(d)  # must be serializable
    md = campaign_markdown(report)
    assert isinstance(md, str)
    assert "Institutional validation campaign" in md
    assert "Readiness verdict" in md


def test_compute_profile_metrics_defaults_are_safe():
    m = compute_profile_metrics({})
    for key in _FINAL_METRIC_KEYS:
        assert key in m

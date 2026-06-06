"""Pass-8: unified inspection summary (machine + human readable) + recommendations.

Aggregates every prior-pass output into one stable schema + a markdown report
with all required sections, deterministic recommendations, and a console line.
Observability only — no strategy/threshold changes. PAPER ONLY.
"""

from __future__ import annotations

from engine.markets import universe_manager as um
from engine.training import PolymarketPaperTrainer, TrainingConfig
from engine.training.inspection_summary import (
    REQUIRED_SECTIONS, build_inspection_summary, console_summary, recommendations,
    to_markdown, validate_report,
)

from tests._pmtrain_helpers import clean_live_env, market

_NOW = 1_000_000.0

_REQUIRED_KEYS = {
    "run", "feature_activation", "bregman_funnel", "strategy_priority", "paper_realism",
    "profitability_ranking", "active_learning", "correlation_risk", "rejection_waterfall",
    "trade_ledger_summary", "readiness", "data_quality", "recommendations",
}


def _trainer(tmp_path, monkeypatch, **cfg):
    clean_live_env(monkeypatch, tmp_path)
    cfg.setdefault("max_open_trades", 8)
    return PolymarketPaperTrainer(TrainingConfig(mode="paper_train", **cfg), data_dir=tmp_path)


def _bregman_event(asks, group="elect"):
    recs = []
    for i, a in enumerate(asks):
        raw = market(i, bid=round(a - 0.02, 4), ask=a, liq=20_000, depth=2000,
                     category="crypto", group=group, now=_NOW)
        raw["negRiskComplete"] = True
        recs.append(um.MarketRecord.from_raw(raw, now=_NOW))
    return recs


# --- schema + sections ------------------------------------------------------

def test_inspection_summary_has_all_top_level_keys(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    s = t.inspection_summary()
    assert _REQUIRED_KEYS <= set(s.keys())
    assert s["paper_only"] is True
    assert s["run"]["live_trading_disabled"] is True


def test_report_contains_all_required_sections(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    md = to_markdown(t.inspection_summary())
    assert validate_report(md) == []
    for sec in REQUIRED_SECTIONS:
        assert f"## {sec}" in md


def test_bregman_metrics_in_unified_report(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    assert t._run_bregman(_bregman_event([0.28, 0.30, 0.30]), _NOW) == 1
    s = t.inspection_summary()
    assert s["bregman_funnel"]["bundles_opened"] == 1
    assert s["bregman_funnel"]["certified_opportunities"] >= 1
    md = to_markdown(s)
    assert "Bregman / ABCAS Funnel" in md
    assert s["trade_ledger_summary"]["bregman_legs"] == 3


def test_paper_realism_profitability_active_learning_correlation_in_report(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    md = to_markdown(t.inspection_summary())
    assert "Paper Execution Realism" in md
    assert "Profitability Ranking" in md
    assert "Active Learning / Exploration" in md
    assert "Correlation / Cluster Risk" in md


# --- feature activation proof (no false "active") ---------------------------

def test_feature_activation_uses_runtime_status_strings(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    feats = {f["feature"]: f for f in t.inspection_summary()["feature_activation"]["features"]}
    allowed = {"active_controls_trades", "active_telemetry_only", "configured_but_no_candidates",
               "disabled_by_config", "imported_unused", "missing_metrics", "unknown"}
    assert all(f["actual_state"] in allowed for f in feats.values())
    # with no bregman opened, bregman execution must NOT claim active_controls_trades
    assert feats["Bregman paper execution"]["actual_state"] == "configured_but_no_candidates"


def test_feature_activation_bregman_active_after_open(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    t._run_bregman(_bregman_event([0.28, 0.30, 0.30]), _NOW)
    feats = {f["feature"]: f for f in t.inspection_summary()["feature_activation"]["features"]}
    assert feats["Bregman paper execution"]["actual_state"] == "active_controls_trades"


# --- rejection waterfall ----------------------------------------------------

def test_rejection_waterfall_aggregates(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    # overround bregman set -> no_positive_edge rejection recorded
    t._run_bregman(_bregman_event([0.40, 0.40, 0.40]), _NOW)
    rw = t.rejection_waterfall()
    assert rw["total_rejections"] >= 1
    assert any("bregman" in r["reason"] for r in rw["ranked_reasons"])
    assert "bregman" in rw["by_strategy"]


# --- readiness separation ---------------------------------------------------

def test_readiness_excludes_shadow_exploration_reference(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    rd = t.inspection_summary()["readiness"]
    assert rd["readiness_excludes_shadow_only"] is True
    assert rd["readiness_excludes_exploration"] is True
    assert rd["readiness_excludes_reference_fills"] is True
    assert rd["readiness_excludes_fallback_fills"] is True
    assert rd["live_trading_enabled"] is False


# --- recommendations --------------------------------------------------------

def test_recommendations_deterministic_certified_none_opened():
    summary = {
        "bregman_funnel": {"raw_groups_discovered": 5, "certified_opportunities": 3,
                           "bundles_opened": 0},
        "paper_realism": {}, "strategy_priority": {}, "profitability_ranking": {},
        "active_learning": {}, "correlation_risk": {}, "run": {},
    }
    codes = [r["code"] for r in recommendations(summary)]
    assert "bregman_certified_none_opened" in codes


def test_recommendations_nominal_when_clean():
    summary = {"bregman_funnel": {"raw_groups_discovered": 0, "certified_opportunities": 0,
                                  "bundles_opened": 0},
               "paper_realism": {}, "strategy_priority": {}, "profitability_ranking": {},
               "active_learning": {"active_learning_candidates_considered": 0},
               "correlation_risk": {}, "run": {"realistic_trades": 1}}
    codes = [r["code"] for r in recommendations(summary)]
    assert codes  # always at least one recommendation


# --- console + graceful empties ---------------------------------------------

def test_console_summary_renders_on_zero_metrics():
    s = build_inspection_summary({}, {"features": []})
    line = console_summary(s)
    assert "Run complete." in line and "Bregman groups discovered/certified/opened: 0/0/0" in line


def test_build_handles_missing_optional_metrics():
    s = build_inspection_summary({"mode": "paper_train"}, {"features": []})
    assert _REQUIRED_KEYS <= set(s.keys())
    assert validate_report(to_markdown(s)) == []


def test_write_inspection_artifacts(tmp_path, monkeypatch):
    t = _trainer(tmp_path, monkeypatch)
    t._begin_correlation_phase()
    summary = t.write_inspection_artifacts(tmp_path)
    assert (tmp_path / "metrics" / "inspection_summary.json").is_file()
    assert (tmp_path / "reports" / "paper_training_inspection.md").is_file()
    assert summary["paper_only"] is True

"""Runtime feature-activation audit (PAPER ONLY, read-only instrumentation).

Pass-1 audit: a machine-readable truth table of which algorithmic edge modules
are TRULY active in the paper-training trade loop vs imported-only, telemetry-only,
or dead. The findings below are derived by TRACING the actual call path from
``scripts/start_polymarket_paper_training.py`` →
``engine/training/polymarket_trainer.py`` → trade opening — not from file/class
names. This module performs no trading and changes no behavior.

Runtime-status vocabulary:
* ``active``        — runs and controls actual paper trade selection/opening.
* ``telemetry``     — runs but only reports; does not affect trades.
* ``annotated``     — data is computed/attached but the gate is not enforced.
* ``imported``      — referenced/constructed but its decision path is unused.
* ``dead``          — defined but not reached by the runtime path.

Evidence is tied to the trainer call chain (this branch, ~1844-line trainer):
``run_tick → scanner.scan → records → watch[:live_watch_limit] →
candidates=watch[:budget] → _run_bregman(candidates) → for rec: _consider →
edge_engine.best_side → (would_trade|_explore_gate) → _open``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("hte.feature_activation")

SCHEMA_VERSION = "feature_activation/1.0"


def _bool(cfg, name, default=None):
    if cfg is None:
        return default
    return getattr(cfg, name, default)


# The audited truth table. ``controls_trades`` / ``telemetry_only`` reflect the
# traced runtime path. ``cfg_probe`` (optional) refines status from a live config.
FEATURES: list[dict] = [
    {
        "feature": "Raw ABCAS/Bregman scanner",
        "files": ["engine/strategies/bregman_scanner.py",
                  "engine/arbitrage/constraint_discovery.py"],
        "runtime_status": "telemetry",
        "controls_trades": False, "telemetry_only": True,
        "flag": "BREGMAN_PAPER_SCAN_ENABLED / ABCAS_ENABLED",
        "evidence": "Run only from start_polymarket_paper_training loop; writes "
                    "bregman_scan.json + metrics/bregman.json. NOT imported by "
                    "polymarket_trainer.py — never opens a paper position.",
        "risk": "ABCAS looks 'enabled' and reports candidates but never trades — "
                "false impression the flagship edge is live.",
    },
    {
        "feature": "Trainer Bregman certifier",
        "files": ["engine/training/bregman_execution.py",
                  "engine/training/bregman_grouping.py",
                  "engine/training/polymarket_trainer.py"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "bregman_enabled (cfg)",
        "evidence": "run_tick → _run_bregman → _bregman_tradable → scan_bregman → "
                    "group_markets(records)+certify_all (trainer ~617-657).",
        "risk": "Certifies only over the directional shortlist (see input universe).",
    },
    {
        "feature": "Bregman paper execution",
        "files": ["engine/training/polymarket_trainer.py:_open_bregman_sets/_open_bregman"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "bregman_execution_enabled (cfg) + mode==paper_train",
        "evidence": "_open_bregman_sets gated on paper_train + bregman_execution_enabled; "
                    "appends hedged-leg PaperPositions via RiskEngine+PaperBroker; "
                    "skips group_type=='binary_yes_no' (synthetic NO leg).",
        "risk": "Almost never fires: binary YES/NO (most of Polymarket) is skipped "
                "and the input is the shortlist, so few/no real multi-leg sets.",
    },
    {
        "feature": "Bregman INPUT UNIVERSE (catalog vs shortlist)",
        "files": ["engine/training/polymarket_trainer.py:run_tick"],
        "runtime_status": "annotated",
        "controls_trades": True, "telemetry_only": False,
        "flag": "live_watch_limit / trade_candidate_limit / paper_decision_budget",
        "evidence": "group_markets is fed candidates=watch[:budget], "
                    "watch=records[:live_watch_limit], records=scanner shortlist — "
                    "NOT raw_catalog.",
        "risk": "HIGH: Bregman/ABCAS sees only the directional shortlist, so most "
                "coherence arbitrage across the full market universe is invisible.",
    },
    {
        "feature": "Graph grouping (groups_from_graph)",
        "files": ["engine/training/bregman_grouping.py"],
        "runtime_status": "dead",
        "controls_trades": False, "telemetry_only": False,
        "flag": "(none)",
        "evidence": "No groups_from_graph() on this branch; the active grouping is "
                    "group_markets(records). Dependency-graph clustering exists but "
                    "is used only for cluster_id annotation.",
        "risk": "Structural graph grouping not used for arbitrage discovery.",
    },
    {
        "feature": "Profitability-first ranking",
        "files": ["engine/training/candidate_ranker.py:annotate_profitability",
                  "engine/training/profitability_governor.py",
                  "engine/training/market_scanner.py"],
        "runtime_status": "imported",
        "controls_trades": False, "telemetry_only": False,
        "flag": "profitability_first (annotate_profitability arg; UNWIRED)",
        "evidence": "market_scanner.scan calls rank_candidates (quality score) + "
                    "annotate_feedback_value, then shortlist=ranked[:shortlist_limit]. "
                    "annotate_profitability() is never called in the runtime path.",
        "risk": "HIGH: candidates are truncated by quality score, NOT after-cost EV — "
                "profitable-but-lower-quality markets are dropped before any decision.",
    },
    {
        "feature": "Active learning selector",
        "files": ["engine/training/active_learning.py:ActiveLearningSelector"],
        "runtime_status": "dead",
        "controls_trades": False, "telemetry_only": False,
        "flag": "active_learning_enabled (reported only)",
        "evidence": "ActiveLearningSelector is not imported by the trainer or any "
                    "engine/scripts runtime module; feedback_value is annotated but "
                    "the selector is never invoked.",
        "risk": "Exploration is blind; high-feedback-value markets are not prioritized.",
    },
    {
        "feature": "Random/hash exploration",
        "files": ["engine/training/polymarket_trainer.py:_explore_gate/_consider"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "exploration_enabled / exploration_rate (cfg)",
        "evidence": "_explore_gate = sha256(market+tick) % 1000 < exploration_rate; "
                    "opens near-miss exploration trades at capped "
                    "exploration_notional_usd (paper_train only).",
        "risk": "Deterministic hash sampling (not learning-value); correctly tiny + "
                "counts_for_readiness=False, but adds no targeted edge.",
    },
    {
        "feature": "Cluster/correlation gate",
        "files": ["engine/training/market_scanner.py (sets cluster_id)",
                  "engine/training/edge_engine.py (accepts open_clusters)",
                  "engine/training/polymarket_trainer.py:_consider"],
        "runtime_status": "annotated",
        "controls_trades": False, "telemetry_only": False,
        "flag": "(cluster_id computed; open_clusters NOT passed)",
        "evidence": "market_scanner sets d['cluster_id']=graph.cluster_of(...); "
                    "EdgeEngine.best_side accepts open_clusters/cluster_id, but the "
                    "trainer call passes only open_event_groups (group_key), so the "
                    "cluster gate is never triggered.",
        "risk": "Correlated (non-same-event) exposure is NOT blocked — concentration "
                "risk; only same-event group_key duplication is gated.",
    },
    {
        "feature": "Paper fill realism (slippage/depth)",
        "files": ["engine/training/paper_policy.py", "engine/execution/paper_broker.py",
                  "engine/training/config.py"],
        "runtime_status": "annotated",
        "controls_trades": True, "telemetry_only": False,
        "flag": "realistic_fill_enabled (default False)",
        "evidence": "realistic_fill_enabled defaults False (slippage+depth modeling "
                    "OFF) outside the campaign-safe profile; status emits "
                    "fill_realism=null.",
        "risk": "HIGH: without realistic_fill_enabled, fills can be optimistic and "
                "null telemetry hides whether PnL is inflated.",
    },
    {
        "feature": "Stale-book rejection",
        "files": ["engine/training/edge_engine.py", "engine/training/config.py"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "reject_on_stale_book=True / clob_stale_ms=3000",
        "evidence": "Hard reject in EdgeEngine.evaluate when the book is stale.",
        "risk": "Low (correctly enforced) — disabling it would allow stale fills.",
    },
    {
        "feature": "Reference-price fill fallback",
        "files": ["engine/execution/paper_broker.py", "engine/training/config.py"],
        "runtime_status": "imported",
        "controls_trades": True, "telemetry_only": False,
        "flag": "allow_pm_reference_price_fills=False (default)",
        "evidence": "PaperBroker supports reference-price fills but they are OFF by "
                    "default (and campaign-safe forces them off).",
        "risk": "If enabled, produces fantasy fills not backed by a real ask.",
    },
    {
        "feature": "Spread/depth gates",
        "files": ["engine/training/edge_engine.py", "engine/training/config.py"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "max_spread=0.08 / min_depth_at_price=50 / max_fill_depth_fraction=0.35",
        "evidence": "Hard rejects in EdgeEngine.evaluate before edge math.",
        "risk": "Low — correctly enforced hard gates.",
    },
    {
        "feature": "Ambiguity gate",
        "files": ["engine/training/edge_engine.py", "engine/training/config.py"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "max_ambiguity_score=0.35 (hard) + ambiguity_penalty_weight (soft)",
        "evidence": "Hard reject above max_ambiguity_score; soft penalty below.",
        "risk": "Low — enforced; mis-set threshold could over/under-filter.",
    },
    {
        "feature": "Chainlink conditioning",
        "files": ["engine/training/chainlink_oracle.py",
                  "engine/training/polymarket_trainer.py", "engine/training/edge_engine.py"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "chainlink_enabled / btc_pulse_require_chainlink",
        "evidence": "Read each tick (read-only); conditions/gates Bregman + BTC Pulse "
                    "and applies a directional penalty when stale.",
        "risk": "Low for paper; stale anchor correctly penalizes.",
    },
    {
        "feature": "News/research/model overlay",
        "files": ["engine/research/news_scanner.py", "engine/research/probability.py",
                  "engine/training/edge_engine.py"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "NEWS_SCANNER_ENABLED / RESEARCH_USE_IN_STRATEGY",
        "evidence": "Advisory, read-only; feeds the probability estimate when "
                    "RESEARCH_USE_IN_STRATEGY; cannot bypass risk/fill gates.",
        "risk": "Medium: research nudges probability; weak calibration could bias edge.",
    },
    {
        "feature": "Grok/LLM reasoning overlay",
        "files": ["engine/research/grok_client.py"],
        "runtime_status": "telemetry",
        "controls_trades": False, "telemetry_only": True,
        "flag": "NEWS_ENABLE_GROK_PACKET (grok_with_news_count null in report)",
        "evidence": "Advisory research-only; cannot place/size/approve. Report shows "
                    "grok_with_news_count=null (telemetry gap, not a trade control).",
        "risk": "Low for trades; unmeasured contribution (null counters).",
    },
    {
        "feature": "Profitability governor",
        "files": ["engine/training/profitability_governor.py"],
        "runtime_status": "dead",
        "controls_trades": False, "telemetry_only": False,
        "flag": "(reached only via the unused annotate_profitability)",
        "evidence": "Not referenced by polymarket_trainer.py; only used inside "
                    "annotate_profitability, which is itself never called.",
        "risk": "No after-cost graylist/throttle is applied to directional ranking.",
    },
    {
        "feature": "Position/open-slot governor",
        "files": ["engine/training/polymarket_trainer.py:run_tick",
                  "engine/training/edge_engine.py", "engine/risk.py"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "max_open_trades / RiskEngine caps",
        "evidence": "run_tick breaks on len(open_positions) >= max_open_trades; "
                    "EdgeEngine gates max_open_trades; RiskEngine enforces exposure.",
        "risk": "Low — enforced.",
    },
    {
        "feature": "Stop-loss/take-profit/settlement handling",
        "files": ["engine/training/polymarket_trainer.py:_monitor"],
        "runtime_status": "active",
        "controls_trades": True, "telemetry_only": False,
        "flag": "(monitor/settlement each tick)",
        "evidence": "_monitor marks open positions to market each tick and settles "
                    "resolved markets into realized PnL.",
        "risk": "Medium: explicit SL/TP is mark-and-settle; no intra-round stop.",
    },
]


# Top edge leaks ranked by expected impact on real profitability.
TOP_EDGE_LEAKS: list[dict] = [
    {"rank": 1, "leak": "Bregman/ABCAS only sees the directional shortlist, not the "
                        "full normalized catalog", "impact": "highest",
     "feature": "Bregman INPUT UNIVERSE (catalog vs shortlist)"},
    {"rank": 2, "leak": "Raw ABCAS scanner is telemetry-only — the flagship edge "
                        "never opens a trade", "impact": "high",
     "feature": "Raw ABCAS/Bregman scanner"},
    {"rank": 3, "leak": "Profitability-first ranking is unused — candidates truncated "
                        "by quality score, not after-cost EV", "impact": "high",
     "feature": "Profitability-first ranking"},
    {"rank": 4, "leak": "realistic_fill_enabled defaults False — paper PnL may be "
                        "optimistic and fill_realism telemetry is null", "impact": "high",
     "feature": "Paper fill realism (slippage/depth)"},
    {"rank": 5, "leak": "Cluster/correlation gate annotated but not enforced "
                        "(open_clusters not passed)", "impact": "medium-high",
     "feature": "Cluster/correlation gate"},
    {"rank": 6, "leak": "binary_yes_no Bregman groups skipped (correct safety) leaves "
                        "the trainer Bregman with almost nothing to trade", "impact": "medium-high",
     "feature": "Bregman paper execution"},
    {"rank": 7, "leak": "Active learning unused — exploration is blind hash sampling",
     "impact": "medium", "feature": "Active learning selector"},
    {"rank": 8, "leak": "Profitability governor dead — no after-cost graylist/throttle "
                        "on directional ranking", "impact": "medium",
     "feature": "Profitability governor"},
    {"rank": 9, "leak": "Grok/news evidence counters null — research overlay impact "
                        "is unmeasured", "impact": "low-medium",
     "feature": "Grok/LLM reasoning overlay"},
    {"rank": 10, "leak": "Two divergent Bregman implementations (strategies/"
                         "bregman_scanner ABCAS vs training/bregman_execution) — "
                         "reporting and execution disagree", "impact": "medium",
     "feature": "Trainer Bregman certifier"},
]

PASS2_RECOMMENDATION = {
    "recommended": True,
    "headline": "Pass 2 SHOULD connect ABCAS to certified paper execution — but only "
                "AFTER widening the Bregman input universe and unifying the two "
                "Bregman implementations.",
    "preconditions": [
        "Feed the FULL normalized catalog (engine.arbitrage.constraint_discovery) to "
        "combinatorial discovery, not the directional shortlist.",
        "Require BOTH legs real + executable (no synthetic binary NO leg) before any "
        "certified-executable open.",
        "Turn on realistic_fill_enabled so certified after-cost profit is real.",
        "Unify engine/strategies/bregman_scanner (ABCAS) with engine/training/"
        "bregman_execution so reporting == execution.",
    ],
    "guardrails": [
        "PAPER ONLY — route certified-executable arbs through the existing RiskEngine "
        "+ PaperBroker; never enable a live path.",
        "Keep EXECUTABLE_AFTER_COST_CERTIFIED gating; theoretical-only stays shadow.",
    ],
    "rationale": "Executing ABCAS today would produce ~0 trades (shortlist input + "
                 "binary skip) or fantasy multi-leg fills (realistic_fill off). Fix "
                 "the input universe + fill realism first.",
}


def build_feature_activation(cfg: Any = None, status: Optional[dict] = None) -> dict:
    """Build the machine-readable feature-activation audit (read-only, pure).

    ``cfg`` (optional TrainingConfig) refines a few live flags; ``status`` (optional
    training status) is used to note observed runtime values. Never trades."""
    features = [dict(f) for f in FEATURES]

    # Optional live-config refinement (does not change the traced verdicts).
    if cfg is not None:
        live = {
            "bregman_execution_enabled": _bool(cfg, "bregman_execution_enabled", True),
            "realistic_fill_enabled": _bool(cfg, "realistic_fill_enabled", False),
            "allow_pm_reference_price_fills": _bool(cfg, "allow_pm_reference_price_fills", False),
            "reject_on_stale_book": _bool(cfg, "reject_on_stale_book", True),
            "exploration_enabled": _bool(cfg, "exploration_enabled", False),
            "active_learning_enabled": _bool(cfg, "active_learning_enabled", False),
            "max_spread": _bool(cfg, "max_spread", 0.08),
            "min_depth_at_price": _bool(cfg, "min_depth_at_price", 50.0),
            "max_ambiguity_score": _bool(cfg, "max_ambiguity_score", 0.35),
        }
    else:
        live = {}

    counts = {"active": 0, "telemetry": 0, "annotated": 0, "imported": 0, "dead": 0}
    for f in features:
        counts[f["runtime_status"]] = counts.get(f["runtime_status"], 0) + 1

    inflation_risks = [f["feature"] for f in features
                       if f["feature"] in ("Paper fill realism (slippage/depth)",
                                           "Reference-price fill fallback",
                                           "Raw ABCAS/Bregman scanner")]

    return {
        "schema_version": SCHEMA_VERSION,
        "paper_only": True,
        "summary": {
            "truly_active": [f["feature"] for f in features if f["controls_trades"]
                             and f["runtime_status"] == "active"],
            "telemetry_only": [f["feature"] for f in features if f["telemetry_only"]],
            "dead_or_unused": [f["feature"] for f in features
                               if f["runtime_status"] in ("dead", "imported")],
            "pnl_inflation_risks": inflation_risks,
            "status_counts": counts,
        },
        "features": features,
        "top_edge_leaks": [dict(x) for x in TOP_EDGE_LEAKS],
        "pass2_recommendation": PASS2_RECOMMENDATION,
        "live_config": live,
        "note": "PASS-1 audit/instrumentation only. No trade-path, threshold, sizing, "
                "or live-execution changes. Verdicts traced from run_tick to open.",
    }


def to_markdown(audit: dict) -> str:
    """Render the audit dict to a human-readable markdown report (pure)."""
    L: list[str] = []
    L.append("# Feature Activation Audit (Pass 1) — Hermes Polymarket Paper Training")
    L.append("")
    L.append("_PAPER ONLY · audit + instrumentation only · no strategy/threshold/"
             "sizing/live changes. Verdicts traced from `run_tick` to trade open._")
    L.append("")
    s = audit["summary"]
    L.append("## Summary")
    L.append(f"- **Truly active (control trades):** {', '.join(s['truly_active'])}")
    L.append(f"- **Telemetry-only:** {', '.join(s['telemetry_only'])}")
    L.append(f"- **Dead / imported-only:** {', '.join(s['dead_or_unused'])}")
    L.append(f"- **PnL-inflation risks:** {', '.join(s['pnl_inflation_risks'])}")
    L.append(f"- Status counts: {s['status_counts']}")
    L.append("")
    L.append("## Runtime feature truth table")
    L.append("")
    L.append("| Feature | File(s) | Runtime status | Controls trades? | Telemetry only? "
             "| Config/env flag | Evidence | Risk if unchanged |")
    L.append("|---|---|---|---|---|---|---|---|")
    for f in audit["features"]:
        files = "<br>".join(f["files"])
        L.append(f"| {f['feature']} | {files} | `{f['runtime_status']}` | "
                 f"{'YES' if f['controls_trades'] else 'no'} | "
                 f"{'YES' if f['telemetry_only'] else 'no'} | {f['flag']} | "
                 f"{f['evidence']} | {f['risk']} |")
    L.append("")
    L.append("## Top 10 edge leaks (ranked by profit impact)")
    L.append("")
    for x in audit["top_edge_leaks"]:
        L.append(f"{x['rank']}. **[{x['impact']}]** {x['leak']} _( {x['feature']} )_")
    L.append("")
    p2 = audit["pass2_recommendation"]
    L.append("## Pass 2 recommendation")
    L.append(f"- **Recommended:** {p2['recommended']}")
    L.append(f"- {p2['headline']}")
    L.append("- Preconditions:")
    for c in p2["preconditions"]:
        L.append(f"  - {c}")
    L.append("- Guardrails:")
    for c in p2["guardrails"]:
        L.append(f"  - {c}")
    L.append(f"- Rationale: {p2['rationale']}")
    L.append("")
    return "\n".join(L)

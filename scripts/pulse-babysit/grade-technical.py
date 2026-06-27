#!/usr/bin/env python3
"""Grade technical data quality from pulled VPS artifacts.

Produces monitoring/technical-grades.json, grades-history.jsonl, and TECHNICAL_GRADES.md.
Reuses engine report scoring plus a technical_runtime dimension (RTDS, TV, gates, pipeline).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = ROOT / "hermes-agent-main" / "plugins" / "hermes-trading-engine"
LATEST = ROOT / "vps_full_reports" / "latest"
MONITOR = ROOT / "monitoring"
GRADES_JSON = MONITOR / "technical-grades.json"
GRADES_HISTORY = MONITOR / "grades-history.jsonl"
GRADES_MD = MONITOR / "TECHNICAL_GRADES.md"
MANIFEST = MONITOR / "design-manifest.json"

sys.path.insert(0, str(ENGINE_ROOT))
from engine.pulse.performance_scoring import (  # noqa: E402
    _clamp,
    _grade,
    _weighted,
    compute_report_scores,
)
from engine.pulse.reporting import build_report_sections  # noqa: E402


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()[:12]
    except Exception:
        return None


def _near(actual: float | int | None, expected: float | int, tol: float = 0.02) -> bool:
    if actual is None:
        return False
    return abs(float(actual) - float(expected)) <= tol


def score_rtds_health(status: dict) -> tuple[float, dict]:
    oracle = (status.get("oracle") or {})
    rtds = oracle.get("rtds") or {}
    price = status.get("price") or {}

    connected = bool(rtds.get("connected"))
    fresh = bool(rtds.get("oracle_fresh"))
    running = bool(rtds.get("running"))
    age = float(rtds.get("oracle_age_s") or price.get("age_s") or 999.0)
    reconnects = int(rtds.get("reconnects") or 0)
    max_age = float(rtds.get("max_age_s") or 45.0)

    conn_score = 100.0 if connected and running else 0.0
    fresh_score = 100.0 if fresh else _clamp(100.0 - max(0.0, age - max_age) * 4.0)
    stability_score = _clamp(100.0 - reconnects * 15.0)
    feed_score = 100.0 if price.get("last_fetch_ok", True) else 40.0

    total, breakdown = _weighted([
        ("connected", conn_score, 35),
        ("oracle_fresh", fresh_score, 30),
        ("stability", stability_score, 20),
        ("price_feed", feed_score, 15),
    ])
    return total, breakdown


def score_tv_intake(status: dict, light: dict) -> tuple[float, dict]:
    tv = (status.get("tradingview") or light.get("tradingview") or {})
    received = int(tv.get("tradingview_alerts_received") or 0)
    valid = int(tv.get("tradingview_alerts_valid") or 0)
    rejected = int(tv.get("tradingview_alerts_rejected") or 0)

    observe_only = bool(tv.get("tradingview_observe_only", True))
    observe_score = 100.0 if observe_only else 0.0

    flow_score = _clamp(valid / 5.0) if valid < 100 else 100.0
    reject_rate = rejected / max(received, 1)
    reject_score = _clamp(100.0 - reject_rate * 300.0)

    sg = tv.get("signal_gate") or {}
    mg = tv.get("mtf_gate") or {}
    cg = tv.get("context_gate") or {}
    trade_gates_off = not any(
        (g or {}).get("enabled") for g in (sg, mg, cg)
    )
    gate_score = 100.0 if trade_gates_off else 30.0

    mtf = tv.get("tradingview_mtf_confirmation") or {}
    tf_fresh = int(mtf.get("trend_fresh_count") or 0)
    mtf_score = _clamp(40.0 + tf_fresh * 20.0)

    total, breakdown = _weighted([
        ("observe_only", observe_score, 25),
        ("alert_flow", flow_score, 25),
        ("reject_rate", reject_score, 15),
        ("trade_gates_off", gate_score, 20),
        ("mtf_freshness", mtf_score, 15),
    ])
    return total, breakdown


def score_design_compliance(status: dict, manifest: dict) -> tuple[float, dict]:
    cfg = status.get("config") or {}
    cohort = status.get("baseline_cohort_gate") or {}
    tv = status.get("tradingview") or {}
    design = (manifest.get("entry_design") or {})

    checks: list[tuple[str, float, float]] = []

    series = status.get("pulse_series_slugs") or []
    expect_series = design.get("series", "btc-up-or-down-15m")
    series_ok = expect_series in series if isinstance(series, list) else False
    checks.append(("series_15m", 100.0 if series_ok else 0.0, 15))

    green = bool(cohort.get("green_path_enabled"))
    checks.append(("green_path", 100.0 if green else 40.0, 10))

    paper = bool(status.get("paper_only", True))
    checks.append(("paper_only", 100.0 if paper else 0.0, 10))

    grok = cfg.get("grok_decider_mode")
    checks.append(("grok_shadow", 100.0 if grok == "shadow" else 60.0, 5))

    tick = float(cfg.get("tick_seconds") or 0)
    expect_tick = float(design.get("tick_seconds") or 15)
    checks.append(("tick_seconds", 100.0 if _near(tick, expect_tick, 1.0) else 50.0, 10))

    max_p = float(cfg.get("max_price") or 0)
    expect_max = float(design.get("max_entry_price") or 0.70)
    checks.append(("max_price", 100.0 if _near(max_p, expect_max, 0.05) else 50.0, 10))

    min_edge = float(cfg.get("min_edge") or 0)
    expect_edge = float(design.get("min_edge") or 0.02)
    checks.append(("min_edge", 100.0 if _near(min_edge, expect_edge, 0.005) else 50.0, 5))

    min_rr = float(cfg.get("min_reward_risk") or 0)
    expect_rr = float(design.get("min_reward_risk") or 0.55)
    checks.append(("min_reward_risk", 100.0 if _near(min_rr, expect_rr, 0.05) else 50.0, 5))

    hi_edge = bool(cohort.get("require_high_edge"))
    strong_cex = bool(cohort.get("require_strong_cex"))
    cohort_relaxed = not hi_edge and not strong_cex
    checks.append(("cohort_relaxed", 100.0 if cohort_relaxed else 40.0, 10))

    tv_gates_off = not any(
        (tv.get(k) or {}).get("enabled")
        for k in ("signal_gate", "mtf_gate", "context_gate", "down_bias_gate")
    )
    checks.append(("tv_trade_gates_off", 100.0 if tv_gates_off else 0.0, 20))

    total, breakdown = _weighted(checks)
    return total, breakdown


def score_trade_pipeline(status: dict, light: dict) -> tuple[float, dict]:
    recon = light.get("reconciliation") or status.get("reconciliation") or {}
    lc = light.get("candidate_lifecycle") or status.get("decision_lifecycle") or {}
    eg = light.get("execution_gate") or status.get("execution_gate") or {}
    stops = light.get("stop_conditions") or status.get("stop_conditions") or {}

    global_ok = bool(light.get("global_reconciled") or recon.get("global_reconciled"))
    integrity_score = 100.0 if global_ok else 0.0

    lc_ok = bool(lc.get("reconciled", True) and lc.get("no_candidate_disappeared", True))
    lifecycle_score = 100.0 if lc_ok else 20.0

    eg_ok = bool(eg.get("reconciled", True))
    gate_score = 100.0 if eg_ok else 30.0

    failed = recon.get("failed_checks") or []
    checks_score = 100.0 if not failed else 0.0

    halted = bool(
        stops.get("any_halted")
        or (stops.get("strategies") or {}).get("directional", {}).get("halted")
    )
    halt_score = 0.0 if halted else 100.0

    ticks = int(status.get("ticks") or 0)
    uptime_score = _clamp(ticks * 0.5) if ticks < 200 else 100.0

    total, breakdown = _weighted([
        ("accounting_integrity", integrity_score, 25),
        ("lifecycle", lifecycle_score, 20),
        ("execution_gate", gate_score, 20),
        ("recon_checks", checks_score, 15),
        ("not_halted", halt_score, 10),
        ("uptime_ticks", uptime_score, 10),
    ])
    return total, breakdown


def score_gate_coupling(status: dict, light: dict) -> tuple[float, dict]:
    lc = light.get("candidate_lifecycle") or status.get("decision_lifecycle") or {}
    eg = light.get("execution_gate") or status.get("execution_gate") or {}
    cohort = status.get("baseline_cohort_gate") or {}

    created = max(int(lc.get("created") or 0), 1)
    accepted = int((lc.get("terminals") or {}).get("accepted") or 0)
    funnel_score = _clamp(30.0 + (accepted / created) * 5000.0)

    sent = int((light.get("reconciliation") or {}).get("counts", {}).get("sent_to_execution_gate") or 0)
    exec_accepted = int(eg.get("accepted") or 0)
    if sent > 0:
        pass_rate = exec_accepted / sent
        exec_score = _clamp(40.0 + pass_rate * 120.0)
    else:
        exec_score = 30.0

    rbs = lc.get("rejected_by_stage") or {}
    top_share = 0.0
    if rbs:
        total_rej = sum(rbs.values()) or 1
        top_share = max(rbs.values()) / total_rej
    diversity_score = _clamp(100.0 - top_share * 40.0)

    cohort_blocks = int(cohort.get("blocked") or 0)
    session_score = _clamp(100.0 - min(cohort_blocks, 50) * 1.5)

    ev = status.get("recent_evaluations") or []
    if ev:
        reasons = [e.get("terminal_reason") or "unknown" for e in ev]
        dominant = max(set(reasons), key=reasons.count)
        dom_frac = reasons.count(dominant) / len(reasons)
        eval_score = _clamp(100.0 - dom_frac * 50.0)
    else:
        eval_score = 50.0

    total, breakdown = _weighted([
        ("lifecycle_funnel", funnel_score, 25),
        ("exec_pass_rate", exec_score, 25),
        ("reject_diversity", diversity_score, 20),
        ("cohort_session_load", session_score, 15),
        ("recent_eval_spread", eval_score, 15),
    ])
    return total, breakdown


def score_technical_runtime(
    status: dict,
    light: dict,
    manifest: dict,
) -> dict:
    rtds_s, rtds_b = score_rtds_health(status)
    tv_s, tv_b = score_tv_intake(status, light)
    design_s, design_b = score_design_compliance(status, manifest)
    pipe_s, pipe_b = score_trade_pipeline(status, light)
    gate_s, gate_b = score_gate_coupling(status, light)

    total, breakdown = _weighted([
        ("rtds_health", rtds_s, 20),
        ("tv_intake", tv_s, 20),
        ("design_compliance", design_s, 25),
        ("trade_pipeline", pipe_s, 20),
        ("gate_coupling", gate_s, 15),
    ])
    return {
        "score": total,
        "grade": _grade(total),
        "components": breakdown,
        "subscores": {
            "rtds_health": {"score": rtds_s, "components": rtds_b},
            "tv_intake": {"score": tv_s, "components": tv_b},
            "design_compliance": {"score": design_s, "components": design_b},
            "trade_pipeline": {"score": pipe_s, "components": pipe_b},
            "gate_coupling": {"score": gate_s, "components": gate_b},
        },
        "note": "RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling.",
    }


def build_report_scores(light: dict, status: dict, ledger: dict) -> dict:
    if light.get("scores"):
        return light["scores"]
    sections = light.get("sections") or build_report_sections(light, status=status, ledger=ledger)
    return compute_report_scores(
        sections,
        global_reconciled=bool(light.get("global_reconciled")),
    )


def build_grades(
    *,
    status: dict,
    light: dict,
    ledger: dict,
    manifest: dict,
    score_history: dict | None = None,
    repo_sha: str | None = None,
) -> dict:
    report_scores = build_report_scores(light, status, ledger)
    technical = score_technical_runtime(status, light, manifest)

    report_overall = float((report_scores.get("overall") or {}).get("score") or 0.0)
    tech_score = float(technical["score"])
    composite = round(report_overall * 0.70 + tech_score * 0.30, 1)

    settled = int((light.get("ledger") or status.get("ledger") or {}).get("settled") or 0)
    ticks = int(status.get("ticks") or 0)

    hist_tail: list[dict] = []
    if score_history:
        for e in (score_history.get("entries") or [])[-5:]:
            sc = e.get("scores") or {}
            hist_tail.append({
                "utc": e.get("utc"),
                "settled": e.get("settled"),
                "overall": sc.get("overall"),
                "trading_performance": sc.get("trading_performance"),
                "operation": sc.get("operation"),
                "external_signals": sc.get("external_signals"),
            })

    return {
        "schema": "technical_grades/1.0",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "repo_sha": repo_sha,
        "ticks": ticks,
        "settled": settled,
        "report_scores": report_scores,
        "technical_runtime": technical,
        "composite": {
            "score": composite,
            "grade": _grade(composite),
            "weights": {"report_overall": 0.70, "technical_runtime": 0.30},
        },
        "vps_score_history_tail": hist_tail,
    }


def _fmt_component_table(components: dict) -> list[str]:
    lines = ["| Component | Score | Weight |", "|-----------|------:|-------:|"]
    for name, info in (components or {}).items():
        lines.append(
            f"| {name} | {info.get('score', '?')} | {info.get('weight', '?')} |"
        )
    return lines


def render_markdown(grades: dict) -> str:
    rs = grades.get("report_scores") or {}
    tr = grades.get("technical_runtime") or {}
    comp = grades.get("composite") or {}
    lines = [
        "# Technical Data Grades",
        "",
        f"**Generated:** {grades.get('ts_utc', '?')}  ",
        f"**Repo SHA:** `{grades.get('repo_sha') or '?'}`  ",
        f"**Ticks:** {grades.get('ticks', '?')} | **Settled:** {grades.get('settled', '?')}",
        "",
        "## Composite",
        "",
        f"| Metric | Score | Grade |",
        f"|--------|------:|-------|",
        f"| **Composite** | **{comp.get('score', '?')}** | **{comp.get('grade', '?')}** |",
        f"| Report overall | {(rs.get('overall') or {}).get('score', '?')} | {(rs.get('overall') or {}).get('grade', '?')} |",
        f"| Technical runtime | {tr.get('score', '?')} | {tr.get('grade', '?')} |",
        "",
        "## Report scores (engine)",
        "",
        f"| Section | Score | Grade |",
        f"|---------|------:|-------|",
    ]
    for key in ("trading_performance", "operation", "external_signals"):
        sec = rs.get(key) or {}
        lines.append(f"| {key.replace('_', ' ').title()} | {sec.get('score', '?')} | {sec.get('grade', '?')} |")

    lines.extend(["", "## Technical runtime", "", f"_{tr.get('note', '')}_", ""])
    lines.extend(_fmt_component_table(tr.get("components")))

    for sub_name, sub in (tr.get("subscores") or {}).items():
        lines.extend([
            "",
            f"### {sub_name.replace('_', ' ').title()} ({sub.get('score', '?')})",
            "",
        ])
        lines.extend(_fmt_component_table(sub.get("components")))

    tail = grades.get("vps_score_history_tail") or []
    if tail:
        lines.extend([
            "",
            "## VPS score history (last entries)",
            "",
            "| UTC | Settled | Overall | Trading | Operation | External |",
            "|-----|--------:|--------:|--------:|----------:|---------:|",
        ])
        for row in tail:
            lines.append(
                f"| {row.get('utc', '?')} | {row.get('settled', '?')} | "
                f"{row.get('overall', '?')} | {row.get('trading_performance', '?')} | "
                f"{row.get('operation', '?')} | {row.get('external_signals', '?')} |"
            )

    lines.append("")
    return "\n".join(lines)


def _history_compact(grades: dict) -> dict:
    rs = grades.get("report_scores") or {}
    tr = grades.get("technical_runtime") or {}
    comp = grades.get("composite") or {}
    return {
        "ts_utc": grades.get("ts_utc"),
        "repo_sha": grades.get("repo_sha"),
        "ticks": grades.get("ticks"),
        "settled": grades.get("settled"),
        "composite": comp.get("score"),
        "composite_grade": comp.get("grade"),
        "report_overall": (rs.get("overall") or {}).get("score"),
        "technical_runtime": tr.get("score"),
        "trading_performance": (rs.get("trading_performance") or {}).get("score"),
        "operation": (rs.get("operation") or {}).get("score"),
        "external_signals": (rs.get("external_signals") or {}).get("score"),
        "grades": {
            "composite": comp.get("grade"),
            "report_overall": (rs.get("overall") or {}).get("grade"),
            "technical_runtime": tr.get("grade"),
            "trading_performance": (rs.get("trading_performance") or {}).get("grade"),
            "operation": (rs.get("operation") or {}).get("grade"),
            "external_signals": (rs.get("external_signals") or {}).get("grade"),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Grade technical data from VPS artifacts")
    ap.add_argument("--latest-dir", type=Path, default=LATEST)
    ap.add_argument("--monitor-dir", type=Path, default=MONITOR)
    args = ap.parse_args()

    latest = args.latest_dir
    monitor = args.monitor_dir
    monitor.mkdir(parents=True, exist_ok=True)

    status = _load_json(latest / "btc_pulse_status.json")
    light = _load_json(latest / "btc_pulse_light_report.json")
    ledger = _load_json(latest / "btc_pulse_ledger.json")
    manifest = _load_json(MANIFEST)
    score_history = _load_json(latest / "btc_pulse_score_history.json")

    if not status and not light:
        print("No status or light report in latest dir", file=sys.stderr)
        return 1

    grades = build_grades(
        status=status,
        light=light,
        ledger=ledger,
        manifest=manifest,
        score_history=score_history or None,
        repo_sha=_git_sha(),
    )

    grades_path = monitor / "technical-grades.json"
    history_path = monitor / "grades-history.jsonl"
    md_path = monitor / "TECHNICAL_GRADES.md"

    grades_path.write_text(json.dumps(grades, indent=2, default=str) + "\n", encoding="utf-8")
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(_history_compact(grades), default=str) + "\n")
    md_path.write_text(render_markdown(grades), encoding="utf-8")

    comp = grades["composite"]
    print(
        f"grades composite={comp['score']} ({comp['grade']}) "
        f"tech_runtime={grades['technical_runtime']['score']} "
        f"report={grades['report_scores']['overall']['score']} "
        f"-> {grades_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
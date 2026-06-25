#!/usr/bin/env python3
"""Merge HIGH WIN RATE pulse env vars into hermes-trading-engine/.env"""
from pathlib import Path

ENV_PATH = Path("/opt/Grok-Bot-2/hermes-agent-main/plugins/hermes-trading-engine/.env")

UPDATES = {
    "PULSE_TV_FEATURE_SYMBOL": "BTCUSDT",
    "PULSE_TRADINGVIEW_SIGNAL_GATE": "1",
    "PULSE_TV_MIN_SIGNAL_STRENGTH": "0.72",
    "PULSE_TV_SIGNAL_MAX_FEATURE_AGE_S": "300",
    "PULSE_TV_CONTEXT_GATE": "1",
    "PULSE_TV_CONTEXT_MAX_TTC_S": "120",
    "PULSE_TV_CONTEXT_EXPLORATION_RATE": "0",
    "PULSE_TV_DOWN_BIAS_GATE": "1",
    "PULSE_TV_DOWN_BIAS_EXPLORE_RATE": "0",
    "PULSE_TV_MTF_CONFLICT_GATE": "1",
    "PULSE_TV_MTF_REQUIRE_CONFIRM": "1",
    "PULSE_TV_MTF_REQUIRE_SIDE_ALIGN": "1",
    "PULSE_TV_MTF_CONFLICT_EXPLORE_RATE": "0",
    "PULSE_LATE_WINDOW_ENTRY": "1",
    "PULSE_LATE_WINDOW_MAX_TTC_S": "120",
    "PULSE_LATE_WINDOW_MIN_CONVICTION": "0.45",
    "PULSE_MIN_REWARD_RISK": "0.40",
    "PULSE_SELECTIVITY_MIN_WIN_RATE": "0.58",
    "PULSE_SELECTIVITY_EXPLORATION_RATE": "0",
    "PULSE_DIRECTIONAL_EXPLORE_RATE": "0",
    "PULSE_CEX_LEAD_TV_STRENGTH_THR": "0.72",
}

text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
lines = [ln for ln in text.splitlines() if not ln.strip().startswith("# HIGH WIN RATE")]
seen = set()
out = []
remaining = dict(UPDATES)
for ln in lines:
    if "=" in ln and not ln.lstrip().startswith("#"):
        key = ln.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
            seen.add(key)
        elif key not in seen:
            out.append(ln)
            seen.add(key)
    elif ln.strip():
        out.append(ln)
for key, val in remaining.items():
    out.append(f"{key}={val}")
out.append("# HIGH WIN RATE profile (2026-06-25)")
ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Wrote {ENV_PATH} ({len(UPDATES)} profile keys)")
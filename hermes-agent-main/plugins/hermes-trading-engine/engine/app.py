"""Slim read-only API for the BTC 5-minute pulse PAPER engine.

After the focused redesign, the only HTTP surface is health + read-only pulse status/ledger
(served from the JSON the pulse engine writes to ``HTE_DATA_DIR``). There is no trading,
mode, or live-execution endpoint — this engine is PAPER ONLY and the loop runs in the
separate ``scripts/run_btc_pulse.py`` process.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Hermes BTC 5-min Pulse (paper)", version="2.0")


def _data_dir() -> Path:
    return Path(os.environ.get("HTE_DATA_DIR", "/data"))


def _read_json(name: str) -> "dict | None":
    path = _data_dir() / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


@app.get("/api/health")
def health() -> dict:
    """Liveness + freshness of the pulse engine (status JSON written every tick)."""
    st = _read_json("btc_pulse_status.json")
    fresh = False
    age = None
    p = _data_dir() / "btc_pulse_status.json"
    if p.exists():
        age = round(time.time() - p.stat().st_mtime, 1)
        fresh = age < 120
    return {"status": "ok", "paper_only": True, "live_trading_enabled": False,
            "pulse_status_fresh": fresh, "pulse_status_age_s": age,
            "ticks": (st or {}).get("ticks")}


@app.get("/api/polymarket/training/btc_pulse")
def btc_pulse_status() -> dict:
    """BTC 5-min pulse engine status: price/vol health, paper ledger, calibration, gating."""
    st = _read_json("btc_pulse_status.json")
    if not st:
        return {"available": False,
                "reason": "pulse engine has not written status yet — start run_btc_pulse.py"}
    return {"available": True, **st}


@app.get("/api/polymarket/training/btc_pulse/ledger")
def btc_pulse_ledger() -> dict:
    """BTC 5-min pulse PAPER ledger: paper positions + realized P&L."""
    led = _read_json("btc_pulse_ledger.json")
    if not led:
        return {"available": False, "reason": "no pulse ledger yet."}
    return {"available": True, **led}


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse({"engine": "btc-5min-pulse", "paper_only": True,
                         "endpoints": ["/api/health", "/api/polymarket/training/btc_pulse",
                                       "/api/polymarket/training/btc_pulse/ledger"]})

"""Runtime control plane for paper subsystems (PAPER ONLY, cross-process).

The dashboard and the training loop run in separate processes that share the
data dir. This module is the single source of truth for per-subsystem on/off/auto
overrides: the dashboard writes ``control_overrides.json`` and the training loop
reads + applies it each tick. Turning a subsystem **off** is always honored
(strictly more restrictive); turning **on** only ever (re)enables a PAPER /
advisory subsystem — it can never enable live trading, wallet access, or real
order submission.

Quant scope — *Monitoring / Ops*: gives an operator a safe, auditable kill/enable
switch for each paper subsystem without editing config or restarting (where the
subsystem supports a live toggle).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hte.control")

CONTROL_FILENAME = "control_overrides.json"
VALID_STATES = ("on", "off", "auto")

# key -> metadata. ``config_flag`` is the engine.config attribute that gates the
# subsystem at trainer construction (None when controlled another way).
# ``live`` describes how a toggle takes effect: "pulse_freeze" (loop freezes the
# isolated pulse live), "grok" (engine brain toggle), "start_stop" (training
# start/stop sentinels), or "restart" (applied on the next training start).
CONTROLLABLE: dict = {
    "polymarket": {"label": "Polymarket paper training", "config_flag": None,
                   "live": "start_stop"},
    "btc_pulse": {"label": "BTC 5-min Pulse", "config_flag": "btc_pulse_enabled",
                  "live": "pulse_freeze"},
    "news": {"label": "News scanner", "config_flag": "news_scanner_enabled",
             "live": "restart"},
    "chainlink": {"label": "Chainlink oracle", "config_flag": "chainlink_enabled",
                  "live": "restart"},
    "btc_fast_price": {"label": "BTC fast price feed",
                       "config_flag": "btc_fast_price_enabled", "live": "restart"},
    "grok": {"label": "Grok research (advisory)", "config_flag": None, "live": "grok"},
    "feedback_accelerator": {"label": "Feedback accelerator",
                             "config_flag": "feedback_accelerator_enabled",
                             "live": "restart"},
    "clob": {"label": "Polymarket CLOB feed", "config_flag": None, "live": "restart"},
}


def overrides_path(data_dir) -> Path:
    return Path(data_dir) / CONTROL_FILENAME


def read_overrides(data_dir) -> dict:
    """Return ``{key: "on"|"off"}`` overrides (``auto`` keys are omitted). Pure,
    defensive: a missing/corrupt file yields ``{}``."""
    try:
        p = overrides_path(data_dir)
        if not p.exists():
            return {}
        raw = json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 — control must never crash a caller
        logger.debug("read_overrides failed: %s", exc)
        return {}
    out: dict = {}
    for k, v in (raw.get("overrides", raw) or {}).items():
        if k in CONTROLLABLE and str(v).lower() in ("on", "off"):
            out[k] = str(v).lower()
    return out


def write_override(data_dir, key: str, state: str) -> dict:
    """Set ``key`` to ``on``/``off``/``auto`` and persist; return the new map.

    ``auto`` removes any override (fall back to config/env). Raises ``ValueError``
    on an unknown key or invalid state. Never writes a live-execution flag.
    """
    if key not in CONTROLLABLE:
        raise ValueError(f"unknown control key: {key}")
    state = str(state).lower()
    if state not in VALID_STATES:
        raise ValueError(f"invalid state: {state}")
    current = read_overrides(data_dir)
    if state == "auto":
        current.pop(key, None)
    else:
        current[key] = state
    p = overrides_path(data_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"overrides": current}, indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("write_override failed: %s", exc)
    logger.info("control override set: %s=%s", key, state)
    return current


def effective_state(key: str, *, default_on: bool, overrides: dict) -> bool:
    """Resolve a subsystem's effective on/off given config default + overrides."""
    ov = (overrides or {}).get(key)
    if ov == "on":
        return True
    if ov == "off":
        return False
    return bool(default_on)


def apply_to_config(cfg, overrides: dict) -> list:
    """Apply on/off overrides to a config object's paper flags (mutating).

    Only ever flips a known paper ``config_flag``; returns the list of
    ``(flag, value)`` applied. Used at training startup so toggles persist across
    restarts. Never touches live/wallet/order flags."""
    applied: list = []
    for key, state in (overrides or {}).items():
        meta = CONTROLLABLE.get(key)
        if not meta or not meta.get("config_flag"):
            continue
        if state not in ("on", "off"):
            continue
        flag = meta["config_flag"]
        value = (state == "on")
        try:
            setattr(cfg, flag, value)
            applied.append((flag, value))
        except Exception as exc:  # noqa: BLE001
            logger.debug("apply_to_config %s failed: %s", flag, exc)
    return applied


def apply_runtime(trainer, overrides: dict) -> dict:
    """Apply overrides to a LIVE trainer each tick (best-effort, paper-only).

    Currently the BTC 5-min Pulse supports a live toggle: ``off`` freezes the
    isolated pulse immediately; ``on`` unfreezes it when it was constructed at
    startup and still passes its fail-closed safety check. Other subsystems are
    applied on the next training start (see :func:`apply_to_config`). Returns a
    small summary of what was toggled. Never enables a live path.
    """
    summary: dict = {}
    pulse = getattr(trainer, "btc_pulse", None)
    st = (overrides or {}).get("btc_pulse")
    if pulse is not None and st in ("on", "off"):
        if st == "off":
            pulse.frozen = True
            summary["btc_pulse"] = "frozen"
        elif bool(getattr(pulse, "enabled_flag", False)) and \
                bool(getattr(pulse, "safety", {}).get("passed", False)):
            pulse.frozen = False
            summary["btc_pulse"] = "unfrozen"
        else:
            summary["btc_pulse"] = "cannot_unfreeze(not_enabled_or_unsafe)"
    return summary

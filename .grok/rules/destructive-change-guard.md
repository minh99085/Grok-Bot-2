# Destructive change guard

Before executing any request to delete, remove, disable, or strip code/config that affects the
bot's trading or safety behavior, understand the blast radius first. For operator-initiated
destructive work in the current message, proceed; otherwise pause and confirm.

## High-risk triggers (understand impact before editing)

- Removing or weakening `engine/robinhood/safety_gates.py`, `client.py`, or the audit log
- Changing `RH_LIVE_TRADING_ENABLED`, notional/loss/PDT/concentration caps, or `RH_APPROVAL_MODE`
- Disabling the OAuth token storage or MCP reconnect loop
- Deleting or bypassing `SafeRobinhoodClient` on any order path
- Large refactors of the agent loop (`scripts/run_robinhood_agent.py`) or MCP adapter

## Before high-risk edits, state

1. **What** changes (files + runtime effect)
2. **Risk** to real capital, safety gates, or connectivity
3. **What stays** protected (live kill switch, gates, audit log)
4. **Deploy impact** — does the VPS need a rebuild?

## Safe to proceed without pause

- Read-only scans, docs, and refactors that keep all safety gates intact
- Changes the operator explicitly asked for in the current message ("remove X", "do it", etc.)
- Reverting a change the operator asked to undo in the same session

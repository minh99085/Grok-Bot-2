# Destructive change guard (operator mandate — 2026-06-28)

**Before executing** any user prompt to delete, remove, disable, or strip code/env that affects live bot behavior, **stop and tell the operator first**. Do not commit, push, or deploy until they confirm.

## Triggers (always pause + explain)

- Remove or delete engine modules (decider, gates, arb, feeds, loops)
- Disable Grok/verifier/TV/trading paths or env authority keys
- Change `frozen-env-keys.json`, `apply-loop-arch-env.py`, or gate defaults
- Large refactors that touch `engine/pulse/engine.py` money path
- `sync-vps` / deploy during `hands_off` unless operator explicitly overrides hands-off for that change

## Required response (before any edits)

1. **What** will be removed/changed (files + runtime effect)
2. **Risk** to trading, PnL, soak baseline, or VPS state
3. **What stays** untouched (arb, dep-arb, gates, paper-only, etc.)
4. **Deploy impact** — will VPS need rebuild? Is hands-off active?
5. **Ask:** "Proceed with this removal?" — wait for explicit yes

## Safe to proceed without full pause

- Read-only scans, dashboard-only display, docs the operator asked for
- Reverting a change the operator explicitly asked to undo in the same session
- Operator says "yes proceed", "do it", "execute", or confirms after the warning

## Example (Grok decider removal)

Operator: "remove Grok decider" → **Do not delete yet.** Reply: decider is removed from trading path but Analyst/Predictor stay; stops per-window Grok API calls; commit `f72d6e3` not on VPS until deploy; confirm before push/deploy.
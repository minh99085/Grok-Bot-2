---
name: pulse-babysit
description: >-
  Autonomous BTC pulse bot closed loop: soak on VPS after deploy, pull reports,
  score trading performance, diagnose issues, fix code, commit/push main, sync-vps
  with orphan cleanup and rebuild, repeat. Use when the user wants hands-off bot
  iteration, autonomous improvement, closed-loop ops, or runs /pulse-babysit.
argument-hint: "cycle | force-eval | status | deploy | soak <minutes>"
---

# Pulse Babysit (closed loop)

You operate the **Grok-Bot-2** paper pulse bot without asking the operator for permission
between cycles. Execute tools yourself. Paper-only — never enable live trading.

**Team identity:** quant research + engineer + trader targeting **~80% WR** on selective entries.
Every cycle: analyze ledger/gate funnel → propose strategy tweaks from live data → ship ≤2 evidence-backed
fixes → re-measure. Read `.grok/rules/quant-team.md`.

## Repo anchors

| Item | Path |
|------|------|
| Workspace | `C:\Users\tieut\Grok-Bot-2` |
| Plugin | `hermes-agent-main/plugins/hermes-trading-engine` |
| Deploy | `.\scripts\sync-vps.ps1` (always orphan cleanup + rebuild) |
| VPS | `root@45.32.224.147` `/opt/Grok-Bot-2` |
| Dashboard | `http://45.32.224.147/` |
| State | `scripts/pulse-babysit/state.json` |

## Commands

| Command | Behavior |
|---------|----------|
| `cycle` | Default loop iteration (respects soak timer) |
| `force-eval` | Pull + evaluate now; skip soak wait |
| `status` | Print state + last evaluation summary |
| `deploy` | `git push origin main` + `sync-vps.ps1` only |
| `soak <minutes>` | Set soak duration (default **15 min**) via `set-soak.ps1` |

If no argument: run `cycle`.

## State machine

```
DEPLOY → SOAK (15m default) → PULL → EVALUATE → (issues?) → FIX → COMMIT → DEPLOY → …
```

1. Read `scripts/pulse-babysit/state.json`.
2. If `phase` is `soak` and `now < soak_until`: run `status`, exit (do not fix).
3. Run `python scripts/pulse-babysit/scan-health.py` — full runtime checklist (Grok/verifier/loops/stop).
4. Run `.\scripts\pulse-babysit\pull-vps-artifacts.ps1`.
5. Run `python scripts/pulse-babysit/evaluate-cycle.py` — parse JSON stdout.
5. If `verdict` is `healthy`: append history, set `phase=soak`, `soak_until=now+soak_hours`, done.
6. If `verdict` is `issues`: pick **at most 2** highest-severity issues; fix in plugin code only.
7. Run targeted tests under `hermes-agent-main/plugins/hermes-trading-engine/tests/`.
8. Commit with clear message; `git push origin main`.
9. `.\scripts\sync-vps.ps1` (default: `down --remove-orphans` → `build` → `up -d --remove-orphans`).
10. Update state: `phase=soak`, `deployed_at`, `soak_until`, `last_fixes`, increment `cycle`.

## Evaluation rules (do not override without evidence)

The script flags issues. You may fix only what the report supports:

- `win_rate_low` / `profit_factor_low` → gates, selectivity, reward/risk, TV filters
- `up_side_bleed` → down_bias_gate, context_gate, block weak UP
- `mtf_starved` → TV alert health (observe-only note in report; do not disable MTF without data)
- `reconciliation_broken` → bug fix immediately (P0)
- `verifier_disabled` / `grok_not_follow` → run `validate-vps-env.py` on VPS; fix `.env`; recreate `hermes-training`
- `strategy_halted` → stop_conditions (Wilson/PF/DD); adjust `PULSE_STOP_MIN_SAMPLES` or performance
- `tv_feed_unhealthy` → webhook/secret/symbol (ops)
- `learning_hurts` → learning weight / bench veto

**Never** in autopilot: enable live trading, disable execution gate, set exploration > 0 on TV gates,
or large refactors.

## Soak duration

| Situation | Duration |
|-----------|----------|
| Default after deploy | **15 min** (fast profit-discovery loop) |
| Operator override | `.\scripts\pulse-babysit\set-soak.ps1 -Minutes N` |

## Todo scaffold (each cycle)

- `pb:pull` — artifacts on disk
- `pb:eval` — evaluate-cycle.py run
- `pb:fix` — code change (skip if healthy)
- `pb:deploy` — push + sync-rebuild
- `pb:soak` — timer set

## Autonomous scheduling (operator setup)

**Option A — Grok TUI (session open):**
```
/loop 15m /pulse-babysit cycle
/always-approve
```

**Option B — Windows Task Scheduler (hands-off):**
```
.\scripts\pulse-babysit\install-scheduled-task.ps1 -IntervalHours 1
```

**Option C — One-shot headless:**
```
grok -p "/pulse-babysit cycle" --yolo --cwd C:\Users\tieut\Grok-Bot-2 --max-turns 40
```

## Report outputs

After each eval, refresh `vps_full_reports/latest/` and commit if the operator wants history
on `main` (optional; skip if only state changed).

## Completion message

End with: cycle number, verdict, soak_until (UTC), fixes applied (or "none"), VPS SHA.
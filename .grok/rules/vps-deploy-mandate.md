# VPS deploy mandate (OPERATOR MEMORY — 2026-07-02, reaffirmed 2026-07-02)

**Operator memory (verbatim):** always push to `main` and VPS, then remove orphans and rebuild the container.

**Non-negotiable on every completed change:** push to `main`, sync the VPS, remove orphans, rebuild.

Do not tell the operator to run deploy — **execute it yourself** before calling any task done.

## Standard sequence (every push to `main`)

1. `git push origin main`
2. `.\scripts\sync-vps.ps1` from repo root (**default** — includes full rebuild)
   - Git bundle sync → `/opt/Grok-Bot-2`
   - `docker compose down --remove-orphans`
   - `docker compose build` (both Polymarket images — no service arg)
   - `docker compose up -d --force-recreate --remove-orphans`
3. If env/gate keys changed: `python3 scripts/apply-loop-arch-env.py` on VPS
4. If loop env changed: `docker compose up -d --force-recreate hermes-training` in pulse plugin dir
5. If Robinhood plugin changed: `.\scripts\sync-vps-robinhood.ps1` (same orphan cleanup + rebuild pattern)
6. `.\scripts\verify-sync.ps1` — VPS HEAD SHA must equal `origin/main`

## Never

- Push to `main` and stop without VPS sync
- Use `-SkipRebuild` unless the operator explicitly requests code-only sync in the current message
- `docker compose restart` or hot-swap a single service without `down --remove-orphans` → `build` → `up -d --remove-orphans`

## VPS access

- Host: `45.32.224.147`, user: `root`, key: `$env:USERPROFILE\.ssh\bot2_grok_temp`
- Repo: `/opt/Grok-Bot-2`
- Polymarket compose: `.../plugins/hermes-trading-engine`
- Robinhood compose: `.../plugins/hermes-trading-engine-robinhood` (profile `robinhood`)
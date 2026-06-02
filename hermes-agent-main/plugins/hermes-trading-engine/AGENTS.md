# Hermes Trading Engine — agent guide

Instructions for AI agents working in this plugin.

## User preference (ALWAYS follow)

**At the end of every task, give simple copy‑paste instructions to start the
system** — short, runnable commands, no long prose. The user runs this on
Windows + Docker Desktop and wants the same easy "how to start it" block each
time (just like prior sessions). Lead with the start commands; keep
explanation minimal.

## Easy start (paste this)

Run from `plugins/hermes-trading-engine`:

```bash
docker compose up -d --build      # build + start (first time / after code changes)
# then open the dashboard:
#   http://localhost:8800
```

Day-to-day:

```bash
docker compose up -d              # start (no rebuild needed)
docker compose stop               # pause (keep containers)
docker compose start              # resume after a stop
docker compose down               # remove containers (data kept in the hte_data volume)
docker compose logs -f hermes-trading-engine   # watch logs
```

Rule of thumb: `stop`↔`start` = pause/resume; `up`↔`down` = create/remove.
After a `down`, always come back with `up` (not `start`).

## What runs

- `hermes-trading-engine` — paper dashboard + API on **:8800** (the core).
- `hermes-training` — Polymarket PAPER training loop (scan → rank → edge → learn).

PAPER ONLY: no real orders. Grok is research-only. Optional: put
`GROK_API_KEY` (or `XAI_API_KEY`) in `.env` to enable the Grok research layer.

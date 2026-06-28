# Hands-off — untouchable while bot is profitable (operator lock)

**Locked:** 2026-06-28. Operator directive after healthy deep scan: bot running and trading well.
**Do NOT change** these without explicit operator approval. Babysit autopilot must not "fix" these.

Read before any env, gate, deploy, or babysit cycle that alters behavior.

## Money path (untouchable)

- Paper-only mode (`live_trading_enabled` must stay OFF)
- Arb scanner + dep-arb execute (primary profit engines)
- `PULSE_TICK_SECONDS=15` (fast tick for arb — never 60s)
- Chainlink RTDS price feed + vol sampler
- CLOB websocket enabled

## Grok observe-only (untouchable — no trade decider)

- Grok trade decider **removed** — quant baseline + arb own all trade decisions
- `GROK_BUDGET_DAILY_USD=35`
- `GROK_PREDICTOR_MAX_CALLS_PER_HOUR=60`
- `GROK_ANALYST_MAX_CALLS_PER_HOUR=4`
- `PULSE_GROK_NEWS_REFRESH_S=300` (CEX-lead context only)
- `PULSE_RESEARCH_LOOP_ENABLED=1` with `PULSE_RESEARCH_AUTO_APPLY=0`
- `PULSE_VERIFIER_ENABLED=1`

## TradingView (untouchable — observe-only lock)

- TV trade gates OFF: signal, MTF require, context, baseline-TV (see `tv-observe-only-lock.md`)
- MTF timeframes **2m / 3m / 4m only** (no 5m/10m/15m charts)
- `PULSE_TV_FEATURE_SYMBOL=BTCUSD`
- Webhook secret on VPS — do not rotate without updating TV alerts

## Directional / gates (untouchable — do not loosen OR tighten)

- `PULSE_BASELINE_COHORT_GATE_ENABLED=1` + 15m fast-lane TTC band
- `PULSE_DIRECTIONAL_DOWN_ONLY=1`
- `PULSE_GREEN_PATH_ENABLED=1`
- `PULSE_DIRECTIONAL_EXPLORE_RATE=0`
- Heavy gate blocking is **expected** in `learning_collection`
- Do not chase 80% WR by tightening gates while arb carries PnL

## Frozen authority (untouchable)

All keys in `scripts/pulse-babysit/frozen-env-keys.json` → `authority_frozen` and `learning_collection_frozen`.

## Never do in autopilot / babysit

1. Re-enable Grok trade decider or follow mode
2. Re-enable any TV trade gate
3. `sync-vps` / deploy without operator ask during hands-off window
4. Relax or tighten quant gates on WR/PF alone while bot is profitable
5. Enable live trading
6. Raise Grok budget above $35 without evidence of starvation
7. `PULSE_RESEARCH_AUTO_APPLY=1`

## Watch only (do not "fix")


- `missing_secret` TV rejects (stray POSTs)
- Readiness `not_ready` for 80% promotion
- Directional PF ~1.0 on small sample

## Winning formula (one line)

Fast tick + arb ON + dep-arb ON + Grok observe-only (A/B/news) + TV observe-only + strict directional gates.
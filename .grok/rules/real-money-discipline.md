# Real-money discipline (operator ON — 2026-06-28)

Paper ledger is treated as **real capital**. Optimize PnL, win rate, and drawdown — not “collect more trades.”

## Goals (state.json)

| Field | Value |
|-------|--------|
| `goals.mode` | `real_money_discipline` |
| `goals.priority` | `pnl_protection_and_win_rate` |
| `goals.win_rate_target_deferred` | **false** |
| `soak_minutes` | **60** (1h between deploys — not 4h) |

## Runtime (engine — less conservative adjust)

| Knob | Discipline value | Why |
|------|------------------|-----|
| `PULSE_RESEARCH_AUTO_APPLY` | 1 | Block proven losers, promote proven winners |
| `PULSE_SELECTIVITY_MIN_SAMPLES` | 30 | Faster evidence for auto-apply |
| `PULSE_SELECTIVITY_MIN_PROFIT_FACTOR` | 0.92 | Stricter on losing buckets |
| `PULSE_RESEARCH_INTERVAL_S` | 1200 | Research every 20 min |
| `PULSE_LEARNING_BENCH_MARGIN` | -0.02 | Allow blend when model is near market |
| `PULSE_LEARNING_MIN_SAMPLES` | 40 | Sooner learning ramp |
| `PULSE_LEARNING_RAMP_SAMPLES` | 120 | Faster weight ramp |

## Babysit — act like a trader

**Fix these (not deferred):**

- `trade_starvation` / `trade_starvation_streak` → **relax** quant gates (still no TV gates)
- `win_rate_below_target` / `profit_factor_low` → **tighten** quant gates / reward_risk
- `up_side_bleed` → strengthen DOWN-only restrictors
- `reconciliation_broken` / `strategy_halted` → fix immediately

**Priority when multiple issues:** starvation first (bot must trade), then PnL/WR tighten.

**WR auto-tune (post-starvation):** when trades flow and 24h DOWN ledger shows band bleed,
`scripts/pulse-babysit/apply-wr-tune.py --apply` patches price gates from `wr-tune-policy.json`:

| Issue | Action |
|-------|--------|
| `cheap_down_bleed` | Raise `PULSE_MIN_ENTRY_PRICE` (+0.01, cap 0.48) |
| `expensive_down_bleed` | Lower `PULSE_MAX_PRICE` (−0.02, floor 0.58) |
| `sweet_spot_underuse` | Tighten toward 0.45–0.55 band |

Floor: **never** lower `PULSE_MIN_ENTRY_PRICE` below **0.45** for starvation relief.

**Never:** Grok follow, TV trade gates, live trading, disable execution gate.

## Still paper-only

`live_trading_enabled` stays OFF until operator explicitly enables live in a dedicated message.
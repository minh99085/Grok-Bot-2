# Soak / learning collection lock (OPERATOR MANDATE)

**Locked:** 2026-06-27. While the bot is in **learning-collection mode**, agents may fine-tune
only within the tunable bounds below. Everything else is frozen so coding sessions do not break
live paper trading or corrupt the ledger/learning dataset.

**Companion files:**

| File | Role |
|------|------|
| `scripts/pulse-babysit/frozen-env-keys.json` | Machine-readable frozen/tunable manifest |
| `scripts/apply-loop-arch-env.py` | Env source of truth (must match manifest) |
| `.grok/rules/tv-observe-only-lock.md` | TV gate authority lock (subset of authority_frozen) |
| `scripts/pulse-babysit/validate-frozen-lock.py` | Pre-deploy / babysit validator |

## Mode: learning_collection

**Goal:** Keep the bot placing 15m DOWN paper trades through agent coding so we collect:

- Settled positions + PnL in `btc_pulse_ledger.json`
- Decision lifecycle / gate funnel (`rejected_by_stage`, `skipped_by_reason`)
- Grok shadow grades, verifier vetoes, TV observe-only features
- Score history and learning bench metrics

**Do not optimize for WR during this phase.** Trade rate and data continuity beat tightening.

## Authority chain (NEVER regress)

These must stay on every deploy. Violation = P0 blocked.

| Layer | Frozen behavior |
|-------|-----------------|
| Grok | `PULSE_GROK_DECIDER_MODE=shadow`, explore=0, never `affects_trading` |
| TradingView | All TV **trade gates** off — see `tv-observe-only-lock.md` |
| Green path | `PULSE_GREEN_PATH_ENABLED=1` — 15m DOWN skips opinion gates |
| Series | 15m only: `PULSE_SERIES_SLUGS=btc-up-or-down-15m` |
| Side | DOWN only: `PULSE_DIRECTIONAL_DOWN_ONLY=1` |
| Execution | Verifier on, fail-closed; execution gate reconciled |
| Paper | `live_trading_enabled=false` — never enable live |
| Open snapshots | Persist in ledger `accounting_state.open_snapshots` — do not remove |
| Reconciliation | Fix bugs immediately; never tune gates on broken ledger |

## Learning-collection frozen env (do not tighten)

These values are locked until the operator ends learning-collection mode in the **current message**.
`apply-loop-arch-env.py` must write them; babysit must not revert relaxations.

**Entry / throughput (relaxed 2026-06-27 cycle 4):**

- `PULSE_MIN_EDGE=0.015`, `PULSE_BASIS_BUFFER=0.01`
- `PULSE_MAX_OPEN_LAG_S=120`, `PULSE_MAX_OPEN_LAG_15M_S=240`
- `PULSE_TICK_SECONDS=15`, `PULSE_MAX_PRICE=0.70`
- `PULSE_MIN_REWARD_RISK=0.55`
- Baseline cohort on; `REQUIRE_HIGH_EDGE=0`, `REQUIRE_STRONG_CEX=0`
- 15m fast lane TTC 150–230 base (scaled ~450–690s)
- `PULSE_BASELINE_DOWN_BLOCK_NOT_STALE=0`, `BLOCK_BULLISH_MTF=0`
- Other baseline DOWN blocks stay as in manifest (bullish range / strong bullish still on)

**TV confidence tier (modulation only, not a gate):**

- `PULSE_TV_CONFIDENCE_TIER_ENABLED=1` with sweet-spot + 15m-only flags

## Tunable (agents MAY change — bounded)

Only these keys may change during fine-tuning, and only in the stated direction/bounds:

| Key | Allowed direction | Bounds |
|-----|-------------------|--------|
| `PULSE_MIN_EDGE` | relax only (lower) | ≥ 0.010 |
| `PULSE_BASIS_BUFFER` | relax only | ≥ 0.005 |
| `PULSE_MAX_PRICE` | relax only (higher) | ≤ 0.75 |
| `PULSE_MIN_REWARD_RISK` | relax only (lower) | ≥ 0.45 |
| `PULSE_BASELINE_COHORT_*_TTC_*` | widen band only | must keep 15m scaled overlap with sweet spot |
| `PULSE_TV_CONFIDENCE_TIER_*_DELTA` | small tweaks | see manifest |
| `PULSE_STOP_MIN_SAMPLES` | raise only | if strategy_halted blocks trading |
| `PULSE_SELECTIVITY_*` | relax only | if selectivity starves fills |

**Forbidden during learning_collection:**

- Re-enable any TV trade gate (MTF require, side-align, context, signal, baseline TV)
- Set `PULSE_GROK_DECIDER_MODE=follow` or explore > 0
- Tighten min_edge, max_price down, reward_risk up, or baseline DOWN blocks to 1
- Enable `PULSE_BASELINE_COHORT_REQUIRE_HIGH_EDGE` or `REQUIRE_STRONG_CEX`
- Disable open-snapshot persistence or shrink `PULSE_MAX_OPEN_LAG_*` below frozen floor
- Large refactors of engine tick loop, executor, or accounting without operator ask

## Frozen code paths (do not break)

| Module | Invariant |
|--------|-----------|
| `engine/pulse/price.py` | Open snapshot capture + `to_open_state()` / restore from ledger |
| `engine/pulse/engine.py` | `_persist()` writes `open_snapshots`; restore on startup |
| `engine/pulse/tv_confidence_tier.py` | Param modulation only; never hard-block |
| `engine/pulse/config_coupling.py` | Context/cohort coupling math |
| `engine/pulse/grok_decider.py` | Shadow mode; grades only |
| `engine/pulse/executor.py` | Paper ledger + reconciliation |
| `tests/test_open_snapshot_persist.py` | Must pass before deploy |

## Babysit / soak rules

1. **Soak default:** 120 min during learning_collection (not 60). Use `set-soak.ps1 -Minutes 120`.
2. **During soak:** no fixes, no deploy — only `status` / pull artifacts.
3. **On `trade_starvation`:** relax tunable quant keys only; never TV gates or WR tighten.
4. **On `win_rate_below_target` / `profit_factor_low`:** ignore if starvation present or
   `settled_flat_eval_streak >= 2`.
5. **Deploy discipline:** every push rebuilds container → mid-window restart. Batch fixes;
   prefer ≤2 changes per cycle. Run `validate-frozen-lock.py` after `apply-loop-arch-env.py`.
6. **Post-deploy:** wait full 15m window + soak before evaluating trade rate.

## Verification checklist

```bash
python scripts/pulse-babysit/validate-frozen-lock.py
python scripts/pulse-babysit/validate-vps-env.py   # on VPS via ssh
python scripts/pulse-babysit/scan-health.py
```

Status API must show:

- `grok_decider.mode` = shadow, `affects_trading` = false
- `tradingview.mtf_gate.enabled` = false (or require_confirm false)
- `config.grok_decider_mode` = shadow
- `decision_lifecycle.reconciled` = true
- `price.tracked_opens` > 0 after first window post-restart

## Roan / Bregman rollout (Phase 0+ — does not relax directional learning)

**Design:** 5m brain, 15m hands — see `docs/roan-bregman-architecture.md`.

| Series | Role during learning_collection |
|--------|----------------------------------|
| `btc-up-or-down-5m` | **Brain only** (Phase 1+): scan, LCMM child, arb detect — **no directional trades** |
| `btc-up-or-down-15m` | **Hands**: directional DOWN + parent LCMM + settlement |

**Allowed in Phase 1 without ending learning_collection:**

- `PULSE_SERIES_SLUGS` → `btc-up-or-down-5m,btc-up-or-down-15m` (scan breadth)
- `PULSE_DIRECTIONAL_SERIES_SLUGS` stays `btc-up-or-down-15m` only

**Still forbidden until promotion scorecard (`roan-bregman-promotion-scorecard.json`):**

- `PULSE_DEPENDENCY_ARB_EXECUTE=1`
- `PULSE_BREGMAN_TRADE_AUTHORITY=1`
- Directional trading on 5m series

## Ending learning-collection mode

Operator must say explicitly in the current message. Until then, treat WR targets as **deferred**
and prioritize fill rate + ledger continuity.
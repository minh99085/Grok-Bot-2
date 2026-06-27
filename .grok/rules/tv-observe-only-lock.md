# TradingView observe-only lock (OPERATOR MANDATE — DO NOT CHANGE)

**Locked:** 2026-06-27. Operator directive: keep this setup forever; **never re-enable TV as a trade gate**, no matter how we tweak gates, strategy, babysit cycles, or WR targets.

## Principle

TradingView webhooks are **observe-only**: features for Grok, dashboard, and quant context. TV alerts **never** place, block, resize, or fast-track a directional trade.

Trade authority stays on: **baseline quant cohort** → **selectivity floor** → **execution gate**. Grok remains **shadow**.

## Frozen env keys (`apply-loop-arch-env.py`)

These values must **always** remain as below. Do not set to `1` or tighten in code, babysit fixes, or "starvation relax" unless the operator **explicitly overrides in the current message**:

```
PULSE_TRADINGVIEW_SIGNAL_GATE=0
PULSE_TV_MTF_CONFLICT_GATE=0
PULSE_TV_MTF_REQUIRE_CONFIRM=0
PULSE_TV_MTF_REQUIRE_ALL_CONFIRM=0
PULSE_TV_MTF_REQUIRE_SIDE_ALIGN=0
PULSE_TV_CONTEXT_GATE=0
PULSE_BASELINE_DOWN_TV_GATE_ENABLED=0
PULSE_BASELINE_UP_TV_GATE_ENABLED=0
```

TV intake stays **on** (webhooks, `PULSE_TV_FEATURE_SYMBOL`, `PULSE_TV_MTF_TIMEFRAMES=2,3,4`) — only **gates** are frozen off.

## Frozen engine behavior

- **Green path** (`PULSE_GREEN_PATH_ENABLED=1`): skips `mtf_gate`, `context_gate`, `tv_signal`, `down_bias`, `late_window` on 15m DOWN baseline.
- **`mtf_gate`**: skipped when `PULSE_TV_MTF_CONFLICT_GATE=0` or green path active; record `observe_only: true` in decision logs.
- **Never** add MTF 3/3, side-align, or TV stack checks back into cohort or babysit "fixes".

## What agents may still tune (without touching TV gates)

- Baseline cohort TTC band (480–660s on 15m), edge/CEX relax flags
- Selectivity, execution gate, min_edge, max_price, reward/risk
- DOWN-only, 15m series, Grok shadow, arb settings
- CEX-lead / mispricing (if operator asks) — separate from TV

## Babysit / autopilot

When `trade_starvation`, `mtf_starved`, or `win_rate_below_target` fire:

- **Do not** re-enable `PULSE_TV_MTF_REQUIRE_ALL_CONFIRM`, `SIDE_ALIGN`, `CONTEXT_GATE`, or baseline TV gates.
- Relax **quant** gates (cohort edge, execution floor, selectivity) instead.

## Verification after any deploy

Status API must show:

- `tradingview.mtf_gate.enabled` = **false**
- `baseline_cohort_gate.down_tv_gate_enabled` = **false**
- `tradingview_alerts_valid` > 0 (webhooks still landing)
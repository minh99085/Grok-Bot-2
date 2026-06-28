# Self-improve closed loop (operator ON — 2026-06-28)

Operator mandate: bot must **scan → trade → learn → adjust** without manual prompting.

**Mode:** `real_money_discipline` — see `.grok/rules/real-money-discipline.md`. Paper PnL treated as real capital.

## Adjust layer (runtime — engine)

| Knob | Value | Effect |
|------|-------|--------|
| `PULSE_RESEARCH_AUTO_APPLY` | **1** | Evidence-backed avoid/exploit (maker-checker; never loosens gates) |
| `PULSE_SELECTIVITY_MIN_SAMPLES` | **30** | Faster auto-blocks on proven losers |
| `PULSE_LEARNING_ENABLED` | **1** | Edge-model blend (near-market bench margin) |

## Outer loop (babysit)

| Item | Value |
|------|-------|
| `state.json` `goals.mode` | `real_money_discipline` |
| `phase` | `soak` (60 min — not 4h) |
| `babysit_autopilot` | `true` |
| Windows task `GrokBot2-PulseBabysit` | Enabled (~15 min) |

Babysit **relaxes** on trade_starvation; **tightens** on WR/PF/up_bleed. Never TV trade gates, never Grok follow.

## Still frozen

- Grok decider **shadow** only
- TV observe-only (no signal/MTF/context trade gates)
- Paper-only until explicit live ask
- Arb + dep-arb ON, 15s tick
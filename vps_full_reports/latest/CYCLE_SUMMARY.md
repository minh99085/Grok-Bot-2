# Bot cycle summary (plain English)

_Updated: 2026-06-27 00:25 UTC_

## Last cycle

| | |
|---|---|
| **Cycle #** | 17 |
| **Checked at** | 2026-06-26 23:22 UTC |
| **Result** | **issues** |
| **What it means** | Issues found — UP trades still lose money. More UP blocks may have been added. |
| **Next check after** | 2026-06-27 00:24 UTC |

**Issues flagged:** up_side_bleed

**Fixes applied:**

- down_bias: block UP when orderbook ask_heavy (50% WR, -13.61 PnL, n=20)
- down_bias: block UP when tf_confirm=conflict (25% WR, -4.69 PnL, n=4; Grok path gap)

## How the bot is doing now

| | |
|---|---|
| **Mode** | Paper only (fake money) |
| **Started with** | $500.00 |
| **Total now** | $555.22 (11.04% return) |
| **Arb profit** | $59.73 (7 trades) |
| **Directional profit** | $-4.51 |
| **Win rate** | 61.7% (81 settled trades) |
| **UP win rate** | 50.0% |
| **DOWN win rate** | 65.6% |
| **Bot stopped?** | No — bot is running |
| **Overall grade** | — (—/100) |

### 5m vs 15m (recent)

| Market | Trades | Win rate | PnL |
|--------|--------|----------|-----|
| **15m** | 14 | 57.1% | $-4.69 |
| **5m** | 19 | 63.2% | $-1.31 |

### TradingView (INDEX:BTCUSD)

- Alerts received: **109**
- 5-chart trend: **single_tf** (1/5 fresh)

## Quick verdict

**Good:** Making money on paper (+11.0%); Arbitrage is doing most of the work; DOWN trades work well; Bot is running normally.

**Watch:** UP trades still weak (coin-flip or worse); Cycle flagged UP-side losses.

---

_Auto-generated after each `/pulse-babysit` cycle. Full report: `report.md` / `report.docx` in this folder._

# Bot cycle summary (plain English)

_Updated: 2026-06-26 17:07 UTC_

## Last cycle

| | |
|---|---|
| **Cycle #** | 13 |
| **Checked at** | 2026-06-26 17:07 UTC |
| **Result** | **issues** |
| **What it means** | Issues found — UP trades still lose money. More UP blocks may have been added. |
| **Next check after** | 2026-06-26 17:24 UTC |

**Issues flagged:** up_side_bleed

**Fixes applied:**

- down_bias: block UP when range_state=breakout_down (0% WR, -12.50 PnL)
- down_bias: block UP when bb_state=squeeze (33% WR, -10.82 PnL)

## How the bot is doing now

| | |
|---|---|
| **Mode** | Paper only (fake money) |
| **Started with** | $500.00 |
| **Total now** | $565.80 (13.16% return) |
| **Arb profit** | $59.73 (7 trades) |
| **Directional profit** | $6.07 |
| **Win rate** | 63.6% (55 settled trades) |
| **UP win rate** | 50.0% |
| **DOWN win rate** | 71.4% |
| **Bot stopped?** | No — bot is running |
| **Overall grade** | — (—/100) |

### 5m vs 15m (recent)

| Market | Trades | Win rate | PnL |
|--------|--------|----------|-----|
| **15m** | 4 | 75.0% | $4.37 |
| **5m** | 3 | 66.7% | $0.21 |

### TradingView (INDEX:BTCUSD)

- Alerts received: **34**
- 5-chart trend: **partial_up_5tf** (2/5 fresh)

## Quick verdict

**Good:** Making money on paper (+13.2%); Arbitrage is doing most of the work; DOWN trades work well; Bot is running normally.

**Watch:** UP trades still weak (coin-flip or worse); Cycle flagged UP-side losses.

---

_Auto-generated after each `/pulse-babysit` cycle. Full report: `report.md` / `report.docx` in this folder._

# Bot cycle summary (plain English)

_Updated: 2026-06-26 23:22 UTC_

## Last cycle

| | |
|---|---|
| **Cycle #** | 16 |
| **Checked at** | 2026-06-26 21:22 UTC |
| **Result** | **issues** |
| **What it means** | Issues found — UP trades still lose money. More UP blocks may have been added. |
| **Next check after** | 2026-06-26 22:25 UTC |

**Issues flagged:** up_side_bleed

**Fixes applied:**

- down_bias: block UP when edge_score=medium (50% WR, -13.92 PnL, n=18)
- down_bias: block UP when CEX agreement not strong (50% WR, -11.20 PnL, n=14)

## How the bot is doing now

| | |
|---|---|
| **Mode** | Paper only (fake money) |
| **Started with** | $500.00 |
| **Total now** | $570.22 (14.04% return) |
| **Arb profit** | $59.73 (7 trades) |
| **Directional profit** | $10.49 |
| **Win rate** | 64.1% (78 settled trades) |
| **UP win rate** | 50.0% |
| **DOWN win rate** | 69.0% |
| **Bot stopped?** | No — bot is running |
| **Overall grade** | — (—/100) |

### 5m vs 15m (recent)

| Market | Trades | Win rate | PnL |
|--------|--------|----------|-----|
| **15m** | 11 | 72.7% | $10.31 |
| **5m** | 19 | 63.2% | $-1.31 |

### TradingView (INDEX:BTCUSD)

- Alerts received: **97**
- 5-chart trend: **partial_up_5tf** (2/5 fresh)

## Quick verdict

**Good:** Making money on paper (+14.0%); Arbitrage is doing most of the work; DOWN trades work well; Bot is running normally.

**Watch:** UP trades still weak (coin-flip or worse); Cycle flagged UP-side losses.

---

_Auto-generated after each `/pulse-babysit` cycle. Full report: `report.md` / `report.docx` in this folder._

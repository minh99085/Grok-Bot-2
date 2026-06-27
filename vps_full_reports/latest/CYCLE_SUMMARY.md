# Bot cycle summary (plain English)

_Updated: 2026-06-27 10:33 UTC_

## Last cycle

| | |
|---|---|
| **Cycle #** | 24 |
| **Checked at** | 2026-06-27 08:36 UTC |
| **Result** | **issues** |
| **What it means** | Issues found — UP trades still lose money. More UP blocks may have been added. |
| **Next check after** | 2026-06-27 09:36 UTC |

**Issues flagged:** win_rate_below_target, profit_factor_low, up_side_bleed

**Fixes applied:**

- down_bias: block UP when not_stale (50pct WR, -13.61 PnL, n=20)
- baseline_down: block DOWN when mtf=bullish_aligned (54.5pct WR, -5.16 PnL, n=11)

## How the bot is doing now

| | |
|---|---|
| **Mode** | Paper only (fake money) |
| **Started with** | $500.00 |
| **Total now** | $556.01 (11.2% return) |
| **Arb profit** | $59.73 (7 trades) |
| **Directional profit** | $-3.72 |
| **Win rate** | 61.6% (86 settled trades) |
| **UP win rate** | 50.0% |
| **DOWN win rate** | 65.1% |
| **Bot stopped?** | No — bot is running |
| **Overall grade** | — (—/100) |

### 5m vs 15m (recent)

| Market | Trades | Win rate | PnL |
|--------|--------|----------|-----|
| **15m** | 19 | 57.9% | $-3.91 |
| **5m** | 19 | 63.2% | $-1.31 |

### TradingView (INDEX:BTCUSD)

- Alerts received: **299**
- 5-chart trend: **conflict_3tf** (3/3 fresh)

## Quick verdict

**Good:** Making money on paper (+11.2%); Arbitrage is doing most of the work; DOWN trades work well; Bot is running normally.

**Watch:** UP trades still weak (coin-flip or worse); Cycle flagged UP-side losses.

---

_Auto-generated after each `/pulse-babysit` cycle. Full report: `report.md` / `report.docx` in this folder._

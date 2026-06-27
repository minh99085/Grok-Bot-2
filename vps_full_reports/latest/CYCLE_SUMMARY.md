# Bot cycle summary (plain English)

_Updated: 2026-06-27 02:22 UTC_

## Last cycle

| | |
|---|---|
| **Cycle #** | 18 |
| **Checked at** | 2026-06-27 00:25 UTC |
| **Result** | **issues** |
| **What it means** | Issues found — UP trades still lose money. More UP blocks may have been added. |
| **Next check after** | 2026-06-27 01:27 UTC |

**Issues flagged:** profit_factor_low, up_side_bleed

**Fixes applied:**

- down_bias: block UP when cvd_state=neutral (25% WR, -12.86 PnL, n=4)
- down_bias: block UP when conviction<0.4 (coin-flip fair); PULSE_MIN_REWARD_RISK=0.45

## How the bot is doing now

| | |
|---|---|
| **Mode** | Paper only (fake money) |
| **Started with** | $500.00 |
| **Total now** | $557.53 (11.51% return) |
| **Arb profit** | $59.73 (7 trades) |
| **Directional profit** | $-2.20 |
| **Win rate** | 61.9% (84 settled trades) |
| **UP win rate** | 50.0% |
| **DOWN win rate** | 65.6% |
| **Bot stopped?** | No — bot is running |
| **Overall grade** | — (—/100) |

### 5m vs 15m (recent)

| Market | Trades | Win rate | PnL |
|--------|--------|----------|-----|
| **15m** | 17 | 58.8% | $-2.38 |
| **5m** | 19 | 63.2% | $-1.31 |

### TradingView (INDEX:BTCUSD)

- Alerts received: **117**
- 5-chart trend: **partial_up_5tf** (2/5 fresh)

## Quick verdict

**Good:** Making money on paper (+11.5%); Arbitrage is doing most of the work; DOWN trades work well; Bot is running normally.

**Watch:** UP trades still weak (coin-flip or worse); Cycle flagged UP-side losses.

---

_Auto-generated after each `/pulse-babysit` cycle. Full report: `report.md` / `report.docx` in this folder._

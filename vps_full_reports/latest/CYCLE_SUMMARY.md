# Bot cycle summary (plain English)

_Updated: 2026-06-27 15:33 UTC_

## Last cycle

| | |
|---|---|
| **Cycle #** | 26 |
| **Checked at** | 2026-06-27 14:16 UTC |
| **Result** | **blocked** |
| **What it means** | Stopped — serious problem found. Check issues below. |
| **Next check after** | 2026-06-27 15:11 UTC |

**Issues flagged:** trade_starvation, win_rate_below_target, profit_factor_low, up_side_bleed

**Fixes applied:**

- audit fix: BB_EXPANSION_DOWN=0 (was blocking bearish BB confirm on DOWN)
- audit fix: NOT_STALE=0, MID_ENTRY=0, SINGLE_TF=0 (reduce over-gating; MTF 3/3 remains)

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

- Alerts received: **460**
- 5-chart trend: **confirmed_up_3tf** (3/3 fresh)

## Quick verdict

**Good:** Making money on paper (+11.2%); Arbitrage is doing most of the work; DOWN trades work well; Bot is running normally.

**Watch:** UP trades still weak (coin-flip or worse); Cycle flagged UP-side losses.

---

_Auto-generated after each `/pulse-babysit` cycle. Full report: `report.md` / `report.docx` in this folder._

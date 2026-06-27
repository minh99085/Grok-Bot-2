# Bot cycle summary (plain English)

_Updated: 2026-06-27 19:34 UTC_

## Last cycle

| | |
|---|---|
| **Cycle #** | 2 |
| **Checked at** | 2026-06-27 17:34 UTC |
| **Result** | **blocked** |
| **What it means** | Stopped — serious problem found. Check issues below. |
| **Next check after** | 2026-06-27 18:37 UTC |

**Fixes applied:**

- reconciliation_drift_repair: absorb ledger/lifecycle skew into baseline on startup
- cohort_tier1: REQUIRE_HIGH_EDGE + REQUIRE_STRONG_CEX enabled

## How the bot is doing now

| | |
|---|---|
| **Mode** | Paper only (fake money) |
| **Started with** | $500.00 |
| **Total now** | $545.26 (9.05% return) |
| **Arb profit** | $59.73 (7 trades) |
| **Directional profit** | $-14.47 |
| **Win rate** | 60.0% (90 settled trades) |
| **UP win rate** | 50.0% |
| **DOWN win rate** | 62.9% |
| **Bot stopped?** | No — bot is running |
| **Overall grade** | — (—/100) |

### 5m vs 15m (recent)

| Market | Trades | Win rate | PnL |
|--------|--------|----------|-----|
| **15m** | 23 | 52.2% | $-14.65 |
| **5m** | 19 | 63.2% | $-1.31 |

### TradingView (INDEX:BTCUSD)

- Alerts received: **557**
- 5-chart trend: **confirmed_down_3tf** (3/3 fresh)

## Quick verdict

**Good:** Making money on paper (+9.1%); Arbitrage is doing most of the work; Bot is running normally.

**Watch:** UP trades still weak (coin-flip or worse).

---

_Auto-generated after each `/pulse-babysit` cycle. Full report: `report.md` / `report.docx` in this folder._

# Bot cycle summary (plain English)

_Updated: 2026-06-28 02:34 UTC_

## Last cycle

| | |
|---|---|
| **Cycle #** | 6 |
| **Checked at** | 2026-06-28 01:11 UTC |
| **Result** | **issues** |
| **What it means** | Issues found — UP trades still lose money. More UP blocks may have been added. |
| **Next check after** | 2026-06-28 01:45 UTC |

**Issues flagged:** win_rate_below_target, up_side_bleed

**Fixes applied:**

- reconciliation: repair_accounting_drift before each light_report (absorb ledger/lifecycle drift)
- min_edge: 0.015 → 0.012; min_reward_risk: 0.55 → 0.50 (trade_starvation_streak P0)

## How the bot is doing now

| | |
|---|---|
| **Mode** | Paper only (fake money) |
| **Started with** | $500.00 |
| **Total now** | $576.78 (15.36% return) |
| **Arb profit** | $59.73 (7 trades) |
| **Directional profit** | $-3.38 |
| **Win rate** | 60.8% (97 settled trades) |
| **UP win rate** | 50.0% |
| **DOWN win rate** | 63.6% |
| **Bot stopped?** | No — bot is running |
| **Overall grade** | — (—/100) |

### 5m vs 15m (recent)

| Market | Trades | Win rate | PnL |
|--------|--------|----------|-----|
| **15m** | 30 | 56.7% | $-3.56 |
| **5m** | 19 | 63.2% | $-1.31 |

### TradingView (INDEX:BTCUSD)

- Alerts received: **801**
- 5-chart trend: **confirmed_down_3tf** (3/3 fresh)

## Quick verdict

**Good:** Making money on paper (+15.4%); Arbitrage is doing most of the work; Bot is running normally.

**Watch:** UP trades still weak (coin-flip or worse); Cycle flagged UP-side losses.

---

_Auto-generated after each `/pulse-babysit` cycle. Full report: `report.md` / `report.docx` in this folder._

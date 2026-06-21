# BTC 5-Minute Pulse — Live Paper Report

_Generated 2026-06-21 13:17 UTC from live VPS container `hermes-training`._

**Mode:** PAPER ONLY — `live_trading_enabled = False`, `paper_only = True`. No real orders are ever placed.

## 1. Engine health
| Metric | Value |
|---|---|
| Ticks processed | 4982 |
| Oracle feed | `chainlink_data_streams_refprice` (btc/usd) |
| RTDS connected | True (39580 msgs, 2 reconnects) |
| Latest Chainlink px | 64070.27 |
| Latest Binance px | 64147.87 |
| Price source | `rtds_chainlink` (sampler 1.0s, 5000 vol samples) |
| Tracked window opens | 67 |
| Grok overlay | enabled=True, 109 calls, 0 errors, regime=`calm`, blackout=False |

## 2. Paper P&L (cumulative ledger)
| Metric | Value |
|---|---|
| Trades / settled | 139 / 137 |
| Win rate | 53.3% (up 56.7%, down 50.6%) |
| Realized PnL | $9.80 |
| Avg PnL / trade | $0.0716 |
| Profit factor | 0.935 |
| Avg win / avg loss | $2.11 / $2.58 |
| Max drawdown | $44.46 |
| Realized edge | 0.0087 |
| Open positions | 2 |

## 3. Execution-quality gate
- Candidates evaluated: **94**, accepted: **94**, rejected: **0** (reconciled=True).
- Reject reasons: `{"wide_spread": 0, "insufficient_depth": 0, "negative_ev_after_slippage": 0, "too_close_to_resolution": 0, "min_size_or_tick_violation": 0, "partial_fill_risk": 0, "missing_market_data": 0, "stale_orderbook": 0}`
- EV after costs (n=66): before **0.1021**, after **0.0965**.

## 4. Settlement & reconciliation
- Sources used: `{"polymarket_resolution": 58, "rtds_chainlink_proxy": 63}`
- Proxy/official reconciliation: `{"both": 57, "agree": 54, "disagree": 3}` (54/57 agree).
- Proxy max close lag: 30.0s.

## 5. Calibration
- Brier **0.2320** vs 0.5-baseline 0.25 (lower is better).
- Log-loss 0.6476 · base rate up 0.525 · samples 137.

## 6. Where the edge is (observe-only bucket PnL)
| Markov state | n | win | PnL |
|---|---|---|---|
| stale_polymarket_down | 27 | 63.0% | $26.97 |
| stale_polymarket_up | 19 | 36.8% | $-42.04 |
| chop_noise | 19 | 42.1% | $4.43 |

| Confidence tier | n | win | PnL |
|---|---|---|---|
| high | 52 | 55.8% | $24.58 |
| medium | 10 | 20.0% | $-31.33 |
| low | 3 | 33.3% | $-3.89 |

| Z-score bucket | n | win | PnL |
|---|---|---|---|
| na | 2 | 50.0% | $7.24 |
| -2..-1 | 13 | 53.8% | $1.61 |
| -1..1 | 38 | 42.1% | $-22.51 |
| 1..2 | 6 | 33.3% | $-4.44 |
| <=-2 | 4 | 100.0% | $5.48 |
| >=2 | 2 | 100.0% | $1.98 |

## 7. Tier census & promotion ladder
- Tier census: `{"A+": 0, "A": 0, "B": 6, "C": 5, "D": 0}` (affects_trading=False).
- Promotion candidates: `[]`
- Demotion candidates: `["edge_quality:high", "regime:trending", "zscore_bucket:-1..1", "zscore_bucket:1..2", "ttc_bucket:120-240s"]`
- Sizing: enabled=False, actual_size=$5.0.

## 8. Readiness gates → **NOT_READY** (ready_to_claim_80pct=False)
| Gate | Pass |
|---|---|
| accepted_ge_100 | ✅ |
| accepted_ge_500 | ❌ |
| accepted_ge_1000 | ❌ |
| win_rate_ge_80 | ❌ |
| positive_net_paper_pnl | ✅ |
| profit_factor_ok | ❌ |
| calibration_error_ok | ❌ |
| max_drawdown_ok | ✅ |
| loss_size_le_win_size | ❌ |
| no_reconciliation_failures | ✅ |
| no_missing_settlement_data | ✅ |
| no_unmodeled_fill_assumptions | ✅ |
| no_safety_bypass | ✅ |

**Interpretation:** 139 settled paper trades, 53.3% win rate, +$9.80 net but profit factor 0.94 (<1.0 — avg loss $2.58 still exceeds avg win $2.11). Calibration (0.232) only marginally beats coinflip. Status remains `not_ready`; the engine needs far more settled trades and a real win-rate/profit-factor edge before any promotion. All research features remain observe-only.

# BTC 5-Minute Pulse — Full Report

_Generated 2026-06-22 13:45 UTC from live VPS container `hermes-training` (PAPER ONLY)._

**Mode:** `paper_only=True`, `live_trading_enabled=False`, **`global_reconciled=true`** · ticks 2186 · oracle `chainlink_data_streams_refprice`.

## 1. Paper P&L (cumulative)

| Metric | Value |
|---|---|
| Trades / settled | 283 / 283 |
| Win rate | 52.6% |
| Realized PnL | $-72.7667 |
| Wins / losses | 149 / 134 |
| Open | 0 |
| EV after costs (avg) | 0.107694 |

## 2. Accounting integrity

`global_reconciled=true`. lifecycle counts are cumulative since canonical accounting began; baseline counts are legacy ledger totals that predate it; ledger/gate totals == baseline + accounted.

## 3. Candidate lifecycle

created 13452 · accepted 132 · rejected 12862 · skipped 443 · missing_data 15

**rejected_by_stage:** `{'directional': 12267, 'execution_gate': 0, 'selectivity_gate': 554, 'context_gate': 41}`

## 4. TradingView Context Gate (restrict-only, LIVE)

enabled=True · passed 110 · blocked 41 · explored 2

block_reasons: `{'tv_context_volume_spike': 28, 'tv_context_ttc_too_far': 13}`

## 5. Learned Selectivity Gate

enabled=True · accepted 0 · rejected 554 · explored 32

counterfactual: baseline WR 0.5122 / PnL $-105.1524 → rejects 205, avoids 100 losses.

## 6. Late-window high-conviction entry (time-decay edge)

gate enabled=False (measuring) · verdict **insufficient_evidence**

cohort late_high_conviction: `{'n': 1, 'win_rate': 0.0, 'pnl_usd': -5.0, 'avg_pnl_usd': -5.0, 'avg_ev_after_cost': 0.093194}` · other: `{'n': 4, 'win_rate': 0.5, 'pnl_usd': 0.646, 'avg_pnl_usd': 0.1615, 'avg_ev_after_cost': 0.092874}`

## 7. Grok intel (full $20 coverage)

budget $1.62/$20.0 today (81 calls, 0 errors). Predictor B accuracy 0.5059, Brier 0.256 (n 85). Analyst A calls 21.

## 8. TradingView learning

received 89 · valid 89 · rejected 0 · settled_with_signal 36

best buckets: `ttc_bucket=<60s`(n3,WR0.0), `htf_bias=bearish`(n5,WR0.4), `vwap_state=below`(n14,WR0.5714), `volume_state=active`(n14,WR0.7143)

worst buckets: `range_state=breakout_down`(n3,WR0.6667), `vwap_state=reclaim`(n3,WR0.6667), `zscore_bucket=-2..-1`(n5,WR0.2), `zscore_bucket=1..2`(n3,WR0.3333)

RSI signal-direction hit-rate 0.5 (n 88); v4 order-flow/event fields deployed (observe-only).

## 9. Edge signal

enabled=True · CEX coverage None

## 10. Readiness

status `not_ready`, ready_to_claim_80pct=False.


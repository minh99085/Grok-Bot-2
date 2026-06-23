# BTC 5-Minute Pulse — FULL Performance Report

_PAPER ONLY. `live_trading_enabled=False` · `global_reconciled=True` · ticks 5851._


## 1. Capital & P&L

| metric | value |
|---|---|
| On-hand capital | $408.59 |
| Starting capital | $500.0 |
| Return | -18.28% |
| Open exposure | $0.0 (0 pos) |
| Trades / settled | 359 / 359 |
| Win rate | 0.5237 |
| Win rate up / down | 0.5286 / 0.5205 |
| Realized PnL | $-91.4082 |
| Profit factor | 0.8335 |
| Avg win / avg loss | $2.9789 / $3.9291 |
| Max drawdown | $146.5066 |
| Avg PnL/trade | -0.2546 |
| Side counts | {'up': 140, 'down': 219} |
| Settle sources | {'polymarket_resolution': 169, 'rtds_chainlink_proxy': 174} |
| Proxy vs official | {'both': 168, 'agree': 162, 'disagree': 6} |
| EV before/after cost | 0.112422 / 0.106727 |

## 2. Accounting integrity (reconciliation)

- **global_reconciled:** True
- **scope_note:** lifecycle counts are cumulative since canonical accounting began; baseline counts are legacy ledger totals that predate it; ledger/gate totals == baseline + accounted.
- **rejected_before_execution:** 21174

## 3. Candidate lifecycle

created 30472 · terminals `{'accepted': 208, 'rejected': 29140, 'skipped': 1089, 'expired': 0, 'missing_data': 35}`

rejected_by_stage `{'directional': 20050, 'execution_gate': 55, 'selectivity_gate': 916, 'context_gate': 414, 'grok_decider': 7705}`

## 4. Execution gate & calibration

candidates 369 · accepted 314 · rejects `{'wide_spread': 13, 'insufficient_depth': 0, 'negative_ev_after_slippage': 42, 'too_close_to_resolution': 0, 'min_size_or_tick_violation': 0, 'partial_fill_risk': 0, 'missing_market_data': 0, 'stale_orderbook': 0}`

calibration `{'samples': 359, 'brier': 0.231167, 'log_loss': 0.659223, 'base_rate_up': 0.4986, 'baseline_brier_0_5': 0.25}`

## 5. PnL by bucket (all dimensions)

**pnl_by_confidence_tier:** `{"medium": {"n": 8, "win_rate": 0.5, "pnl_usd": -2.909, "brier": 0.2713}, "low": {"n": 29, "win_rate": 0.4828, "pnl_usd": -24.6133, "brier": 0.209}}`
**pnl_by_conviction_bucket:** `{"0.4-0.6": {"n": 9, "win_rate": 0.5556, "pnl_usd": -4.3652, "brier": 0.287}, "<0.2": {"n": 9, "win_rate": 0.2222, "pnl_usd": -23.7567, "brier": 0.249}, "0.2-0.4": {"n": 10, "win_rate": 0.6, "pnl_usd": 10.1881, "brier": 0.2475}, "0.6-0.8": {"n": 8, "win_rate": 0.625, "pnl_usd": -4.5886, "brier": 0.1154}, ">=0.8": {"n": 1, "win_rate": 0.0, "pnl_usd": -5.0, "brier": 0.0085}}`
**pnl_by_depth_bucket:** `{">=1000": {"n": 37, "win_rate": 0.4865, "pnl_usd": -27.5224, "brier": 0.2225}}`
**pnl_by_edge_quality_bucket:** `{"high": {"n": 33, "win_rate": 0.4848, "pnl_usd": -22.6635, "brier": 0.2471}, "medium": {"n": 4, "win_rate": 0.5, "pnl_usd": -4.8588, "brier": 0.0189}}`
**pnl_by_entry_mode:** `{"standard": {"n": 31, "win_rate": 0.4839, "pnl_usd": -22.0975, "brier": 0.2599}, "late_window": {"n": 6, "win_rate": 0.5, "pnl_usd": -5.4249, "brier": 0.029}}`
**pnl_by_half_life_bucket:** `{"<30s": {"n": 34, "win_rate": 0.4706, "pnl_usd": -27.2156, "brier": 0.2334}, "30-120s": {"n": 3, "win_rate": 0.6667, "pnl_usd": -0.3067, "brier": 0.0988}}`
**pnl_by_hurst_regime:** `{"trending": {"n": 35, "win_rate": 0.4857, "pnl_usd": -25.997, "brier": 0.218}, "insufficient_data": {"n": 1, "win_rate": 0.0, "pnl_usd": -5.0, "brier": 0.4907}, "noise": {"n": 1, "win_rate": 1.0, "pnl_usd": 3.4746, "brier": 0.1097}}`
**pnl_by_markov_state:** `{"stale_polymarket_down": {"n": 14, "win_rate": 0.7143, "pnl_usd": 11.6238, "brier": 0.2121}, "stale_polymarket_up": {"n": 3, "win_rate": 0.0, "pnl_usd": -15.0, "brier": 0.4634}, "chop_noise": {"n": 19, "win_rate": 0.3684, "pnl_usd": -26.0907, "brier": 0.2031}, "resolution_danger": {"n": 1, "win_rate": 1.0, "pnl_usd": 1.9444, "brier": 0.0133}}`
**pnl_by_spread_bucket:** `{"<=0.01": {"n": 30, "win_rate": 0.5, "pnl_usd": -17.0975, "brier": 0.198}, "0.03-0.06": {"n": 3, "win_rate": 0.3333, "pnl_usd": -8.0556, "brier": 0.4311}, "0.01-0.03": {"n": 4, "win_rate": 0.5, "pnl_usd": -2.3693, "brier": 0.2497}}`
**pnl_by_ttc_bucket:** `{"120-240s": {"n": 28, "win_rate": 0.5, "pnl_usd": -13.8543, "brier": 0.2636}, "60-120s": {"n": 3, "win_rate": 0.3333, "pnl_usd": -5.566, "brier": 0.2368}, "<60s": {"n": 5, "win_rate": 0.4, "pnl_usd": -9.8588, "brier": 0.0209}, ">=240s": {"n": 1, "win_rate": 1.0, "pnl_usd": 1.7568, "brier": 0.0367}}`
**pnl_by_zscore_bucket:** `{"-1..1": {"n": 27, "win_rate": 0.4815, "pnl_usd": -18.4044, "brier": 0.2342}, "-2..-1": {"n": 4, "win_rate": 0.75, "pnl_usd": 7.1809, "brier": 0.2236}, "<=-2": {"n": 4, "win_rate": 0.5, "pnl_usd": -6.2988, "brier": 0.2466}, "1..2": {"n": 2, "win_rate": 0.0, "pnl_usd": -10.0, "brier": 0.0134}}`

## 6. Learned selectivity gate

- **decision_rule:** confidently_below_breakeven
- **confidence_z:** 1.64
- **accepted:** 44
- **rejected:** 916
- **explored:** 51
| dim | bucket | n | WR | breakeven | WR_upperCI | EV/trade | blocked |
|---|---|---|---|---|---|---|---|
| markov_state | stale_polymarket_up | 80 | 0.4875 | 0.5899 | 0.5781 | -0.7955 | True |
| direction | down | 192 | 0.5052 | 0.5659 | 0.5639 | -0.5071 | True |
| spread_bucket | <=0.01 | 270 | 0.5074 | 0.558 | 0.557 | -0.4342 | True |
| zscore_bucket | 1..2 | 34 | 0.4118 | 0.5188 | 0.5516 | -0.9798 | False |
| hurst_regime | insufficient_data | 31 | 0.3871 | 0.486 | 0.534 | -0.9428 | False |
| zscore_bucket | na | 41 | 0.4146 | 0.519 | 0.5422 | -0.9139 | False |
| ttc_bucket | 120-240s | 87 | 0.5287 | 0.6059 | 0.6143 | -0.6226 | False |
| markov_state | chop_noise | 111 | 0.4324 | 0.493 | 0.5102 | -0.5984 | False |

counterfactual `{'replayed': 236, 'trades_rejected': 233, 'losses_avoided': 114, 'pnl_removed_by_rejects': -117.0603, 'counterfactual_trades': 3, 'counterfactual_win_rate': 0.6667, 'counterfactual_pnl_usd': -0.1366, 'baseline_trades': 236, 'baseline_win_rate': 0.5127, 'baseline_pnl_usd': -117.1969, 'reject_reasons_by_bucket': {'bad_bucket:spread_bucket=<=0.01': 221, 'bad_bucket:markov_state=stale_polymarket_up': 3, 'bad_bucket:direction=down': 9}, 'note': 'in-sample replay using final accumulated bucket evidence (diagnostic estimate)'}`

## 7. Entry gates (context / late-window / reward-risk)

context_gate enabled=True · blocked 414 · `{'tv_context_volume_spike': 220, 'tv_context_ttc_too_far': 166, 'tv_context_hurst_noise': 28}`

late_window gate=False · verdict insufficient_evidence · LHC `{'n': 11, 'win_rate': 0.4545, 'pnl_usd': -14.5519, 'avg_pnl_usd': -1.3229, 'avg_ev_after_cost': 0.124659}` · other `{'n': 70, 'win_rate': 0.5143, 'pnl_usd': -8.4434, 'avg_pnl_usd': -0.1206, 'avg_ev_after_cost': 0.101101}`

## 8. Grok Decision Engine (decides; bot executes)

- **mode:** follow
- **affects_trading:** True
- **decided:** 221
- **errors:** 4
- **skipped_budget:** 0
- **avg_latency_s:** 5.798
- **graded_directional:** 0
- **direction_accuracy:** None
- **brier:** None
- **views_graded:** 170
- **view_accuracy:** 0.5
- **view_brier:** 0.2529
- **abstains:** 213
- **follow_fraction:** 1.0
- **explore_rate:** 0.5
- **adaptive_enabled:** True

by_action `{'no_trade': {'n': 213, 'direction_accuracy': None, 'pnl_usd': 0.0}}`

adaptive_policy_counts `{'exploit': 0, 'explore': 0, 'avoid': 0}`

aggression `{'aggression': 0.55, 'min': 0.0, 'max': 1.0, 'step_up': 0.05, 'step_down': 0.1, 'recent_net_pnl': 25.5716, 'updates': 21, 'note': 'loosens (more explore/looser exploit/larger size) as acted trades profit; tightens on losses; circuit breaker is the hard floor.'}`

accuracy_by_context `{"hurst_regime": {"insufficient_data": {"n": 13, "accuracy": 0.3077}, "trending": {"n": 152, "accuracy": 0.5263}, "noise": {"n": 5, "accuracy": 0.2}}, "markov_state": {"stale_polymarket_up": {"n": 50, "accuracy": 0.52}, "stale_polymarket_down": {"n": 59, "accuracy": 0.5424}, "chop_noise": {"n": 61, "accuracy": 0.4426}}, "ttc_bucket": {">=240s": {"n": 170, "accuracy": 0.5}}, "conviction_bucket": {"coinflip": {"n": 169, "accuracy": 0.497}, "lean": {"n": 1, "accuracy": 1.0}}}`

view_edge_candidates `[]`

circuit_breaker `{'tripped': True, 'reason': 'daily_loss_cap', 'consecutive_losses': 0, 'daily_follow_loss_usd': 31.88, 'daily_loss_cap_usd': 30.0, 'trips': 15, 'cooldown_remaining_s': 1507.6, 'max_consecutive_losses': 4, 'max_latency_s': 20.0}`

news_digest `{"enabled": true, "interval_s": 300.0, "calls": 217, "errors": 2, "skipped_budget": 0, "latest": {"sentiment": "bearish", "confidence": 0.65, "headlines": ["Bitcoin ETFs see continued outflows (~$68M daily, sustained negative streak)", "Crypto market drops as Nasdaq tech selloff spills into digital assets (BTC ~$62k)", "50+ crypto leaders meet US senators today urging crypto market structure bill", "CLARITY Act field hearing locked for July 17 in NYC", "Bitcoin volatility looks cheap ahead of $10B options settlement"], "event_risk": "low"}, "age_s": 32.2}`

recent_decisions `[{"action": "no_trade", "p_up": 0.495, "confidence": 0.0, "outcome_up": true, "view_correct": false, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_down", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.485, "confidence": 0.0, "outcome_up": false, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_up", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.495, "confidence": 0.0, "outcome_up": false, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_down", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.475, "confidence": 0.0, "outcome_up": true, "view_correct": false, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_down", `

## 9. Grok signal intel (analyst + predictor + budget)

budget `{'daily_usd_cap': 20.0, 'est_usd_per_call': 0.02, 'spent_today_usd': 7.38, 'calls_today': 369, 'per_feature_hourly': {'predictor': 120, 'analyst': 6, 'overlay': 20, 'decider': 60, 'news': 30}}`

predictor_B `{'enabled': True, 'observe_only': True, 'affects_trading': False, 'off_hot_path': True, 'requested': 314, 'predicted': 311, 'errors': 3, 'skipped_budget': 0, 'scored': 289, 'accuracy': 0.5156, 'brier': 0.2535, 'pending': 0, 'note': 'observe-only Grok P(up) per signal; graded vs realized BTC move before it could ever be trusted; never places/sizes/bypasses a trade.'}`

analyst_A last_note `{"summary": "DOWN_STRONG, range_bottom, lower_wick_rejection, dead volume, and bearish_aligned buckets now show confirmed positive EV with n>=13, win-rates 0.57-0.77 above breakeven, and net positive realized pnl after costs; most other regimes remain noise with negative aggregate pnl of -33.88 USD across 100 trades. UP direction and short ttc (<60s) buckets are clear underperformers. No prior analysis provided so no changes tracked yet.", "working": ["DOWN_STRONG (n=55, wr=0.5818, +10.29 pnl)", "range_bottom (n=28, wr=0.75, +39.78 pnl)", "lower_wick_rejection (n=13, wr=0.7692, +22.86 pnl)", "volume_dead (n=44, wr=0.5909, +10.67 pnl)", "bearish_aligned mtf (n=37, wr=0.5676, +13.46 pnl)"], "failing": ["UP direction overall (n=24, wr=0.4583, -30.13 pnl)", "volume_spike (n=14, wr=0.2857, -36.33 pnl)", "range_top (n=18, wr=0.3333, -35.05 pnl)", "ttc_<60s (n=13, wr=0.2308, -41.92 pnl)", "1..2 zscore (n=8, wr=0.25, -28.18 pnl)"], "warnings": ["All EV_after_cost values positive yet total realized pnl negative indicates unmodeled costs or slippage", "n<8 buckets ignored per rules; many remaining buckets still low power", "observe_only mode means no live execution risk but also no real fill`

## 10. TradingView learning

- **tradingview_alerts_received:** 314
- **tradingview_alerts_valid:** 314
- **tradingview_alerts_rejected:** 0

settled_with_signal 101

best_buckets `[{"dimension": "spread_bucket", "bucket": "0.01-0.03", "n": 7, "win_rate": 0.5714, "pnl_usd": -0.8226, "avg_ev_after_cost": 0.158524, "all_reconciled": true}, {"dimension": "ttc_bucket", "bucket": "<60s", "n": 13, "win_rate": 0.2308, "pnl_usd": -41.9223, "avg_ev_after_cost": 0.148731, "all_reconciled": true}, {"dimension": "hurst_regime", "bucket": "insufficient_data", "n": 6, "win_rate": 0.5, "pnl_usd": 4.7503, "avg_ev_after_cost": 0.126917, "all_reconciled": true}, {"dimension": "candle_pressure", "bucket": "lower_wick_rejection", "n": 13, "win_rate": 0.7692, "pnl_usd": 22.8635, "avg_ev_after_cost": 0.123608, "all_reconciled": true}, {"dimension": "volume_state", "bucket": "active", "n": 43, "win_rate": 0.5814, "pnl_usd": -13.2267, "avg_ev_after_cost": 0.122281, "all_reconciled": true}]`

worst_buckets `[{"dimension": "liquidation_spike", "bucket": "True", "n": 3, "win_rate": 0.6667, "pnl_usd": 1.3405, "avg_ev_after_cost": 0.076747, "all_reconciled": true}, {"dimension": "hurst_regime", "bucket": "noise", "n": 3, "win_rate": 0.3333, "pnl_usd": -6.5254, "avg_ev_after_cost": 0.07809, "all_reconciled": true}, {"dimension": "vwap_state", "bucket": "reclaim", "n": 3, "win_rate": 0.6667, "pnl_usd": -1.6643, "avg_ev_after_cost": 0.078272, "all_reconciled": true}, {"dimension": "range_state", "bucket": "breakout_up", "n": 5, "win_rate": 0.6, "pnl_usd": -4.8198, "avg_ev_after_cost": 0.088722, "all_reconciled": true}, {"dimension": "spread_bucket", "bucket": "0.03-0.06", "n": 4, "win_rate": 0.5, "pnl_usd": -5.6536, "avg_ev_after_cost": 0.089064, "all_reconciled": true}]`

rsi_trend hit_rate 0.5048 (n 313) · pred_acc 0.4491

## 11. Loop engineering (maker-checker / lessons / loops / research)

**Verifier (independent Claude maker-checker):** `{"enabled": true, "verified": 88, "approvals": 84, "vetoes": 4, "errors": 1, "approve_rate": 0.9545, "approved_acted_settled": {"n": 7, "win_rate": 0.5714, "pnl_usd": 11.1176}, "avg_latency_s": 4.683}`

**Research meta-loop:** `{"enabled": true, "calls": 15, "auto_apply": false, "lessons_added": 88}`

- research summary: Paper BTC bot is fundamentally unprofitable: 358 settled trades, 52.5% win rate, -$86 PnL, profit factor 0.84, with losses averaging $3.92 vs wins $2.98. No context shows robust edge—most buckets are coin-flip or losing. The market is efficient at 5-min horizons; small sample pockets (zscore -2..-1: n=4, 75% WR; stale_polymarket_down: n=14, 71% WR) are noise, not exploitable signal.

**Lessons (compounding rules):** count 96
- [`research`] ttc <60s: n=4, 25% WR, -$13.06 → execution/slippage overwhelms any model edge
- [`research`] zscore ≤-2 or 1..2: both lose (n=4+2) → momentum continues, mean-reversion bet fails
- [`research`] half_life <30s: n=30, 50% WR, -$15.41 → price oscillates too fast for 5-min resolution edge
- [`research`] 355 trades, profit_factor=0.85, avg_loss > avg_win → current feature set does NOT beat market efficiency at 5-min scale
- [`research`] 358 trades, 52.5% WR, -$86 PnL, PF=0.84: no exploitable edge in base strategy; 5-min BTC is near-efficient
- [`research`] zscore -2..-1 (n=4, 75% WR) and stale_polymarket_down (n=14, 71% WR) are small-sample flukes, not robust edges
- [`research`] Brier 0.230 vs baseline 0.250; model barely beats coin-flip, not predictive enough for profitable directionality
- [`research`] regime=trending: n=34, 50% WR, -$21 PnL; trend-following fails at 5-min scale due to lag and noise
- [`research`] execution gate rejected 42 trades as negative_ev_after_slippage; gate is working but pre-gate model still unprofitable
- [`research`] ttc <120s buckets lose more (33-40% WR) vs 120-240s (51.9% WR); sub-2min window adds execution noise, no edge

**Sub-loops:** data_ingestion, execution, heartbeat, lessons, news, research_meta, risk_monitor, signal_generation, verifier

## 12. Edge signal & readiness

edge_signal `{"enabled": true, "observe_only": true, "report_only": true, "affects_trading": false, "settled": 121, "by_stale_divergence": {"not_stale": {"n": 104, "win_rate": 0.5481, "pnl_usd": -25.065, "avg_ev_after_cost": 0.100302, "all_reconciled": true}, "already_priced": {"n": 11, "win_rate": 0.3636, "pnl_usd": -15.3432, "avg_ev_after_cost": 0.156639, "all_reconciled": true}, "stale_polymarket_up": {"n": 3, "win_rate": 0.3333, "pnl_usd": -8.6709, "avg_ev_after_cost": 0.089161, "all_reconciled": true}, "stale_polymarket_down": {"n": 3, "win_rate": 0.6667, "pnl_usd": -0.0715, "avg_ev_after_cost": 0.156542, "all_reconciled": true}}, "by_ttc_bucket": {"240_300s": {"n": 35, "win_rate": 0.5143, "pnl_usd"`

readiness `{'report_only': True, 'status': 'not_ready', 'ready_to_claim_80pct': False, 'gates': {'accepted_ge_100': True, 'accepted_ge_500': False, 'accepted_ge_1000': False, 'win_rate_ge_80': False, 'positive_net_paper_pnl': False, 'profit_factor_ok': False, 'calibration_error_ok': False, 'max_drawdown_ok': False, 'loss_size_le_win_size': False, 'no_reconciliation_failures': True, 'no_missing_settlement_data': True, 'no_unmodeled_fill_assumptions': True, 'no_safety_bypass': True}, 'metrics': {'accepted': 359, 'win_rate': 0.5237, 'net_pnl_usd': -91.4082, 'profit_factor': 0.8335, 'calibration_error': 0.231167, 'max_drawdown_usd': 146.5066, 'avg_win_usd': 2.9789, 'avg_loss_usd': 3.9291}}`

## 13. Recent paper positions

| window | side | entry_mode | entry | fair | outcome | won | pnl |
|---|---|---|---|---|---|---|---|
| , 8:25AM-8:30AM ET | down | standard | 0.65 | 0.2550272848360117 | up | ✗ | -5.0 |
| , 8:00AM-8:05AM ET | up | standard | 0.76 | 0.8514458949074138 | down | ✗ | -5.0 |
| , 7:55AM-8:00AM ET | up | late_window | 0.6100000000000001 | 0.8116603611364213 | up | ✓ | 3.196721 |
| , 7:50AM-7:55AM ET | down | standard | 0.68 | 0.22566537875815953 | up | ✗ | -5.0 |
| , 7:15AM-7:20AM ET | down | late_window | 0.029999999999999995 | 0.9079850364131508 | up | ✗ | -5.0 |
| , 7:05AM-7:10AM ET | down | standard | 0.47000000000000003 | 0.4047362461789197 | up | ✗ | -5.0 |
| , 6:50AM-6:55AM ET | down | standard | 0.72 | 0.21140242149811933 | down | ✓ | 1.944444 |
| , 6:35AM-6:40AM ET | down | standard | 0.22999999999999998 | 0.5859542746897715 | up | ✗ | -5.0 |
| , 6:30AM-6:35AM ET | down | standard | 0.74 | 0.16975893701184458 | down | ✓ | 1.756757 |
| , 6:25AM-6:30AM ET | down | standard | 0.64 | 0.28023094846670954 | down | ✓ | 2.8125 |
| , 6:20AM-6:25AM ET | down | standard | 0.63 | 0.3098743412143807 | down | ✓ | 2.936508 |
| , 6:10AM-6:15AM ET | down | standard | 0.37 | 0.5668255290645186 | up | ✗ | -5.0 |
| , 6:05AM-6:10AM ET | down | standard | 0.55 | 0.38730037591930694 | down | ✓ | 4.090909 |
| , 5:55AM-6:00AM ET | down | standard | 0.56 | 0.35699038968890456 | down | ✓ | 3.928571 |
| , 5:45AM-5:50AM ET | down | standard | 0.43000000000000005 | 0.40876542744316147 | up | ✗ | -5.0 |

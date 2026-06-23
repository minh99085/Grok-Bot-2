# BTC 5-Minute Pulse — FULL Performance Report

_PAPER ONLY. `live_trading_enabled=False` · `global_reconciled=True` · ticks 12._


## 1. Capital & P&L

| metric | value |
|---|---|
| On-hand capital | $412.75 |
| Starting capital | $500.0 |
| Return | -17.45% |
| Open exposure | $2.5 (1 pos) |
| Trades / settled | 305 / 304 |
| Win rate | 0.523 |
| Win rate up / down | 0.5328 / 0.515 |
| Realized PnL | $-87.245 |
| Profit factor | 0.8068 |
| Avg win / avg loss | $2.829 / $3.8448 |
| Max drawdown | $142.5879 |
| Avg PnL/trade | -0.287 |
| Side counts | {'up': 137, 'down': 167} |
| Settle sources | {'polymarket_resolution': 136, 'rtds_chainlink_proxy': 152} |
| Proxy vs official | {'both': 135, 'agree': 129, 'disagree': 6} |
| EV before/after cost | 0.112393 / 0.106997 |

## 2. Accounting integrity (reconciliation)

- **global_reconciled:** True
- **scope_note:** lifecycle counts are cumulative since canonical accounting began; baseline counts are legacy ledger totals that predate it; ledger/gate totals == baseline + accounted.
- **rejected_before_execution:** 16677

## 3. Candidate lifecycle

created 25305 · terminals `{'accepted': 154, 'rejected': 24094, 'skipped': 1025, 'expired': 0, 'missing_data': 32}`

rejected_by_stage `{'directional': 15620, 'execution_gate': 0, 'selectivity_gate': 837, 'context_gate': 217, 'grok_decider': 7420}`

## 4. Execution gate & calibration

candidates 260 · accepted 260 · rejects `{'wide_spread': 0, 'insufficient_depth': 0, 'negative_ev_after_slippage': 0, 'too_close_to_resolution': 0, 'min_size_or_tick_violation': 0, 'partial_fill_risk': 0, 'missing_market_data': 0, 'stale_orderbook': 0}`

calibration `{'samples': 304, 'brier': 0.231595, 'log_loss': 0.660584, 'base_rate_up': 0.5066, 'baseline_brier_0_5': 0.25}`

## 5. PnL by bucket (all dimensions)


## 6. Learned selectivity gate

- **decision_rule:** confidently_below_breakeven
- **confidence_z:** 1.64
- **accepted:** 1
- **rejected:** 837
- **explored:** 44
| dim | bucket | n | WR | breakeven | WR_upperCI | EV/trade | blocked |
|---|---|---|---|---|---|---|---|
| zscore_bucket | na | 31 | 0.3226 | 0.5302 | 0.4696 | -1.8645 | True |
| markov_state | stale_polymarket_up | 69 | 0.4928 | 0.6168 | 0.5899 | -0.9479 | True |
| direction | down | 140 | 0.4929 | 0.576 | 0.5616 | -0.6959 | True |
| confidence_tier | high | 177 | 0.5141 | 0.5784 | 0.5751 | -0.5395 | True |
| spread_bucket | <=0.01 | 224 | 0.5045 | 0.5644 | 0.5589 | -0.5184 | True |
| ttc_bucket | 120-240s | 57 | 0.5439 | 0.6407 | 0.6476 | -0.7411 | False |
| zscore_bucket | 1..2 | 32 | 0.4375 | 0.5174 | 0.5806 | -0.7289 | False |
| zscore_bucket | -1..1 | 122 | 0.5 | 0.5605 | 0.5734 | -0.5356 | False |

counterfactual `{'replayed': 199, 'trades_rejected': 198, 'losses_avoided': 99, 'pnl_removed_by_rejects': -138.1732, 'counterfactual_trades': 1, 'counterfactual_win_rate': 1.0, 'counterfactual_pnl_usd': 1.6667, 'baseline_trades': 199, 'baseline_win_rate': 0.5025, 'baseline_pnl_usd': -136.5066, 'reject_reasons_by_bucket': {'bad_bucket:confidence_tier=high': 138, 'bad_bucket:zscore_bucket=na': 19, 'bad_bucket:spread_bucket=<=0.01': 40, 'bad_bucket:direction=down': 1}, 'note': 'in-sample replay using final accumulated bucket evidence (diagnostic estimate)'}`

## 7. Entry gates (context / late-window / reward-risk)

context_gate enabled=True · blocked 217 · `{'tv_context_volume_spike': 111, 'tv_context_ttc_too_far': 85, 'tv_context_hurst_noise': 21}`

late_window gate=False · verdict insufficient_evidence · LHC `{'n': 5, 'win_rate': 0.4, 'pnl_usd': -9.127, 'avg_pnl_usd': -1.8254, 'avg_ev_after_cost': 0.115902}` · other `{'n': 21, 'win_rate': 0.4762, 'pnl_usd': -9.7052, 'avg_pnl_usd': -0.4622, 'avg_ev_after_cost': 0.088439}`

## 8. Grok Decision Engine (decides; bot executes)

- **mode:** follow
- **affects_trading:** True
- **decided:** 116
- **errors:** 4
- **skipped_budget:** 0
- **avg_latency_s:** 5.917
- **graded_directional:** 0
- **direction_accuracy:** None
- **brier:** None
- **views_graded:** 65
- **view_accuracy:** 0.4615
- **view_brier:** 0.2537
- **abstains:** 108
- **follow_fraction:** 1.0
- **explore_rate:** 0.5
- **adaptive_enabled:** True

by_action `{'no_trade': {'n': 108, 'direction_accuracy': None, 'pnl_usd': 0.0}}`

adaptive_policy_counts `{'exploit': 0, 'explore': 0, 'avoid': 0}`

aggression `{'aggression': 0.0, 'min': 0.0, 'max': 1.0, 'step_up': 0.05, 'step_down': 0.1, 'recent_net_pnl': -2.5, 'updates': 3, 'note': 'loosens (more explore/looser exploit/larger size) as acted trades profit; tightens on losses; circuit breaker is the hard floor.'}`

accuracy_by_context `{"hurst_regime": {"insufficient_data": {"n": 6, "accuracy": 0.1667}, "trending": {"n": 59, "accuracy": 0.4915}}, "markov_state": {"stale_polymarket_up": {"n": 25, "accuracy": 0.48}, "stale_polymarket_down": {"n": 20, "accuracy": 0.5}, "chop_noise": {"n": 20, "accuracy": 0.4}}, "ttc_bucket": {">=240s": {"n": 65, "accuracy": 0.4615}}, "conviction_bucket": {"coinflip": {"n": 65, "accuracy": 0.4615}}}`

view_edge_candidates `[]`

circuit_breaker `{'tripped': False, 'reason': None, 'consecutive_losses': 2, 'daily_follow_loss_usd': 12.5, 'daily_loss_cap_usd': 30.0, 'trips': 0, 'cooldown_remaining_s': 0, 'max_consecutive_losses': 4, 'max_latency_s': 20.0}`

news_digest `{"enabled": true, "interval_s": 300.0, "calls": 113, "errors": 2, "skipped_budget": 0, "latest": {"sentiment": "neutral", "confidence": 0.55, "headlines": ["Strategy/Saylor adds 520 BTC (~$35M); holdings ~848k BTC (X post ~3:51 GMT)", "BTC ETF daily net inflow reported +$95.67M (XT exchange summary)", "US extends Iran-related license, easing sanctions fears; BTC rebounding to ~$64k (X)", "Ark Invest buys $32M SpaceX shares amid plunge (X ~3:48 GMT)", "Bitcoin liquidation heatmaps show liquidity clusters $65.5k-$66.5k (X)"], "event_risk": "low"}, "age_s": 13.9}`

recent_decisions `[{"action": "no_trade", "p_up": 0.495, "confidence": 0.0, "outcome_up": false, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_up", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.498, "confidence": 0.0, "outcome_up": true, "view_correct": false, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_down", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.49, "confidence": 0.0, "outcome_up": false, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_down", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.492, "confidence": 0.0, "outcome_up": true, "view_correct": false, "context": {"hurst_regime": "insufficient_data", "markov_state": "chop_noise", "tt`

## 9. Grok signal intel (analyst + predictor + budget)

budget `{'daily_usd_cap': 20.0, 'est_usd_per_call': 0.02, 'spent_today_usd': 0.04, 'calls_today': 2, 'per_feature_hourly': {'predictor': 120, 'analyst': 6, 'overlay': 20, 'decider': 60, 'news': 30}}`

predictor_B `{'enabled': True, 'observe_only': True, 'affects_trading': False, 'off_hot_path': True, 'requested': 223, 'predicted': 220, 'errors': 3, 'skipped_budget': 0, 'scored': 204, 'accuracy': 0.5098, 'brier': 0.2554, 'pending': 0, 'note': 'observe-only Grok P(up) per signal; graded vs realized BTC move before it could ever be trusted; never places/sizes/bypasses a trade.'}`

analyst_A last_note `{"summary": "With n=50 settled trades, DOWN_WEAK (wr 0.6923), 120-240s TTC (0.6667), range_middle (0.6875), range_bottom (0.7273), mixed MTF (0.6538) and dead volume (0.6471) show win-rates comfortably above breakeven with positive realized pnl and n>=8; trending regime and z-score -1..1 also look stable. Most other buckets remain marginal or negative-EV in practice despite positive avg_ev_after_cost. Overall book is still slightly negative due to small sample and a few toxic sub-buckets.", "working": ["DOWN_WEAK n=13 wr=0.69", "120-240s TTC n=30 wr=0.67", "range_middle n=16 wr=0.69", "range_bottom n=11 wr=0.73", "mixed MTF n=26 wr=0.65", "dead volume n=17 wr=0.65", "bullish supertrend n=21 wr=0.67"], "failing": ["UP_STRONG n=14 wr=0.43", "volume spike n=8 wr=0.125", "range_top n=14 wr=0.29", "<60s TTC n=8 wr=0.125", "UP_WEAK n=8 wr=0.5"], "warnings": ["total n=50 still tiny; many buckets near n=8-11 boundary", "realized pnl negative despite positive avg_ev_after_cost across board", "ignore all n<8 buckets entirely"], "changes_since_last": ["first analysis - no prior baseline"], "focus_next": ["accumulate samples specifically in DOWN_WEAK + 120-240s + range_middle intersection", "t`

## 10. TradingView learning

- **tradingview_alerts_received:** 223
- **tradingview_alerts_valid:** 223
- **tradingview_alerts_rejected:** 0

settled_with_signal 50

best_buckets `[{"dimension": "ttc_bucket", "bucket": "<60s", "n": 8, "win_rate": 0.125, "pnl_usd": -32.0635, "avg_ev_after_cost": 0.168514, "all_reconciled": true}, {"dimension": "vwap_state", "bucket": "below", "n": 16, "win_rate": 0.5, "pnl_usd": -17.1331, "avg_ev_after_cost": 0.143315, "all_reconciled": true}, {"dimension": "htf_bias", "bucket": "bearish", "n": 12, "win_rate": 0.4167, "pnl_usd": -13.9216, "avg_ev_after_cost": 0.140423, "all_reconciled": true}, {"dimension": "volume_state", "bucket": "active", "n": 25, "win_rate": 0.6, "pnl_usd": -4.4526, "avg_ev_after_cost": 0.138888, "all_reconciled": true}, {"dimension": "signal_level", "bucket": "DOWN_WEAK", "n": 13, "win_rate": 0.6923, "pnl_usd": 1.1163, "avg_ev_after_cost": 0.137307, "all_reconciled": true}]`

worst_buckets `[{"dimension": "vwap_state", "bucket": "reclaim", "n": 3, "win_rate": 0.6667, "pnl_usd": -1.6643, "avg_ev_after_cost": 0.078272, "all_reconciled": true}, {"dimension": "volume_state", "bucket": "dead", "n": 17, "win_rate": 0.6471, "pnl_usd": 0.3323, "avg_ev_after_cost": 0.088628, "all_reconciled": true}, {"dimension": "candle_pressure", "bucket": "upper_wick_rejection", "n": 5, "win_rate": 0.8, "pnl_usd": 6.8906, "avg_ev_after_cost": 0.091645, "all_reconciled": true}, {"dimension": "signal_level", "bucket": "UP_STRONG", "n": 14, "win_rate": 0.4286, "pnl_usd": -17.6717, "avg_ev_after_cost": 0.091713, "all_reconciled": true}, {"dimension": "bb_state", "bucket": "normal", "n": 4, "win_rate": 0.5, "pnl_usd": -6.1722, "avg_ev_after_cost": 0.092025, "all_reconciled": true}]`

rsi_trend hit_rate 0.4888 (n 223) · pred_acc 0.4057

## 11. Edge signal & readiness

edge_signal `{"enabled": true, "observe_only": true, "report_only": true, "affects_trading": false, "settled": 66, "by_stale_divergence": {"not_stale": {"n": 56, "win_rate": 0.5536, "pnl_usd": -21.4479, "avg_ev_after_cost": 0.099294, "all_reconciled": true}, "already_priced": {"n": 5, "win_rate": 0.4, "pnl_usd": -10.3632, "avg_ev_after_cost": 0.157737, "all_reconciled": true}, "stale_polymarket_up": {"n": 3, "win_rate": 0.3333, "pnl_usd": -8.6709, "avg_ev_after_cost": 0.089161, "all_reconciled": true}, "stale_polymarket_down": {"n": 2, "win_rate": 0.5, "pnl_usd": -4.5055, "avg_ev_after_cost": 0.131644, "all_reconciled": true}}, "by_ttc_bucket": {"240_300s": {"n": 18, "win_rate": 0.3889, "pnl_usd": -22.26`

readiness `{'report_only': True, 'status': 'not_ready', 'ready_to_claim_80pct': False, 'gates': {'accepted_ge_100': True, 'accepted_ge_500': False, 'accepted_ge_1000': False, 'win_rate_ge_80': False, 'positive_net_paper_pnl': False, 'profit_factor_ok': False, 'calibration_error_ok': False, 'max_drawdown_ok': False, 'loss_size_le_win_size': False, 'no_reconciliation_failures': True, 'no_missing_settlement_data': True, 'no_unmodeled_fill_assumptions': True, 'no_safety_bypass': True}, 'metrics': {'accepted': 304, 'win_rate': 0.523, 'net_pnl_usd': -87.245, 'profit_factor': 0.8068, 'calibration_error': 0.231595, 'max_drawdown_usd': 142.5879, 'avg_win_usd': 2.829, 'avg_loss_usd': 3.8448}}`

## 12. Recent paper positions

| window | side | entry_mode | entry | fair | outcome | won | pnl |
|---|---|---|---|---|---|---|---|
| 11:50PM-11:55PM ET | down | grok_explore | 0.22 | 0.7009455406832006 | — | — | None |
| 11:45PM-11:50PM ET | down | grok_explore | 0.5 | 0.6093947182560404 | up | ✗ | -2.5 |
| 11:40PM-11:45PM ET | down | grok_explore | 0.45 | 0.42433897216193917 | up | ✗ | -2.5 |
| 11:35PM-11:40PM ET | down | grok_explore | 0.5 | 0.5015105423406077 | down | ✓ | 2.5 |
| 11:25PM-11:30PM ET | down | grok_explore | 0.37 | 0.5604452508501454 | up | ✗ | -2.5 |
| 11:15PM-11:20PM ET | down | grok_explore | 0.43000000000000005 | 0.5264569428938204 | up | ✗ | -2.5 |
| 11:00PM-11:05PM ET | down | grok_explore | 0.5 | 0.4494325639795902 | down | ✓ | 2.5 |
| 10:55PM-11:00PM ET | down | grok_explore | 0.4799999999999999 | 0.4386728454091663 | down | ✓ | 2.708333 |
| 10:50PM-10:55PM ET | down | grok_explore | 0.4799999999999999 | 0.5139612120827818 | up | ✗ | -2.5 |
| , 2:30PM-2:35PM ET | down | late_window | 0.63 | 0.16871135832232878 | down | ✓ | 2.936508 |
| , 2:15PM-2:20PM ET | down | late_window | 0.63 | 0.2233626380729752 | down | ✓ | 2.936508 |
| , 2:10PM-2:15PM ET | down | standard | 0.21391622262844698 | 0.6655454499273238 | up | ✗ | -5.0 |
| , 2:05PM-2:10PM ET | up | standard | 0.62 | 0.7950185603314788 | down | ✗ | -5.0 |
| , 1:35PM-1:40PM ET | down | standard | 0.34 | 0.5282115331574825 | up | ✗ | -5.0 |
| , 1:15PM-1:20PM ET | down | standard | 0.59 | 0.34934067876195035 | down | ✓ | 3.474576 |

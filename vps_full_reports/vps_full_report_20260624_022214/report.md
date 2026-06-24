# BTC 5-Minute Pulse — FULL Performance Report

_PAPER ONLY. `live_trading_enabled=False` · `global_reconciled=True` · ticks 983._


## 1. Capital & P&L

| metric | value |
|---|---|
| On-hand capital | $432.1 |
| Starting capital | $500.0 |
| Return | -13.58% |
| Open exposure | $5.0 (1 pos) |
| Trades / settled | 386 / 385 |
| Win rate | 0.5325 |
| Win rate up / down | 0.5329 / 0.5322 |
| Realized PnL | $-67.8988 |
| Profit factor | 0.8768 |
| Avg win / avg loss | $3.066 / $3.9827 |
| Max drawdown | $151.7258 |
| Avg PnL/trade | -0.1764 |
| Side counts | {'up': 152, 'down': 233} |
| Settle sources | {'polymarket_resolution': 186, 'rtds_chainlink_proxy': 183} |
| Proxy vs official | {'both': 185, 'agree': 179, 'disagree': 6} |
| EV before/after cost | 0.109656 / 0.103752 |

## 2. Accounting integrity (reconciliation)

- **global_reconciled:** True
- **scope_note:** lifecycle counts are cumulative since canonical accounting began; baseline counts are legacy ledger totals that predate it; ledger/gate totals == baseline + accounted.
- **rejected_before_execution:** 31577

## 3. Candidate lifecycle

created 41927 · terminals `{'accepted': 235, 'rejected': 40137, 'skipped': 1507, 'expired': 0, 'missing_data': 48}`

rejected_by_stage `{'directional': 30022, 'execution_gate': 217, 'selectivity_gate': 1170, 'context_gate': 840, 'grok_decider': 7705, 'research_avoid': 183}`

## 4. Execution gate & calibration

candidates 558 · accepted 341 · rejects `{'wide_spread': 55, 'insufficient_depth': 0, 'negative_ev_after_slippage': 70, 'too_close_to_resolution': 0, 'min_size_or_tick_violation': 6, 'partial_fill_risk': 0, 'missing_market_data': 0, 'stale_orderbook': 0, 'underdog_price_below_floor': 86}`

calibration `{'samples': 385, 'brier': 0.22723, 'log_loss': 0.649423, 'base_rate_up': 0.4935, 'baseline_brier_0_5': 0.25}`

## 5. PnL by bucket (all dimensions)

**pnl_by_confidence_tier:** `{"low": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`
**pnl_by_conviction_bucket:** `{"0.4-0.6": {"n": 1, "win_rate": 1.0, "pnl_usd": 3.1967, "brier": 0.082}, "0.2-0.4": {"n": 1, "win_rate": 0.0, "pnl_usd": -5.0, "brier": 0.4225}}`
**pnl_by_depth_bucket:** `{">=1000": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`
**pnl_by_edge_quality_bucket:** `{"high": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`
**pnl_by_entry_mode:** `{"standard": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`
**pnl_by_half_life_bucket:** `{"<30s": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`
**pnl_by_hurst_regime:** `{"trending": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`
**pnl_by_markov_state:** `{"chop_noise": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`
**pnl_by_spread_bucket:** `{"0.01-0.03": {"n": 1, "win_rate": 1.0, "pnl_usd": 3.1967, "brier": 0.082}, "0.03-0.06": {"n": 1, "win_rate": 0.0, "pnl_usd": -5.0, "brier": 0.4225}}`
**pnl_by_ttc_bucket:** `{"120-240s": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`
**pnl_by_zscore_bucket:** `{"-1..1": {"n": 2, "win_rate": 0.5, "pnl_usd": -1.8033, "brier": 0.2523}}`

## 6. Learned selectivity gate

- **decision_rule:** confidently_below_breakeven
- **confidence_z:** 1.64
- **accepted:** 227
- **rejected:** 1170
- **explored:** 57
| dim | bucket | n | WR | breakeven | WR_upperCI | EV/trade | blocked |
|---|---|---|---|---|---|---|---|
| markov_state | stale_polymarket_up | 80 | 0.4875 | 0.5899 | 0.5781 | -0.7955 | True |
| zscore_bucket | 1..2 | 35 | 0.4 | 0.5194 | 0.5382 | -1.095 | False |
| hurst_regime | insufficient_data | 31 | 0.3871 | 0.486 | 0.534 | -0.9428 | False |
| zscore_bucket | na | 41 | 0.4146 | 0.519 | 0.5422 | -0.9139 | False |
| confidence_tier | high | 186 | 0.5161 | 0.5753 | 0.5756 | -0.4913 | False |
| direction | down | 206 | 0.5194 | 0.5662 | 0.5759 | -0.3919 | False |
| ttc_bucket | 120-240s | 101 | 0.5545 | 0.6006 | 0.6331 | -0.3759 | False |
| spread_bucket | <=0.01 | 287 | 0.5157 | 0.5553 | 0.5637 | -0.3425 | False |

counterfactual `{'replayed': 202, 'trades_rejected': 46, 'losses_avoided': 25, 'pnl_removed_by_rejects': -31.003, 'counterfactual_trades': 156, 'counterfactual_win_rate': 0.5449, 'counterfactual_pnl_usd': -33.0302, 'baseline_trades': 202, 'baseline_win_rate': 0.5248, 'baseline_pnl_usd': -64.0332, 'reject_reasons_by_bucket': {'bad_bucket:markov_state=stale_polymarket_up': 46}, 'note': 'in-sample replay using final accumulated bucket evidence (diagnostic estimate)'}`

## 7. Entry gates (context / late-window / reward-risk)

context_gate enabled=True · blocked 840 · `{'tv_context_volume_spike': 430, 'tv_context_ttc_too_far': 280, 'tv_context_hurst_noise': 130}`

late_window gate=False · verdict insufficient_evidence · LHC `{'n': 15, 'win_rate': 0.5333, 'pnl_usd': -9.8508, 'avg_pnl_usd': -0.6567, 'avg_ev_after_cost': 0.11953}` · other `{'n': 92, 'win_rate': 0.5435, 'pnl_usd': 10.3649, 'avg_pnl_usd': 0.1127, 'avg_ev_after_cost': 0.095275}`

## 8. Grok Decision Engine (decides; bot executes)

- **mode:** follow
- **affects_trading:** True
- **decided:** 387
- **errors:** 4
- **skipped_budget:** 0
- **avg_latency_s:** 5.882
- **graded_directional:** 1
- **direction_accuracy:** 1.0
- **brier:** 0.1444
- **views_graded:** 335
- **view_accuracy:** 0.5045
- **view_brier:** 0.2534
- **abstains:** 377
- **follow_fraction:** 1.0
- **explore_rate:** 0.5
- **adaptive_enabled:** True

by_action `{'no_trade': {'n': 377, 'direction_accuracy': None, 'pnl_usd': 0.0}, 'up': {'n': 1, 'direction_accuracy': 1.0, 'pnl_usd': 0.0}}`

adaptive_policy_counts `{'exploit': 0, 'explore': 0, 'avoid': 0}`

aggression `{'aggression': 0.55, 'min': 0.0, 'max': 1.0, 'step_up': 0.05, 'step_down': 0.1, 'recent_net_pnl': 25.5716, 'updates': 21, 'note': 'loosens (more explore/looser exploit/larger size) as acted trades profit; tightens on losses; circuit breaker is the hard floor.'}`

accuracy_by_context `{"hurst_regime": {"insufficient_data": {"n": 23, "accuracy": 0.3478}, "trending": {"n": 290, "accuracy": 0.5172}, "noise": {"n": 22, "accuracy": 0.5}}, "markov_state": {"stale_polymarket_up": {"n": 96, "accuracy": 0.5312}, "stale_polymarket_down": {"n": 105, "accuracy": 0.5143}, "chop_noise": {"n": 134, "accuracy": 0.4776}}, "ttc_bucket": {">=240s": {"n": 335, "accuracy": 0.5045}}, "conviction_bucket": {"coinflip": {"n": 334, "accuracy": 0.503}, "lean": {"n": 1, "accuracy": 1.0}}}`

view_edge_candidates `[]`

circuit_breaker `{'tripped': True, 'reason': 'daily_loss_cap', 'consecutive_losses': 0, 'daily_follow_loss_usd': 31.88, 'daily_loss_cap_usd': 30.0, 'trips': 42, 'cooldown_remaining_s': 843.3, 'max_consecutive_losses': 4, 'max_latency_s': 20.0}`

news_digest `{"enabled": true, "interval_s": 300.0, "calls": 380, "errors": 2, "skipped_budget": 0, "latest": {"sentiment": "neutral", "confidence": 0.55, "headlines": ["BTC testing $62k support amid recent $171M liquidation wave (hours ago)", "Spot BTC ETFs saw $68M outflows on June 22 (recent flow update)", "No major macro prints, regulatory headlines, or large liquidations in last 30 min"], "event_risk": "low"}, "age_s": 200.5}`

recent_decisions `[{"action": "no_trade", "p_up": 0.49, "confidence": 0.0, "outcome_up": true, "view_correct": false, "context": {"hurst_regime": "trending", "markov_state": "chop_noise", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.51, "confidence": 0.0, "outcome_up": true, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_up", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.505, "confidence": 0.0, "outcome_up": true, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_up", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.51, "confidence": 0.0, "outcome_up": false, "view_correct": false, "context": {"hurst_regime": "trending", "markov_state": "chop_noise", "ttc_bucket": ">=240s", "con`

## 9. Grok signal intel (analyst + predictor + budget)

budget `{'daily_usd_cap': 20.0, 'est_usd_per_call': 0.02, 'spent_today_usd': 1.26, 'calls_today': 63, 'per_feature_hourly': {'predictor': 120, 'analyst': 6, 'overlay': 20, 'decider': 60, 'news': 30}}`

predictor_B `{'enabled': True, 'observe_only': True, 'affects_trading': False, 'off_hot_path': True, 'requested': 424, 'predicted': 419, 'errors': 3, 'skipped_budget': 0, 'scored': 390, 'accuracy': 0.5179, 'brier': 0.2528, 'pending': 0, 'note': 'observe-only Grok P(up) per signal; graded vs realized BTC move before it could ever be trusted; never places/sizes/bypasses a trade.'}`

analyst_A last_note `{"summary": "DOWN_STRONG and v4 signals in trending regimes with z-score -1..1, dead volume, range_bottom, and 60-240s TTC show confirmed positive EV (avg_ev_after_cost ~0.10-0.13) and win-rates above breakeven with n>=14-96; overall sample remains small (127 trades) with mixed realized pnl due to variance and UP-side underperformance. Most other buckets (e.g., UP_WEAK, volume spike, <60s TTC, range_top) are noise or negative with insufficient samples after n<8 filter. No material change from prior (first analysis) as evidence is initial.", "working": ["DOWN_STRONG (n=68, wr=0.588, +16.6 pnl)", "v4 composite (n=96, wr=0.5625, +5.45 pnl)", "zscore -1..1 (n=84, wr=0.607, +15.2 pnl)", "dead volume (n=52, wr=0.635, +30.3 pnl)", "range_bottom (n=39, wr=0.769, +58.6 pnl)", "bearish_aligned mtf (n=44, wr=0.591, +25.5 pnl)", "60-120s and >=240s TTC (n=14-73, positive pnl)"], "failing": ["UP_WEAK/UP_STRONG (negative pnl, wr<=0.52)", "volume spike (n=14, wr=0.286, -36 pnl)", "<60s TTC (n=20, wr=0.3, -46 pnl)", "range_top (n=24, wr=0.417, -30 pnl)", "v3 composite (n=31, -20.8 pnl)"], "warnings": ["Total realized pnl negative despite positive avg_ev; high variance in small n buckets", "Strong `

## 10. TradingView learning

- **tradingview_alerts_received:** 424
- **tradingview_alerts_valid:** 424
- **tradingview_alerts_rejected:** 0

settled_with_signal 127

best_buckets `[{"dimension": "zscore_bucket", "bucket": "<=-2", "n": 7, "win_rate": 0.4286, "pnl_usd": -6.5929, "avg_ev_after_cost": 0.152993, "all_reconciled": true}, {"dimension": "cvd_state", "bucket": "buy_pressure", "n": 8, "win_rate": 0.5, "pnl_usd": 2.1593, "avg_ev_after_cost": 0.1347, "all_reconciled": true}, {"dimension": "ttc_bucket", "bucket": "<60s", "n": 20, "win_rate": 0.3, "pnl_usd": -46.444, "avg_ev_after_cost": 0.132953, "all_reconciled": true}, {"dimension": "bb_state", "bucket": "expansion_up", "n": 11, "win_rate": 0.4545, "pnl_usd": -0.1134, "avg_ev_after_cost": 0.13214, "all_reconciled": true}, {"dimension": "candle_pressure", "bucket": "lower_wick_rejection", "n": 17, "win_rate": 0.7059, "pnl_usd": 24.7123, "avg_ev_after_cost": 0.127022, "all_reconciled": true}]`

worst_buckets `[{"dimension": "cvd_state", "bucket": "sell_pressure", "n": 6, "win_rate": 0.6667, "pnl_usd": 3.8494, "avg_ev_after_cost": 0.044817, "all_reconciled": true}, {"dimension": "liquidation_spike", "bucket": "True", "n": 3, "win_rate": 0.6667, "pnl_usd": 1.3405, "avg_ev_after_cost": 0.076747, "all_reconciled": true}, {"dimension": "hurst_regime", "bucket": "noise", "n": 3, "win_rate": 0.3333, "pnl_usd": -6.5254, "avg_ev_after_cost": 0.07809, "all_reconciled": true}, {"dimension": "vwap_state", "bucket": "reclaim", "n": 3, "win_rate": 0.6667, "pnl_usd": -1.6643, "avg_ev_after_cost": 0.078272, "all_reconciled": true}, {"dimension": "mtf_alignment", "bucket": "neutral", "n": 16, "win_rate": 0.5, "pnl_usd": -22.7739, "avg_ev_after_cost": 0.080786, "all_reconciled": true}]`

rsi_trend hit_rate 0.5035 (n 423) · pred_acc 0.4507

## 11. Loop engineering (maker-checker / lessons / loops / research)

**Verifier (independent Claude maker-checker):** `{"enabled": true, "verified": 243, "approvals": 218, "vetoes": 25, "errors": 10, "approve_rate": 0.8971, "approved_acted_settled": {"n": 7, "win_rate": 0.5714, "pnl_usd": 11.1176}, "avg_latency_s": 4.563}`

**Research meta-loop:** `{"enabled": true, "calls": 42, "auto_apply": true, "lessons_added": 205}`

- research summary: Bot shows 53.4% win rate on 384 settled trades with -$62.90 PnL and 0.88 profit factor—losses outsize wins by 30%. TradingView DOWN signals exhibit 60% hit rate (90 samples), but overall the strategy bleeds on execution costs and adverse selection. No context shows robust, sample-backed edge above costs.

**Lessons (compounding rules):** count 214
- [`research`] markov_state=stale_polymarket_down (n=2, 100% win, +$6.07) warrants targeted exploration (target n=30)
- [`research`] TradingView DOWN 60% vs UP 48.6% hit—direction matters more than aggregate 56.8%
- [`research`] 60-70% bucket: 5 samples, 20% empirical up—overconfident model, reject until 30+ samples
- [`research`] EV drop 11.0%→10.4% plus loss>win means sub-1% net edge insufficient for 5-min noise
- [`research`] 232 DOWN vs 151 UP fills, DOWN 53.4% win vs UP 53.0%—DOWN slight edge, UP neutral
- [`research`] TradingView DOWN signals show 60% hit rate (n=90) vs 50% UP (n=36); isolate DOWN-only flow if execution costs can be reduced below 0.5% per round-trip
- [`research`] 53.4% win rate is negated by 1.30x loss:win ratio; never trade unless avg_loss <= 1.05 * avg_win, enforced pre-execution
- [`research`] hurst_regime=trending shows n=1 win but zero statistical power; require min 30 samples before trusting any regime bucket
- [`research`] 83 rejects for underdog_price_below_floor vs 58 for negative_ev; floor may be blocking best DOWN opportunities—test 0.45-0.48 range
- [`research`] Brier 0.227 vs baseline 0.25 and edge_model shows reasonable calibration, but profits fail; edge exists in prediction but dies in execution—focus on cost reduction, not signal tuning

**Sub-loops:** data_ingestion, execution, heartbeat, lessons, news, research_meta, risk_monitor, signal_generation, verifier

## 12. Edge signal & readiness

edge_signal `{"enabled": true, "observe_only": true, "report_only": true, "affects_trading": false, "settled": 147, "by_stale_divergence": {"not_stale": {"n": 126, "win_rate": 0.5873, "pnl_usd": 18.4444, "avg_ev_after_cost": 0.094768, "all_reconciled": true}, "already_priced": {"n": 12, "win_rate": 0.3333, "pnl_usd": -20.3432, "avg_ev_after_cost": 0.166486, "all_reconciled": true}, "stale_polymarket_up": {"n": 4, "win_rate": 0.25, "pnl_usd": -13.6709, "avg_ev_after_cost": 0.136871, "all_reconciled": true}, "stale_polymarket_down": {"n": 5, "win_rate": 0.4, "pnl_usd": -10.0715, "avg_ev_after_cost": 0.103074, "all_reconciled": true}}, "by_ttc_bucket": {"240_300s": {"n": 35, "win_rate": 0.5143, "pnl_usd": 0`

**CEX-lead latency edge** (grades CEX-implied P(up) vs the MARKET price): mode `shadow` · affects_trading False · signals_seen 9461 · graded 154 · drove 0 · any_proven (beats market) **False**
| divergence | n | acc | brier_cex | brier_mkt | beats_mkt | avg_pnl/u | proven |
|---|---|---|---|---|---|---|---|
| >=0.30 | 145 | 0.4966 | 0.452 | 0.242 | False | -0.0001 | False |
| ttc=>=0.30|240_300s | 89 | 0.5506 | 0.4193 | 0.241 | False | 0.0574 | False |
| late=>=0.30|indecisive | 65 | 0.5846 | 0.3914 | 0.2432 | False | 0.0945 | False |
| conf=>=0.30|unconfirmed | 53 | 0.5849 | 0.3893 | 0.2468 | False | 0.0975 | False |
| tv=>=0.30|confirmed | 38 | 0.6053 | 0.3599 | 0.2493 | False | 0.1251 | False |
| news=>=0.30|against | 38 | 0.6053 | 0.3735 | 0.2482 | False | 0.1132 | False |
_promotion: n>=min AND wilson_lower(win_rate)>breakeven AND Brier_cex<Brier_market AND avg_pnl>0_

readiness `{'report_only': True, 'status': 'not_ready', 'ready_to_claim_80pct': False, 'gates': {'accepted_ge_100': True, 'accepted_ge_500': False, 'accepted_ge_1000': False, 'win_rate_ge_80': False, 'positive_net_paper_pnl': False, 'profit_factor_ok': False, 'calibration_error_ok': True, 'max_drawdown_ok': False, 'loss_size_le_win_size': False, 'no_reconciliation_failures': True, 'no_missing_settlement_data': True, 'no_unmodeled_fill_assumptions': True, 'no_safety_bypass': True}, 'metrics': {'accepted': 385, 'win_rate': 0.5325, 'net_pnl_usd': -67.8988, 'profit_factor': 0.8768, 'calibration_error': 0.0725, 'max_drawdown_usd': 151.7258, 'avg_win_usd': 3.066, 'avg_loss_usd': 3.9827}}`

## 13. Recent paper positions

| window | side | entry_mode | entry | fair | outcome | won | pnl |
|---|---|---|---|---|---|---|---|
| 10:15PM-10:20PM ET | down | standard | 0.6 | 0.17899636992337015 | — | — | None |
| 10:05PM-10:10PM ET | down | standard | 0.53 | 0.34996994840852347 | up | ✗ | -5.0 |
| , 9:50PM-9:55PM ET | up | standard | 0.6100000000000001 | 0.7136506273282903 | up | ✓ | 3.196721 |
| , 8:55PM-9:00PM ET | up | standard | 0.55 | 0.6313513976340303 | up | ✓ | 4.090909 |
| , 8:45PM-8:50PM ET | up | standard | 0.53 | 0.6035378075268946 | up | ✓ | 4.433962 |
| , 8:25PM-8:30PM ET | up | standard | 0.56 | 0.6386579025498204 | up | ✓ | 3.928571 |
| , 7:55PM-8:00PM ET | up | late_window | 0.66 | 0.8095601906883138 | up | ✓ | 2.575758 |
| , 7:05PM-7:10PM ET | down | standard | 0.7 | 0.11507697323675237 | down | ✓ | 2.142857 |
| , 6:50PM-6:55PM ET | down | standard | 0.52 | 0.33040189860002006 | up | ✗ | -5.0 |
| , 6:40PM-6:45PM ET | down | late_window | 0.6100000000000001 | 0.20297387782593398 | down | ✓ | 3.196721 |
| , 5:45PM-5:50PM ET | up | late_window | 0.56 | 0.7876938765338629 | up | ✓ | 3.928571 |
| , 2:35PM-2:40PM ET | down | standard | 0.54 | 0.35464412745446516 | down | ✓ | 4.259259 |
| , 2:25PM-2:30PM ET | down | standard | 0.52 | 0.3193053052773396 | down | ✓ | 4.615385 |
| 11:15AM-11:20AM ET | down | standard | 0.6100000000000001 | 0.19427170985707087 | down | ✓ | 3.196721 |
| 11:10AM-11:15AM ET | down | standard | 0.44 | 0.49678851666380386 | up | ✗ | -5.0 |

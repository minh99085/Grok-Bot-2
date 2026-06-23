# BTC 5-Minute Pulse — FULL Performance Report

_PAPER ONLY. `live_trading_enabled=False` · `global_reconciled=True` · ticks 36._


## 1. Capital & P&L

| metric | value |
|---|---|
| On-hand capital | $422.83 |
| Starting capital | $500.0 |
| Return | -15.43% |
| Open exposure | $0.0 (0 pos) |
| Trades / settled | 365 / 365 |
| Win rate | 0.5288 |
| Win rate up / down | 0.5286 / 0.5289 |
| Realized PnL | $-77.1701 |
| Profit factor | 0.8558 |
| Avg win / avg loss | $3.0014 / $3.9353 |
| Max drawdown | $146.5066 |
| Avg PnL/trade | -0.2114 |
| Side counts | {'up': 140, 'down': 225} |
| Settle sources | {'polymarket_resolution': 172, 'rtds_chainlink_proxy': 177} |
| Proxy vs official | {'both': 171, 'agree': 165, 'disagree': 6} |
| EV before/after cost | 0.112084 / 0.106385 |

## 2. Accounting integrity (reconciliation)

- **global_reconciled:** True
- **scope_note:** lifecycle counts are cumulative since canonical accounting began; baseline counts are legacy ledger totals that predate it; ledger/gate totals == baseline + accounted.
- **rejected_before_execution:** 21823

## 3. Candidate lifecycle

created 31154 · terminals `{'accepted': 214, 'rejected': 29780, 'skipped': 1124, 'expired': 0, 'missing_data': 36}`

rejected_by_stage `{'directional': 20663, 'execution_gate': 55, 'selectivity_gate': 935, 'context_gate': 422, 'grok_decider': 7705}`

## 4. Execution gate & calibration

candidates 375 · accepted 320 · rejects `{'wide_spread': 13, 'insufficient_depth': 0, 'negative_ev_after_slippage': 42, 'too_close_to_resolution': 0, 'min_size_or_tick_violation': 0, 'partial_fill_risk': 0, 'missing_market_data': 0, 'stale_orderbook': 0}`

calibration `{'samples': 365, 'brier': 0.230598, 'log_loss': 0.65766, 'base_rate_up': 0.4932, 'baseline_brier_0_5': 0.25}`

## 5. PnL by bucket (all dimensions)


## 6. Learned selectivity gate

- **decision_rule:** confidently_below_breakeven
- **confidence_z:** 1.64
- **accepted:** 48
- **rejected:** 935
- **explored:** 53
| dim | bucket | n | WR | breakeven | WR_upperCI | EV/trade | blocked |
|---|---|---|---|---|---|---|---|
| markov_state | stale_polymarket_up | 80 | 0.4875 | 0.5899 | 0.5781 | -0.7955 | True |
| zscore_bucket | 1..2 | 34 | 0.4118 | 0.5188 | 0.5516 | -0.9798 | False |
| hurst_regime | insufficient_data | 31 | 0.3871 | 0.486 | 0.534 | -0.9428 | False |
| zscore_bucket | na | 41 | 0.4146 | 0.519 | 0.5422 | -0.9139 | False |
| confidence_tier | high | 185 | 0.5189 | 0.5751 | 0.5785 | -0.4668 | False |
| zscore_bucket | -1..1 | 160 | 0.5062 | 0.558 | 0.5704 | -0.4528 | False |
| markov_state | chop_noise | 114 | 0.4474 | 0.4925 | 0.5241 | -0.4452 | False |
| ttc_bucket | 120-240s | 93 | 0.5484 | 0.6011 | 0.6305 | -0.429 | False |

counterfactual `{'replayed': 200, 'trades_rejected': 51, 'losses_avoided': 27, 'pnl_removed_by_rejects': -31.6862, 'counterfactual_trades': 149, 'counterfactual_win_rate': 0.5369, 'counterfactual_pnl_usd': -41.8214, 'baseline_trades': 200, 'baseline_win_rate': 0.52, 'baseline_pnl_usd': -73.5076, 'reject_reasons_by_bucket': {'bad_bucket:markov_state=stale_polymarket_up': 51}, 'note': 'in-sample replay using final accumulated bucket evidence (diagnostic estimate)'}`

## 7. Entry gates (context / late-window / reward-risk)

context_gate enabled=True · blocked 422 · `{'tv_context_volume_spike': 220, 'tv_context_ttc_too_far': 174, 'tv_context_hurst_noise': 28}`

late_window gate=False · verdict insufficient_evidence · LHC `{'n': 11, 'win_rate': 0.4545, 'pnl_usd': -14.5519, 'avg_pnl_usd': -1.3229, 'avg_ev_after_cost': 0.124659}` · other `{'n': 76, 'win_rate': 0.5395, 'pnl_usd': 5.7946, 'avg_pnl_usd': 0.0762, 'avg_ev_after_cost': 0.100583}`

## 8. Grok Decision Engine (decides; bot executes)

- **mode:** follow
- **affects_trading:** True
- **decided:** 234
- **errors:** 4
- **skipped_budget:** 0
- **avg_latency_s:** 5.761
- **graded_directional:** 0
- **direction_accuracy:** None
- **brier:** None
- **views_graded:** 183
- **view_accuracy:** 0.5137
- **view_brier:** 0.2525
- **abstains:** 226
- **follow_fraction:** 1.0
- **explore_rate:** 0.5
- **adaptive_enabled:** True

by_action `{'no_trade': {'n': 226, 'direction_accuracy': None, 'pnl_usd': 0.0}}`

adaptive_policy_counts `{'exploit': 0, 'explore': 0, 'avoid': 0}`

aggression `{'aggression': 0.55, 'min': 0.0, 'max': 1.0, 'step_up': 0.05, 'step_down': 0.1, 'recent_net_pnl': 25.5716, 'updates': 21, 'note': 'loosens (more explore/looser exploit/larger size) as acted trades profit; tightens on losses; circuit breaker is the hard floor.'}`

accuracy_by_context `{"hurst_regime": {"insufficient_data": {"n": 14, "accuracy": 0.2857}, "trending": {"n": 163, "accuracy": 0.5399}, "noise": {"n": 6, "accuracy": 0.3333}}, "markov_state": {"stale_polymarket_up": {"n": 52, "accuracy": 0.5385}, "stale_polymarket_down": {"n": 64, "accuracy": 0.5312}, "chop_noise": {"n": 67, "accuracy": 0.4776}}, "ttc_bucket": {">=240s": {"n": 183, "accuracy": 0.5137}}, "conviction_bucket": {"coinflip": {"n": 182, "accuracy": 0.511}, "lean": {"n": 1, "accuracy": 1.0}}}`

view_edge_candidates `[]`

circuit_breaker `{'tripped': True, 'reason': 'daily_loss_cap', 'consecutive_losses': 0, 'daily_follow_loss_usd': 31.88, 'daily_loss_cap_usd': 30.0, 'trips': 17, 'cooldown_remaining_s': 1267.8, 'max_consecutive_losses': 4, 'max_latency_s': 20.0}`

news_digest `{"enabled": true, "interval_s": 300.0, "calls": 230, "errors": 2, "skipped_budget": 0, "latest": {"sentiment": "bearish", "confidence": 0.65, "headlines": ["Ongoing US spot BTC ETF outflows (recent sessions -$68M to -$90M; $6.35B over 30 days)", "$161K BTC long liquidated at ~$62,205", "Macro storm: Fed hawkish, BOJ rate hike signals, risk assets dumping (BTC -3.5%)", "BTC consolidating below $63K with bearish tilt; PCE inflation watch"], "event_risk": "low"}, "age_s": 113.4}`

recent_decisions `[{"action": "no_trade", "p_up": 0.48, "confidence": 0.0, "outcome_up": true, "view_correct": false, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_down", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.485, "confidence": 0.0, "outcome_up": false, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "chop_noise", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.48, "confidence": 0.0, "outcome_up": false, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "chop_noise", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "no_trade", "p_up": 0.485, "confidence": 0.0, "outcome_up": false, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_up", "ttc_bucket": ">=240s", `

## 9. Grok signal intel (analyst + predictor + budget)

budget `{'daily_usd_cap': 20.0, 'est_usd_per_call': 0.02, 'spent_today_usd': 0.06, 'calls_today': 3, 'per_feature_hourly': {'predictor': 120, 'analyst': 6, 'overlay': 20, 'decider': 60, 'news': 30}}`

predictor_B `{'enabled': True, 'observe_only': True, 'affects_trading': False, 'off_hot_path': True, 'requested': 327, 'predicted': 324, 'errors': 3, 'skipped_budget': 0, 'scored': 301, 'accuracy': 0.5249, 'brier': 0.252, 'pending': 0, 'note': 'observe-only Grok P(up) per signal; graded vs realized BTC move before it could ever be trusted; never places/sizes/bypasses a trade.'}`

analyst_A last_note `{"summary": "DOWN_STRONG (n=62, wr=0.597) and range_bottom (n=32, wr=0.781) show confirmed positive EV with n>=8 and wr above breakeven after costs; overall sample remains small (107 trades) with net negative realized pnl driven by UP and short-ttc buckets. Most other slices are either n<8 or show mixed/noisy results (e.g., volume_spike, zscore 1..2).", "working": ["DOWN_STRONG (n=62, wr=0.597, +19.5 pnl)", "range_bottom (n=32, wr=0.781, +51.2 pnl)", "bearish_aligned mtf (n=43, wr=0.581, +21.2 pnl)", ">=240s ttc (n=20, wr=0.6, +12.2 pnl)", "dead volume (n=45, wr=0.6, +12.2 pnl)"], "failing": ["UP direction (n=24, wr=0.458, -30.1 pnl)", "<60s ttc (n=13, wr=0.231, -41.9 pnl)", "range_top (n=18, wr=0.333, -35.0 pnl)", "volume_spike (n=14, wr=0.286, -36.3 pnl)", "zscore 1..2 (n=8, wr=0.25, -28.2 pnl)"], "warnings": ["Total realized pnl still negative (-24.6) despite positive avg_ev in most buckets; small n and possible selection bias in accepted trades only."], "changes_since_last": ["First analysis; no prior baseline."], "focus_next": ["Accumulate samples in range_bottom + DOWN_STRONG intersection", "Track ttc>=120s and dead-volume slices for stability", "Monitor whether UP_weak and m`

## 10. TradingView learning

- **tradingview_alerts_received:** 327
- **tradingview_alerts_valid:** 327
- **tradingview_alerts_rejected:** 0

settled_with_signal 107

best_buckets `[{"dimension": "ttc_bucket", "bucket": "<60s", "n": 13, "win_rate": 0.2308, "pnl_usd": -41.9223, "avg_ev_after_cost": 0.148731, "all_reconciled": true}, {"dimension": "spread_bucket", "bucket": "0.01-0.03", "n": 8, "win_rate": 0.625, "pnl_usd": 0.6709, "avg_ev_after_cost": 0.147914, "all_reconciled": true}, {"dimension": "candle_pressure", "bucket": "lower_wick_rejection", "n": 14, "win_rate": 0.7857, "pnl_usd": 25.0064, "avg_ev_after_cost": 0.127655, "all_reconciled": true}, {"dimension": "hurst_regime", "bucket": "insufficient_data", "n": 6, "win_rate": 0.5, "pnl_usd": 4.7503, "avg_ev_after_cost": 0.126917, "all_reconciled": true}, {"dimension": "volume_state", "bucket": "active", "n": 48, "win_rate": 0.6042, "pnl_usd": -0.4821, "avg_ev_after_cost": 0.119826, "all_reconciled": true}]`

worst_buckets `[{"dimension": "liquidation_spike", "bucket": "True", "n": 3, "win_rate": 0.6667, "pnl_usd": 1.3405, "avg_ev_after_cost": 0.076747, "all_reconciled": true}, {"dimension": "hurst_regime", "bucket": "noise", "n": 3, "win_rate": 0.3333, "pnl_usd": -6.5254, "avg_ev_after_cost": 0.07809, "all_reconciled": true}, {"dimension": "vwap_state", "bucket": "reclaim", "n": 3, "win_rate": 0.6667, "pnl_usd": -1.6643, "avg_ev_after_cost": 0.078272, "all_reconciled": true}, {"dimension": "range_state", "bucket": "breakout_up", "n": 5, "win_rate": 0.6, "pnl_usd": -4.8198, "avg_ev_after_cost": 0.088722, "all_reconciled": true}, {"dimension": "candle_pressure", "bucket": "upper_wick_rejection", "n": 9, "win_rate": 0.6667, "pnl_usd": 1.188, "avg_ev_after_cost": 0.089353, "all_reconciled": true}]`

rsi_trend hit_rate 0.5153 (n 326) · pred_acc 0.464

## 11. Loop engineering (maker-checker / lessons / loops / research)

**Verifier (independent Claude maker-checker):** `{"enabled": true, "verified": 101, "approvals": 96, "vetoes": 5, "errors": 1, "approve_rate": 0.9505, "approved_acted_settled": {"n": 7, "win_rate": 0.5714, "pnl_usd": 11.1176}, "avg_latency_s": 4.717}`

**Research meta-loop:** `{"enabled": true, "calls": 17, "auto_apply": false, "lessons_added": 98}`

- research summary: The bot shows no statistically significant edge across 363 settled trades: 52.6% win rate, -$85 PnL, profit factor 0.84, and calibration error (Brier 0.23) near random baseline (0.25). Most contexts are losing or coin-flip. The only positive signals are small-sample anomalies (zscore -2..-1: n=4, 75% WR; noise regime: n=1, 100% WR) that lack statistical power and likely reflect noise rather than edge.

**Lessons (compounding rules):** count 106
- [`research`] stale_polymarket_down n=14 71%WR +$12 is noise; no mechanism for stale orderbook → direction edge
- [`research`] zscore -2..-1 n=4 positive is too small; do not chase mean-reversion without n>=30 and stable profit factor
- [`research`] trending (n=36) and noise (n=1) regimes both near breakeven; Hurst not predictive of edge in 5-min BTC
- [`research`] conviction <0.2 lost -$24 on n=9 22%WR; model uncertainty is informative—respect it
- [`research`] edge_quality:high n=34 50%WR -$21;LabVIEW feature scoring does not predict realized edge
- [`research`] 360 trades, all major slices losing or coin-flip; no context shows repeatable alpha above execution costs
- [`research`] 5-minute BTC direction prediction at 52.6% WR over 363 samples confirms near-market efficiency; do not assume edge exists without >>55% WR and positive PnL over n≥200
- [`research`] Ignore any bucket with n<20: zscore -2..-1 (n=4, 75% WR) and noise regime (n=1, 100% WR) are statistically meaningless and likely regression artifacts
- [`research`] Brier score 0.23 vs baseline 0.25 is only marginally better than random; calibration alone does not imply profitability in directional betting
- [`research`] Avg loss $3.94 > avg win $2.99 at 52.6% WR mathematically guarantees losses; must achieve ≥57% WR to break even at this payoff ratio

**Sub-loops:** data_ingestion, execution, heartbeat, lessons, news, research_meta, risk_monitor, signal_generation, verifier

## 12. Edge signal & readiness

edge_signal `{"enabled": true, "observe_only": true, "report_only": true, "affects_trading": false, "settled": 127, "by_stale_divergence": {"not_stale": {"n": 110, "win_rate": 0.5636, "pnl_usd": -10.8269, "avg_ev_after_cost": 0.099987, "all_reconciled": true}, "already_priced": {"n": 11, "win_rate": 0.3636, "pnl_usd": -15.3432, "avg_ev_after_cost": 0.156639, "all_reconciled": true}, "stale_polymarket_up": {"n": 3, "win_rate": 0.3333, "pnl_usd": -8.6709, "avg_ev_after_cost": 0.089161, "all_reconciled": true}, "stale_polymarket_down": {"n": 3, "win_rate": 0.6667, "pnl_usd": -0.0715, "avg_ev_after_cost": 0.156542, "all_reconciled": true}}, "by_ttc_bucket": {"240_300s": {"n": 35, "win_rate": 0.5143, "pnl_usd`

**CEX-lead latency edge** (grades CEX-implied P(up) vs the MARKET price): mode `shadow` · affects_trading False · signals_seen 126 · graded 2 · drove 0 · any_proven (beats market) **False**
| divergence | n | acc | brier_cex | brier_mkt | beats_mkt | avg_pnl/u | proven |
|---|---|---|---|---|---|---|---|
| >=0.30 | 1 | 1.0 | 0.0188 | 0.2256 | True | 0.475 | False |
| 0.15-0.30 | 1 | 1.0 | 0.2337 | 0.4556 | True | 0.675 | False |
_promotion: n>=min AND wilson_lower(win_rate)>breakeven AND Brier_cex<Brier_market AND avg_pnl>0_

readiness `{'report_only': True, 'status': 'not_ready', 'ready_to_claim_80pct': False, 'gates': {'accepted_ge_100': True, 'accepted_ge_500': False, 'accepted_ge_1000': False, 'win_rate_ge_80': False, 'positive_net_paper_pnl': False, 'profit_factor_ok': False, 'calibration_error_ok': False, 'max_drawdown_ok': False, 'loss_size_le_win_size': False, 'no_reconciliation_failures': True, 'no_missing_settlement_data': True, 'no_unmodeled_fill_assumptions': True, 'no_safety_bypass': True}, 'metrics': {'accepted': 365, 'win_rate': 0.5288, 'net_pnl_usd': -77.1701, 'profit_factor': 0.8558, 'calibration_error': 0.230598, 'max_drawdown_usd': 146.5066, 'avg_win_usd': 3.0014, 'avg_loss_usd': 3.9353}}`

## 13. Recent paper positions

| window | side | entry_mode | entry | fair | outcome | won | pnl |
|---|---|---|---|---|---|---|---|
| , 9:25AM-9:30AM ET | down | standard | 0.7 | 0.11973152022954285 | down | ✓ | 2.142857 |
| , 9:20AM-9:25AM ET | down | standard | 0.47000000000000003 | 0.46509388252257666 | down | ✓ | 5.638298 |
| , 9:15AM-9:20AM ET | down | standard | 0.77 | 0.1563527223246346 | down | ✓ | 1.493506 |
| , 9:10AM-9:15AM ET | down | standard | 0.7 | 0.2304289547323075 | up | ✗ | -5.0 |
| , 9:05AM-9:10AM ET | down | standard | 0.39 | 0.545432240039216 | down | ✓ | 7.820513 |
| , 8:45AM-8:50AM ET | down | standard | 0.7 | 0.18577194133862882 | down | ✓ | 2.142857 |
| , 8:25AM-8:30AM ET | down | standard | 0.65 | 0.2550272848360117 | up | ✗ | -5.0 |
| , 8:00AM-8:05AM ET | up | standard | 0.76 | 0.8514458949074138 | down | ✗ | -5.0 |
| , 7:55AM-8:00AM ET | up | late_window | 0.6100000000000001 | 0.8116603611364213 | up | ✓ | 3.196721 |
| , 7:50AM-7:55AM ET | down | standard | 0.68 | 0.22566537875815953 | up | ✗ | -5.0 |
| , 7:15AM-7:20AM ET | down | late_window | 0.029999999999999995 | 0.9079850364131508 | up | ✗ | -5.0 |
| , 7:05AM-7:10AM ET | down | standard | 0.47000000000000003 | 0.4047362461789197 | up | ✗ | -5.0 |
| , 6:50AM-6:55AM ET | down | standard | 0.72 | 0.21140242149811933 | down | ✓ | 1.944444 |
| , 6:35AM-6:40AM ET | down | standard | 0.22999999999999998 | 0.5859542746897715 | up | ✗ | -5.0 |
| , 6:30AM-6:35AM ET | down | standard | 0.74 | 0.16975893701184458 | down | ✓ | 1.756757 |

# BTC 5-Minute Pulse — FULL Performance Report

_PAPER ONLY. `live_trading_enabled=False` · `global_reconciled=True` · ticks 229._


## 1. Capital & P&L

| metric | value |
|---|---|
| On-hand capital | $500.0 |
| Starting capital | $500.0 |
| Return | 0.0% |
| Open exposure | $0.0 (0 pos) |
| Trades / settled | 0 / 0 |
| Win rate | None |
| Win rate up / down | None / None |
| Realized PnL | $0.0 |
| Profit factor | None |
| Avg win / avg loss | $None / $None |
| Max drawdown | $0.0 |
| Avg PnL/trade | None |
| Side counts | {'up': 0, 'down': 0} |
| Settle sources | {'polymarket_resolution': 0, 'rtds_chainlink_proxy': 0} |
| Proxy vs official | {'both': 0, 'agree': 0, 'disagree': 0} |
| EV before/after cost | None / None |

## 2. Accounting integrity (reconciliation)

- **global_reconciled:** True
- **scope_note:** lifecycle counts are cumulative since canonical accounting began; baseline counts are legacy ledger totals that predate it; ledger/gate totals == baseline + accounted.
- **rejected_before_execution:** 765

## 3. Candidate lifecycle

created 1015 · terminals `{'accepted': 0, 'rejected': 745, 'skipped': 263, 'expired': 0, 'missing_data': 7}`

rejected_by_stage `{'directional': 495, 'execution_gate': 0, 'context_gate': 62, 'directional_allowlist': 188}`

## 4. Execution gate & calibration

candidates 0 · accepted 0 · rejects `{'wide_spread': 0, 'insufficient_depth': 0, 'negative_ev_after_slippage': 0, 'too_close_to_resolution': 0, 'min_size_or_tick_violation': 0, 'partial_fill_risk': 0, 'missing_market_data': 0, 'stale_orderbook': 0, 'underdog_price_below_floor': 0}`

calibration `{'samples': 0, 'brier': None, 'log_loss': None, 'base_rate_up': None, 'baseline_brier_0_5': 0.25}`

## 5. PnL by bucket (all dimensions)


## 6. Learned selectivity gate

- **decision_rule:** confidently_below_breakeven
- **confidence_z:** 1.64
- **accepted:** 0
- **rejected:** 0
- **explored:** 0

counterfactual `{'replayed': 0, 'trades_rejected': 0, 'losses_avoided': 0, 'pnl_removed_by_rejects': 0.0, 'counterfactual_trades': 0, 'counterfactual_win_rate': None, 'counterfactual_pnl_usd': 0, 'baseline_trades': 0, 'baseline_win_rate': None, 'baseline_pnl_usd': 0, 'reject_reasons_by_bucket': {}, 'note': 'in-sample replay using final accumulated bucket evidence (diagnostic estimate)'}`

## 7. Entry gates (context / late-window / reward-risk)

context_gate enabled=True · blocked 62 · `{'tv_context_ttc_too_far': 40, 'tv_context_hurst_noise': 22}`

late_window gate=False · verdict insufficient_evidence · LHC `{'n': 0, 'win_rate': None, 'pnl_usd': 0.0, 'avg_pnl_usd': None, 'avg_ev_after_cost': None}` · other `{'n': 0, 'win_rate': None, 'pnl_usd': 0.0, 'avg_pnl_usd': None, 'avg_ev_after_cost': None}`

## 8. Grok Decision Engine (decides; bot executes)

- **mode:** shadow
- **affects_trading:** False
- **decided:** 13
- **errors:** 1
- **skipped_budget:** 0
- **avg_latency_s:** 8.022
- **graded_directional:** 7
- **direction_accuracy:** 0.8571
- **brier:** 0.1324
- **views_graded:** 12
- **view_accuracy:** 0.6667
- **view_brier:** 0.1916
- **abstains:** 5
- **follow_fraction:** 1.0
- **explore_rate:** 0.0
- **adaptive_enabled:** True

by_action `{'no_trade': {'n': 5, 'direction_accuracy': None, 'pnl_usd': 0.0}, 'up': {'n': 7, 'direction_accuracy': 0.8571, 'pnl_usd': 0.0}}`

adaptive_policy_counts `{'exploit': 0, 'explore': 0, 'avoid': 0}`

aggression `{'aggression': 0.0, 'min': 0.0, 'max': 1.0, 'step_up': 0.05, 'step_down': 0.1, 'recent_net_pnl': 0, 'updates': 0, 'note': 'loosens (more explore/looser exploit/larger size) as acted trades profit; tightens on losses; circuit breaker is the hard floor.'}`

accuracy_by_context `{"hurst_regime": {"insufficient_data": {"n": 5, "accuracy": 0.8}, "trending": {"n": 6, "accuracy": 0.5}, "noise": {"n": 1, "accuracy": 1.0}}, "markov_state": {"stale_polymarket_up": {"n": 8, "accuracy": 0.75}, "stale_polymarket_down": {"n": 2, "accuracy": 1.0}, "chop_noise": {"n": 2, "accuracy": 0.0}}, "ttc_bucket": {">=240s": {"n": 12, "accuracy": 0.6667}}, "conviction_bucket": {"coinflip": {"n": 12, "accuracy": 0.6667}}}`

view_edge_candidates `[]`

circuit_breaker `{'tripped': False, 'reason': None, 'consecutive_losses': 0, 'daily_follow_loss_usd': 0.0, 'daily_loss_cap_usd': 30.0, 'trips': 0, 'cooldown_remaining_s': 0, 'max_consecutive_losses': 4, 'max_latency_s': 20.0}`

news_digest `{"enabled": false}`

recent_decisions `[{"action": "no_trade", "p_up": 0.53, "confidence": 0.0, "outcome_up": false, "view_correct": false, "context": {"hurst_regime": "insufficient_data", "markov_state": "stale_polymarket_up", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "up", "p_up": 0.72, "confidence": 0.0, "outcome_up": true, "view_correct": true, "context": {"hurst_regime": "insufficient_data", "markov_state": "stale_polymarket_up", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "up", "p_up": 0.78, "confidence": 0.0, "outcome_up": true, "view_correct": true, "context": {"hurst_regime": "insufficient_data", "markov_state": "stale_polymarket_up", "ttc_bucket": ">=240s", "conviction_bucket": "coinflip"}}, {"action": "up", "p_up": 0.78, "confidence": 0.0, "outcome_up": true, "view_correct": true, "context": {"hurst_regime": "trending", "markov_state": "stale_polymarket_up", "tt`

## 9. Grok signal intel (analyst + predictor + budget)

budget `{'daily_usd_cap': 5.0, 'est_usd_per_call': 0.02, 'spent_today_usd': 0.18, 'calls_today': 9, 'per_feature_hourly': {'predictor': 30, 'analyst': 4, 'overlay': 20, 'decider': 60, 'news': 30}}`

predictor_B `{'enabled': True, 'observe_only': True, 'affects_trading': False, 'off_hot_path': True, 'requested': 0, 'predicted': 0, 'errors': 0, 'skipped_budget': 0, 'scored': 0, 'accuracy': None, 'brier': None, 'pending': 0, 'note': 'observe-only Grok P(up) per signal; graded vs realized BTC move before it could ever be trusted; never places/sizes/bypasses a trade.'}`

analyst_A last_note `{"summary": "After five analyses the bot remains at zero settled trades, signals, and evaluations across every source, so no bucket, regime, or signal meets the n>=8 or min_samples=30 thresholds required for confirmation or rejection. All learned metrics stay at baseline null values with context_gate continuing to block solely on ttc_too_far and hurst_noise. The system is still in its initial observe-only state with no observable patterns.", "working": [], "failing": [], "warnings": ["all evidence buckets empty (n=0)", "no win-rate or EV estimates possible", "observe-only mode prevents any trading authority"], "changes_since_last": ["no new settled trades, signals, or evaluations since prior analysis; all metrics unchanged at baseline null"], "focus_next": ["accumulate settled trades until n>=30 in any regime/z-score/conviction bucket", "monitor context_gate blocks for ttc distribution", "wait for signal_learning and edge_vs_5min_outcome to reach min_evidence"]}`

## 10. TradingView learning

- **tradingview_alerts_received:** 0
- **tradingview_alerts_valid:** 0
- **tradingview_alerts_rejected:** 0

settled_with_signal 0

best_buckets `[]`

worst_buckets `[]`

rsi_trend hit_rate None (n 0) · pred_acc None

## 11. Loop engineering (maker-checker / lessons / loops / research)

**Verifier (independent Claude maker-checker):** `{"enabled": false, "verified": null, "approvals": null, "vetoes": null, "errors": null, "approve_rate": null, "approved_acted_settled": null, "avg_latency_s": null}`

**Research meta-loop:** `{"enabled": false, "calls": null, "auto_apply": null, "lessons_added": null}`

**Lessons (compounding rules):** count 0

**Sub-loops:** arbitrage, data_ingestion, directional, execution, heartbeat, lessons, news, research_meta, risk_monitor, signal_generation, verifier

## 12. Execution-realistic edge (Roan Part IV)

candidates_scored 0 · avg_exec_ev_usd None · avg_kl None

payoff_guards `{'rejected_tiny_upside': 35, 'rejected_bad_reward_to_risk': 45, 'rejected_high_entry_insufficient_margin': 0}`

simplex_diagnostics `{}`

## 13. Edge signal & readiness

edge_signal `{"enabled": true, "observe_only": true, "report_only": true, "affects_trading": false, "settled": 0, "by_stale_divergence": {}, "by_ttc_bucket": {}, "by_ob_pressure": {}}`

**CEX-lead latency edge** (grades CEX-implied P(up) vs the MARKET price): mode `shadow` · affects_trading False · signals_seen 649 · graded 13 · drove 0 · any_proven (beats market) **False**
| divergence | n | acc | brier_cex | brier_mkt | beats_mkt | avg_pnl/u | proven |
|---|---|---|---|---|---|---|---|
| >=0.30 | 13 | 0.6154 | 0.3118 | 0.2622 | False | 0.1412 | False |
| ttc=>=0.30|240_300s | 13 | 0.6154 | 0.3118 | 0.2622 | False | 0.1412 | False |
| tv=>=0.30|unconfirmed | 13 | 0.6154 | 0.3118 | 0.2622 | False | 0.1412 | False |
| news=>=0.30|neutral | 13 | 0.6154 | 0.3118 | 0.2622 | False | 0.1412 | False |
| late=>=0.30|indecisive | 13 | 0.6154 | 0.3118 | 0.2622 | False | 0.1412 | False |
| conf=>=0.30|confirmed | 8 | 0.75 | 0.209 | 0.2651 | True | 0.2812 | False |
_promotion: n>=min AND wilson_lower(win_rate)>breakeven AND Brier_cex<Brier_market AND avg_pnl>0_

**Within-window risk-free arbitrage** (Roan dutch book `up_vwap+down_vwap<1`; P&L SEGREGATED from directional, never blended): detected_actionable 2 · sell_both_detected 352 · executed 2 · settled 2 · open 0 · realized_profit **$16.5179** (risk-free)

readiness `{'report_only': True, 'status': 'not_ready', 'ready_to_claim_80pct': False, 'gates': {'accepted_ge_100': False, 'accepted_ge_500': False, 'accepted_ge_1000': False, 'win_rate_ge_80': False, 'positive_net_paper_pnl': False, 'profit_factor_ok': False, 'calibration_error_ok': False, 'max_drawdown_ok': True, 'loss_size_le_win_size': True, 'no_reconciliation_failures': True, 'no_missing_settlement_data': True, 'no_unmodeled_fill_assumptions': True, 'no_safety_bypass': True}, 'metrics': {'accepted': 0, 'win_rate': None, 'net_pnl_usd': 0.0, 'profit_factor': None, 'calibration_error': None, 'max_drawdown_usd': 0.0, 'avg_win_usd': None, 'avg_loss_usd': None}}`

## 14. Recent paper positions

_no positions_

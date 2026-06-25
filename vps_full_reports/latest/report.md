# BTC 5-Minute Pulse — FULL Performance Report

_PAPER ONLY. `live_trading_enabled=False` · `global_reconciled=True` · ticks 11._


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
- **rejected_before_execution:** 9

## 3. Candidate lifecycle

created 11 · terminals `{'accepted': 0, 'rejected': 8, 'skipped': 1, 'expired': 0, 'missing_data': 2}`

rejected_by_stage `{'directional': 6, 'execution_gate': 0, 'context_gate': 2}`

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

context_gate enabled=True · blocked 2 · `{'tv_context_ttc_too_far': 2}`

late_window gate=False · verdict insufficient_evidence · LHC `{'n': 0, 'win_rate': None, 'pnl_usd': 0.0, 'avg_pnl_usd': None, 'avg_ev_after_cost': None}` · other `{'n': 0, 'win_rate': None, 'pnl_usd': 0.0, 'avg_pnl_usd': None, 'avg_ev_after_cost': None}`

## 8. Grok Decision Engine (decides; bot executes)

- **mode:** shadow
- **affects_trading:** False
- **decided:** 1
- **errors:** 0
- **skipped_budget:** 0
- **avg_latency_s:** 8.501
- **graded_directional:** 0
- **direction_accuracy:** None
- **brier:** None
- **views_graded:** 0
- **view_accuracy:** None
- **view_brier:** None
- **abstains:** 0
- **follow_fraction:** 1.0
- **explore_rate:** 0.0
- **adaptive_enabled:** True

by_action `{}`

adaptive_policy_counts `{'exploit': 0, 'explore': 0, 'avoid': 0}`

aggression `{'aggression': 0.0, 'min': 0.0, 'max': 1.0, 'step_up': 0.05, 'step_down': 0.1, 'recent_net_pnl': 0, 'updates': 0, 'note': 'loosens (more explore/looser exploit/larger size) as acted trades profit; tightens on losses; circuit breaker is the hard floor.'}`

accuracy_by_context `{}`

view_edge_candidates `[]`

circuit_breaker `{'tripped': False, 'reason': None, 'consecutive_losses': 0, 'daily_follow_loss_usd': 0.0, 'daily_loss_cap_usd': 30.0, 'trips': 0, 'cooldown_remaining_s': 0, 'max_consecutive_losses': 4, 'max_latency_s': 20.0}`

news_digest `{"enabled": false}`

recent_decisions `[]`

## 9. Grok signal intel (analyst + predictor + budget)

budget `{'daily_usd_cap': 5.0, 'est_usd_per_call': 0.02, 'spent_today_usd': 0.04, 'calls_today': 2, 'per_feature_hourly': {'predictor': 30, 'analyst': 4, 'overlay': 20, 'decider': 60, 'news': 30}}`

predictor_B `{'enabled': True, 'observe_only': True, 'affects_trading': False, 'off_hot_path': True, 'requested': 0, 'predicted': 0, 'errors': 0, 'skipped_budget': 0, 'scored': 0, 'accuracy': None, 'brier': None, 'pending': 0, 'note': 'observe-only Grok P(up) per signal; graded vs realized BTC move before it could ever be trusted; never places/sizes/bypasses a trade.'}`

analyst_A last_note `null`

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

## 12. Edge signal & readiness

edge_signal `{"enabled": true, "observe_only": true, "report_only": true, "affects_trading": false, "settled": 0, "by_stale_divergence": {}, "by_ttc_bucket": {}, "by_ob_pressure": {}}`

**CEX-lead latency edge** (grades CEX-implied P(up) vs the MARKET price): mode `shadow` · affects_trading False · signals_seen 8 · graded 0 · drove 0 · any_proven (beats market) **False**
_promotion: n>=min AND wilson_lower(win_rate)>breakeven AND Brier_cex<Brier_market AND avg_pnl>0_

**Within-window risk-free arbitrage** (Roan dutch book `up_vwap+down_vwap<1`; P&L SEGREGATED from directional, never blended): detected_actionable 0 · sell_both_detected 4 · executed 0 · settled 0 · open 0 · realized_profit **$0.0** (risk-free)

readiness `{'report_only': True, 'status': 'not_ready', 'ready_to_claim_80pct': False, 'gates': {'accepted_ge_100': False, 'accepted_ge_500': False, 'accepted_ge_1000': False, 'win_rate_ge_80': False, 'positive_net_paper_pnl': False, 'profit_factor_ok': False, 'calibration_error_ok': False, 'max_drawdown_ok': True, 'loss_size_le_win_size': True, 'no_reconciliation_failures': True, 'no_missing_settlement_data': True, 'no_unmodeled_fill_assumptions': True, 'no_safety_bypass': True}, 'metrics': {'accepted': 0, 'win_rate': None, 'net_pnl_usd': 0.0, 'profit_factor': None, 'calibration_error': None, 'max_drawdown_usd': 0.0, 'avg_win_usd': None, 'avg_loss_usd': None}}`

## 13. Recent paper positions

_no positions_

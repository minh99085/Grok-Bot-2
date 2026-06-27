# Technical Data Grades

**Generated:** 2026-06-27T20:56:32.569033+00:00  
**Repo SHA:** `de1545374cf5`  
**Ticks:** 3 | **Settled:** 90

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **69.9** | **D** |
| Report overall | 63.5 | D |
| Technical runtime | 84.9 | B |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 58.2 | F |
| Operation | 90.4 | A |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 100.0 | 20 |
| tv_intake | 98.7 | 20 |
| design_compliance | 66.5 | 25 |
| trade_pipeline | 90.2 | 20 |
| gate_coupling | 69.7 | 15 |

### Rtds Health (100.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| connected | 100.0 | 35 |
| oracle_fresh | 100.0 | 30 |
| stability | 100.0 | 20 |
| price_feed | 100.0 | 15 |

### Tv Intake (98.7)

| Component | Score | Weight |
|-----------|------:|-------:|
| observe_only | 100.0 | 25 |
| alert_flow | 100.0 | 25 |
| reject_rate | 91.1 | 15 |
| trade_gates_off | 100.0 | 20 |
| mtf_freshness | 100.0 | 15 |

### Design Compliance (66.5)

| Component | Score | Weight |
|-----------|------:|-------:|
| series_15m | 100.0 | 15 |
| green_path | 100.0 | 10 |
| paper_only | 100.0 | 10 |
| grok_shadow | 100.0 | 5 |
| tick_seconds | 50.0 | 10 |
| max_price | 100.0 | 10 |
| min_edge | 100.0 | 5 |
| min_reward_risk | 50.0 | 5 |
| cohort_relaxed | 40.0 | 10 |
| tv_trade_gates_off | 0.0 | 20 |

### Trade Pipeline (90.2)

| Component | Score | Weight |
|-----------|------:|-------:|
| accounting_integrity | 100.0 | 25 |
| lifecycle | 100.0 | 20 |
| execution_gate | 100.0 | 20 |
| recon_checks | 100.0 | 15 |
| not_halted | 100.0 | 10 |
| uptime_ticks | 1.5 | 10 |

### Gate Coupling (69.7)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 38.7 | 25 |
| exec_pass_rate | 84.6 | 25 |
| reject_diversity | 69.6 | 20 |
| cohort_session_load | 100.0 | 15 |
| recent_eval_spread | 66.7 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-27 17:48:10 UTC | 88 | 53.8 | 48.8 | 70.4 | 47.0 |
| 2026-06-27 18:18:41 UTC | 88 | 53.8 | 48.8 | 70.4 | 47.0 |
| 2026-06-27 18:33:10 UTC | 89 | 55.2 | 51.7 | 70.4 | 47.0 |
| 2026-06-27 19:03:10 UTC | 90 | 53.5 | 48.2 | 70.4 | 47.0 |
| 2026-06-27 19:27:06 UTC | 90 | 63.5 | 58.2 | 90.4 | 47.0 |

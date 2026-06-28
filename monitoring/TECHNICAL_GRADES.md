# Technical Data Grades

**Generated:** 2026-06-28T12:33:59.532866+00:00  
**Repo SHA:** `e95386f9c0d0`  
**Ticks:** 467 | **Settled:** 116

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **74.9** | **C** |
| Report overall | 70.3 | C |
| Technical runtime | 85.8 | B+ |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 72.4 | C |
| Operation | 89.3 | B+ |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 97.0 | 20 |
| tv_intake | 99.9 | 20 |
| design_compliance | 70.0 | 25 |
| trade_pipeline | 100.0 | 20 |
| gate_coupling | 59.6 | 15 |

### Rtds Health (97.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| connected | 100.0 | 35 |
| oracle_fresh | 100.0 | 30 |
| stability | 85.0 | 20 |
| price_feed | 100.0 | 15 |

### Tv Intake (99.9)

| Component | Score | Weight |
|-----------|------:|-------:|
| observe_only | 100.0 | 25 |
| alert_flow | 100.0 | 25 |
| reject_rate | 99.5 | 15 |
| trade_gates_off | 100.0 | 20 |
| mtf_freshness | 100.0 | 15 |

### Design Compliance (70.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| series_15m | 100.0 | 15 |
| green_path | 100.0 | 10 |
| paper_only | 100.0 | 10 |
| grok_shadow | 100.0 | 5 |
| tick_seconds | 100.0 | 10 |
| max_price | 50.0 | 10 |
| min_edge | 50.0 | 5 |
| min_reward_risk | 50.0 | 5 |
| cohort_relaxed | 100.0 | 10 |
| tv_trade_gates_off | 0.0 | 20 |

### Trade Pipeline (100.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| accounting_integrity | 100.0 | 25 |
| lifecycle | 100.0 | 20 |
| execution_gate | 100.0 | 20 |
| recon_checks | 100.0 | 15 |
| not_halted | 100.0 | 10 |
| uptime_ticks | 100.0 | 10 |

### Gate Coupling (59.6)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 37.8 | 25 |
| exec_pass_rate | 87.6 | 25 |
| reject_diversity | 69.4 | 20 |
| cohort_session_load | 25.0 | 15 |
| recent_eval_spread | 70.8 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-28 11:02:37 UTC | 113 | 69.5 | 70.7 | 89.5 | 47.0 |
| 2026-06-28 11:32:52 UTC | 113 | 69.5 | 70.7 | 89.4 | 47.0 |
| 2026-06-28 11:48:20 UTC | 114 | 70.5 | 72.8 | 89.4 | 47.0 |
| 2026-06-28 12:03:07 UTC | 115 | 69.3 | 70.4 | 89.4 | 47.0 |
| 2026-06-28 12:16:52 UTC | 116 | 70.3 | 72.4 | 89.4 | 47.0 |

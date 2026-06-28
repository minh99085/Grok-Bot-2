# Technical Data Grades

**Generated:** 2026-06-28T09:33:57.439841+00:00  
**Repo SHA:** `1739dc27e2f7`  
**Ticks:** 386 | **Settled:** 110

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **75.5** | **C+** |
| Report overall | 70.8 | C |
| Technical runtime | 86.6 | B+ |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 73.3 | C |
| Operation | 89.8 | B+ |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 100.0 | 20 |
| tv_intake | 99.9 | 20 |
| design_compliance | 70.0 | 25 |
| trade_pipeline | 100.0 | 20 |
| gate_coupling | 60.8 | 15 |

### Rtds Health (100.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| connected | 100.0 | 35 |
| oracle_fresh | 100.0 | 30 |
| stability | 100.0 | 20 |
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

### Gate Coupling (60.8)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 37.9 | 25 |
| exec_pass_rate | 89.8 | 25 |
| reject_diversity | 69.3 | 20 |
| cohort_session_load | 25.0 | 15 |
| recent_eval_spread | 75.0 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-28 08:33:15 UTC | 106 | 69.0 | 69.5 | 89.9 | 47.0 |
| 2026-06-28 08:47:00 UTC | 107 | 67.8 | 67.1 | 89.9 | 47.0 |
| 2026-06-28 09:03:28 UTC | 108 | 68.7 | 68.9 | 89.8 | 47.0 |
| 2026-06-28 09:18:28 UTC | 109 | 69.7 | 70.9 | 89.8 | 47.0 |
| 2026-06-28 09:33:15 UTC | 110 | 70.8 | 73.3 | 89.8 | 47.0 |

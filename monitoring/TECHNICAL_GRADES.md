# Technical Data Grades

**Generated:** 2026-06-29T00:07:21.735008+00:00  
**Repo SHA:** `2ca238f7a048`  
**Ticks:** 583 | **Settled:** 134

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **77.8** | **C+** |
| Report overall | 73.8 | C |
| Technical runtime | 87.1 | B+ |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 80.5 | B |
| Operation | 87.4 | B+ |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 97.0 | 20 |
| tv_intake | 100.0 | 20 |
| design_compliance | 70.0 | 25 |
| trade_pipeline | 100.0 | 20 |
| gate_coupling | 68.2 | 15 |

### Rtds Health (97.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| connected | 100.0 | 35 |
| oracle_fresh | 100.0 | 30 |
| stability | 85.0 | 20 |
| price_feed | 100.0 | 15 |

### Tv Intake (100.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| observe_only | 100.0 | 25 |
| alert_flow | 100.0 | 25 |
| reject_rate | 99.7 | 15 |
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

### Gate Coupling (68.2)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 37.2 | 25 |
| exec_pass_rate | 91.5 | 25 |
| reject_diversity | 69.1 | 20 |
| cohort_session_load | 73.0 | 15 |
| recent_eval_spread | 75.0 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-28 22:17:05 UTC | 133 | 73.6 | 79.9 | 87.6 | 47.0 |
| 2026-06-28 22:47:19 UTC | 133 | 73.6 | 79.9 | 87.6 | 47.0 |
| 2026-06-28 23:03:05 UTC | 134 | 73.9 | 80.5 | 87.5 | 47.0 |
| 2026-06-28 23:33:19 UTC | 134 | 73.8 | 80.5 | 87.4 | 47.0 |
| 2026-06-29 00:03:19 UTC | 134 | 73.8 | 80.5 | 87.4 | 47.0 |

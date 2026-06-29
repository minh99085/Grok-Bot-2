# Technical Data Grades

**Generated:** 2026-06-29T02:58:53.730616+00:00  
**Repo SHA:** `9eef281f2dfb`  
**Ticks:** 307 | **Settled:** 136

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **77.6** | **C+** |
| Report overall | 73.0 | C |
| Technical runtime | 88.4 | B+ |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 78.9 | C+ |
| Operation | 87.1 | B+ |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 100.0 | 20 |
| tv_intake | 100.0 | 20 |
| design_compliance | 72.5 | 25 |
| trade_pipeline | 100.0 | 20 |
| gate_coupling | 68.8 | 15 |

### Rtds Health (100.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| connected | 100.0 | 35 |
| oracle_fresh | 100.0 | 30 |
| stability | 100.0 | 20 |
| price_feed | 100.0 | 15 |

### Tv Intake (100.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| observe_only | 100.0 | 25 |
| alert_flow | 100.0 | 25 |
| reject_rate | 99.7 | 15 |
| trade_gates_off | 100.0 | 20 |
| mtf_freshness | 100.0 | 15 |

### Design Compliance (72.5)

| Component | Score | Weight |
|-----------|------:|-------:|
| series_15m | 100.0 | 15 |
| green_path | 100.0 | 10 |
| paper_only | 100.0 | 10 |
| grok_shadow | 100.0 | 5 |
| tick_seconds | 100.0 | 10 |
| max_price | 50.0 | 10 |
| min_edge | 50.0 | 5 |
| min_reward_risk | 100.0 | 5 |
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

### Gate Coupling (68.8)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 37.0 | 25 |
| exec_pass_rate | 90.5 | 25 |
| reject_diversity | 69.0 | 20 |
| cohort_session_load | 79.0 | 15 |
| recent_eval_spread | 75.0 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-29 00:48:02 UTC | 135 | 73.5 | 79.7 | 87.4 | 47.0 |
| 2026-06-29 01:18:18 UTC | 135 | 73.4 | 79.7 | 87.3 | 47.0 |
| 2026-06-29 01:45:25 UTC | 136 | 73.0 | 78.9 | 87.2 | 47.0 |
| 2026-06-29 02:15:25 UTC | 136 | 73.0 | 78.9 | 87.2 | 47.0 |
| 2026-06-29 02:45:25 UTC | 136 | 73.0 | 78.9 | 87.2 | 47.0 |

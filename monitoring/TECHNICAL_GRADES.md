# Technical Data Grades

**Generated:** 2026-06-29T04:44:42.514416+00:00  
**Repo SHA:** `bf911eea653e`  
**Ticks:** 321 | **Settled:** 137

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **77.1** | **C+** |
| Report overall | 72.5 | C |
| Technical runtime | 87.9 | B+ |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 78.1 | C+ |
| Operation | 86.9 | B+ |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 100.0 | 20 |
| tv_intake | 100.0 | 20 |
| design_compliance | 70.0 | 25 |
| trade_pipeline | 100.0 | 20 |
| gate_coupling | 69.5 | 15 |

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

### Gate Coupling (69.5)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 36.9 | 25 |
| exec_pass_rate | 90.7 | 25 |
| reject_diversity | 69.0 | 20 |
| cohort_session_load | 83.5 | 15 |
| recent_eval_spread | 75.0 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-29 02:45:25 UTC | 136 | 73.0 | 78.9 | 87.2 | 47.0 |
| 2026-06-29 03:15:28 UTC | 136 | 73.0 | 78.9 | 87.1 | 47.0 |
| 2026-06-29 03:45:40 UTC | 136 | 73.0 | 78.9 | 87.0 | 47.0 |
| 2026-06-29 04:15:55 UTC | 136 | 73.0 | 78.9 | 87.0 | 47.0 |
| 2026-06-29 04:33:10 UTC | 137 | 72.5 | 78.1 | 86.9 | 47.0 |

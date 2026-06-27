# Technical Data Grades

**Generated:** 2026-06-27T23:42:14.604414+00:00  
**Repo SHA:** `c27982438bb3`  
**Ticks:** 4 | **Settled:** 93

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **72.0** | **C** |
| Report overall | 64.9 | D |
| Technical runtime | 88.6 | B+ |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 61.1 | D |
| Operation | 90.4 | A |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 100.0 | 20 |
| tv_intake | 98.9 | 20 |
| design_compliance | 80.0 | 25 |
| trade_pipeline | 90.2 | 20 |
| gate_coupling | 71.6 | 15 |

### Rtds Health (100.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| connected | 100.0 | 35 |
| oracle_fresh | 100.0 | 30 |
| stability | 100.0 | 20 |
| price_feed | 100.0 | 15 |

### Tv Intake (98.9)

| Component | Score | Weight |
|-----------|------:|-------:|
| observe_only | 100.0 | 25 |
| alert_flow | 100.0 | 25 |
| reject_rate | 92.8 | 15 |
| trade_gates_off | 100.0 | 20 |
| mtf_freshness | 100.0 | 15 |

### Design Compliance (80.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| series_15m | 100.0 | 15 |
| green_path | 100.0 | 10 |
| paper_only | 100.0 | 10 |
| grok_shadow | 100.0 | 5 |
| tick_seconds | 100.0 | 10 |
| max_price | 100.0 | 10 |
| min_edge | 100.0 | 5 |
| min_reward_risk | 100.0 | 5 |
| cohort_relaxed | 100.0 | 10 |
| tv_trade_gates_off | 0.0 | 20 |

### Trade Pipeline (90.2)

| Component | Score | Weight |
|-----------|------:|-------:|
| accounting_integrity | 100.0 | 25 |
| lifecycle | 100.0 | 20 |
| execution_gate | 100.0 | 20 |
| recon_checks | 100.0 | 15 |
| not_halted | 100.0 | 10 |
| uptime_ticks | 2.0 | 10 |

### Gate Coupling (71.6)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 38.6 | 25 |
| exec_pass_rate | 83.4 | 25 |
| reject_diversity | 69.5 | 20 |
| cohort_session_load | 100.0 | 15 |
| recent_eval_spread | 81.2 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-27 22:03:10 UTC | 92 | 53.4 | 48.1 | 70.4 | 47.0 |
| 2026-06-27 22:33:25 UTC | 92 | 53.4 | 48.1 | 70.4 | 47.0 |
| 2026-06-27 23:03:40 UTC | 92 | 53.4 | 48.1 | 70.4 | 47.0 |
| 2026-06-27 23:30:10 UTC | 93 | 54.9 | 51.1 | 70.4 | 47.0 |
| 2026-06-27 23:39:44 UTC | 93 | 64.9 | 61.1 | 90.4 | 47.0 |

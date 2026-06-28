# Technical Data Grades

**Generated:** 2026-06-28T17:21:58.923212+00:00  
**Repo SHA:** `89b2e7454021`  
**Ticks:** 78 | **Settled:** 126

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **77.3** | **C+** |
| Report overall | 73.4 | C |
| Technical runtime | 86.5 | B+ |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 79.1 | C+ |
| Operation | 88.5 | B+ |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 100.0 | 20 |
| tv_intake | 99.9 | 20 |
| design_compliance | 70.0 | 25 |
| trade_pipeline | 93.9 | 20 |
| gate_coupling | 68.5 | 15 |

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
| reject_rate | 99.6 | 15 |
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

### Trade Pipeline (93.9)

| Component | Score | Weight |
|-----------|------:|-------:|
| accounting_integrity | 100.0 | 25 |
| lifecycle | 100.0 | 20 |
| execution_gate | 100.0 | 20 |
| recon_checks | 100.0 | 15 |
| not_halted | 100.0 | 10 |
| uptime_ticks | 39.0 | 10 |

### Gate Coupling (68.5)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 37.5 | 25 |
| exec_pass_rate | 89.5 | 25 |
| reject_diversity | 69.3 | 20 |
| cohort_session_load | 98.5 | 15 |
| recent_eval_spread | 54.2 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-28 16:16:22 UTC | 124 | 72.9 | 78.0 | 88.6 | 47.0 |
| 2026-06-28 16:46:22 UTC | 124 | 72.9 | 78.0 | 88.5 | 47.0 |
| 2026-06-28 16:46:37 UTC | 125 | 73.1 | 78.5 | 88.5 | 47.0 |
| 2026-06-28 17:16:41 UTC | 125 | 73.1 | 78.5 | 88.5 | 47.0 |
| 2026-06-28 17:16:56 UTC | 126 | 73.4 | 79.1 | 88.5 | 47.0 |

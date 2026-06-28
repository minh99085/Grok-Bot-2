# Technical Data Grades

**Generated:** 2026-06-28T02:34:04.746610+00:00  
**Repo SHA:** `a1a824869810`  
**Ticks:** 1 | **Settled:** 97

## Composite

| Metric | Score | Grade |
|--------|------:|-------|
| **Composite** | **70.5** | **C** |
| Report overall | 66.7 | D |
| Technical runtime | 79.5 | C+ |

## Report scores (engine)

| Section | Score | Grade |
|---------|------:|-------|
| Trading Performance | 64.3 | D |
| Operation | 91.0 | A |
| External Signals | 47.0 | F |

## Technical runtime

_RTDS/oracle health, TV observe-only intake, design manifest compliance, pipeline integrity, gate coupling._

| Component | Score | Weight |
|-----------|------:|-------:|
| rtds_health | 61.0 | 20 |
| tv_intake | 99.1 | 20 |
| design_compliance | 77.5 | 25 |
| trade_pipeline | 90.0 | 20 |
| gate_coupling | 67.3 | 15 |

### Rtds Health (61.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| connected | 100.0 | 35 |
| oracle_fresh | 0.0 | 30 |
| stability | 100.0 | 20 |
| price_feed | 40.0 | 15 |

### Tv Intake (99.1)

| Component | Score | Weight |
|-----------|------:|-------:|
| observe_only | 100.0 | 25 |
| alert_flow | 100.0 | 25 |
| reject_rate | 93.8 | 15 |
| trade_gates_off | 100.0 | 20 |
| mtf_freshness | 100.0 | 15 |

### Design Compliance (77.5)

| Component | Score | Weight |
|-----------|------:|-------:|
| series_15m | 100.0 | 15 |
| green_path | 100.0 | 10 |
| paper_only | 100.0 | 10 |
| grok_shadow | 100.0 | 5 |
| tick_seconds | 100.0 | 10 |
| max_price | 100.0 | 10 |
| min_edge | 100.0 | 5 |
| min_reward_risk | 50.0 | 5 |
| cohort_relaxed | 100.0 | 10 |
| tv_trade_gates_off | 0.0 | 20 |

### Trade Pipeline (90.0)

| Component | Score | Weight |
|-----------|------:|-------:|
| accounting_integrity | 100.0 | 25 |
| lifecycle | 100.0 | 20 |
| execution_gate | 100.0 | 20 |
| recon_checks | 100.0 | 15 |
| not_halted | 100.0 | 10 |
| uptime_ticks | 0.5 | 10 |

### Gate Coupling (67.3)

| Component | Score | Weight |
|-----------|------:|-------:|
| lifecycle_funnel | 38.4 | 25 |
| exec_pass_rate | 85.1 | 25 |
| reject_diversity | 69.4 | 20 |
| cohort_session_load | 100.0 | 15 |
| recent_eval_spread | 50.0 | 15 |

## VPS score history (last entries)

| UTC | Settled | Overall | Trading | Operation | External |
|-----|--------:|--------:|--------:|----------:|---------:|
| 2026-06-28 00:48:03 UTC | 95 | 64.6 | 60.5 | 90.4 | 47.0 |
| 2026-06-28 01:03:04 UTC | 96 | 65.7 | 62.7 | 90.4 | 47.0 |
| 2026-06-28 01:33:15 UTC | 96 | 65.7 | 62.7 | 90.4 | 47.0 |
| 2026-06-28 02:02:51 UTC | 97 | 66.5 | 64.3 | 90.4 | 47.0 |
| 2026-06-28 02:33:06 UTC | 97 | 66.5 | 64.3 | 90.4 | 47.0 |

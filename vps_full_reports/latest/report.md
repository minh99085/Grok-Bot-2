# BTC 5-min Pulse — Live Report

Generated from the live VPS pulse engine (PAPER ONLY). Snapshot: **2026-06-21 04:13:42 UTC** · ticks **1493**

## Oracle reference model
| Field | Value |
|---|---|
| oracle_feed_type | `chainlink_data_streams_refprice` |
| oracle_symbol | `btc/usd` |
| price source | `rtds_chainlink` (last `64321.84`) |
| open_snapshot_source | `rtds_chainlink` |
| close_snapshot_source | `rtds_chainlink` |
| fast_feed_symbols (lead only) | `binance_btcusdt, coinbase_btcusd` |
| settlement_source_priority | `polymarket_resolution -> rtds_chainlink_proxy` |
| RTDS connected | `True` (msgs `11589`, reconnects `0`) |
| Chainlink btc/usd (oracle) | `64321.84` |
| Binance btcusdt (lead) | `64403.93` (settlement_eligible `False`) |
| Coinbase btcusd (lead) | `64322.57` (settlement_eligible `False`) |
| price sampler | every `1.0s`, running `True`, polls `7459` (errors `3`) |
| sigma_per_sec | `3.177e-05` (vol_samples `5000`) |

## Paper P&L (PAPER ONLY — no real orders)
| Metric | Value |
|---|---|
| trades / settled | 37 / 36 |
| win_rate | 0.5833 (up 0.5238, down 0.6667) |
| avg_entry_price | 0.4928 |
| **edge_realized** (win_rate - avg cost) | **0.0906** |
| realized_pnl_usd | **38.2059** |
| avg_pnl_per_trade | 1.0613 |
| open_positions | 1 |
| side_counts | {'up': 21, 'down': 15} |

## Settlement & calibration
| Metric | Value |
|---|---|
| settlement sources used | {'polymarket_resolution': 8, 'rtds_chainlink_proxy': 12} |
| proxy/official reconciliation | both 8, agree 7, disagree 1 |
| calibration Brier | 0.226625 (baseline 0.25) |
| calibration log_loss | 0.635974 |
| calibration samples | 36 (base_rate_up 0.4444) |

## Grok event-risk overlay (advisory, off hot path)
| Field | Value |
|---|---|
| enabled / running | True / True |
| calls / errors | 32 / 0 |
| regime | `calm` (blackout False) |
| reason | no imminent high-impact events |

## Files
- `btc_pulse_status.json` — full engine status (oracle, price, ledger, calibration, overlay).
- `btc_pulse_ledger.json` — full paper ledger (positions + P&L + accumulators).
- `vps_state.txt` — container status + deployed commit.

> PAPER ONLY. The engine trades only the Polymarket `btc-up-or-down-5m` series; oracle =
> Chainlink Data Streams reference price via Polymarket RTDS `crypto_prices_chainlink`;
> Binance/Coinbase are lead predictors only; settlement = official Polymarket resolution first,
> then RTDS Chainlink open/close proxy within the close-lag threshold.

# VPS Full Reports

Live snapshots of the **BTC 5-minute pulse** PAPER engine running on the VPS.

> **Agent convention:** every full-report pull MUST be committed here on `main` (refresh
> `latest/` from the live VPS container, then commit + push).

## `latest/`
- `report.md` — human-readable summary (oracle, paper P&L, settlement, calibration, overlay).
- `report.docx` — Word export of the full report (always committed with each pull).
- `btc_pulse_status.json` — full engine status (oracle reference model, price feed, ledger
  stats, calibration, Grok overlay, RTDS + lead-feature health).
- `btc_pulse_ledger.json` — full paper ledger (per-window positions, P&L, accumulators).
- `vps_state.txt` — container status + deployed commit.

PAPER ONLY — no real orders. Oracle = Chainlink Data Streams reference price via Polymarket
RTDS `crypto_prices_chainlink` (`btc/usd`); Binance/Coinbase are lead predictors only;
settlement = official Polymarket resolution first, then RTDS Chainlink open/close proxy.

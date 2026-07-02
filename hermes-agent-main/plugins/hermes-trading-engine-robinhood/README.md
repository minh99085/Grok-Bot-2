# Hermes Trading Engine — Robinhood Agentic

Isolated plugin for connecting Hermes to [Robinhood's official Trading MCP](https://agent.robinhood.com/mcp/trading). Runs **alongside** the Polymarket paper engine (`hermes-trading-engine`) without sharing containers, ports, or data volumes.

## Architecture

| Service | Container | Port | Role |
|---------|-----------|------|------|
| API | `hermes-robinhood-api` | `8810` | Health + status (`/api/health`, `/api/robinhood/status`) |
| Agent loop | `hermes-robinhood-agent` | — | MCP connection manager, reconnect, status persistence |

Data volume: `rh_data` → `/data` (OAuth tokens, audit log, status JSON).

## Quick start (local)

```bash
cd hermes-agent-main/plugins/hermes-trading-engine-robinhood
cp .env.example .env
pip install -r requirements.txt -r requirements-dev.txt

# One-time OAuth (desktop browser)
python scripts/robinhood_oauth_login.py

# Run agent + API
docker compose --profile robinhood up -d --build
curl http://127.0.0.1:8810/api/health
curl http://127.0.0.1:8810/api/robinhood/tools
```

## VPS deploy (does not touch Polymarket)

From repo root after pushing to `main`:

```powershell
git push origin main
.\scripts\sync-vps-robinhood.ps1
```

Polymarket deploy remains `.\scripts\sync-vps.ps1` — unchanged.

### First-time VPS OAuth

Robinhood requires **desktop** OAuth for Agentic account onboarding:

1. SSH to VPS or run locally with `RH_DATA_DIR` pointing at the volume.
2. `python scripts/robinhood_oauth_login.py` — open the printed URL, complete auth, paste callback URL.
3. Confirm tokens at `/data/robinhood_oauth_tokens.json` inside `rh_data` volume.
4. Start containers: `docker compose --profile robinhood up -d`.

## Safety defaults

| Setting | Default | Meaning |
|---------|---------|---------|
| `RH_LIVE_TRADING_ENABLED` | `0` | Blocks `place_*` orders |
| `RH_APPROVAL_MODE` | `review_required` | Requires Robinhood `review_*` before place |
| `RH_MAX_ORDER_NOTIONAL_USD` | `100` | Hard cap per order |
| `RH_REVIEW_THRESHOLD_NOTIONAL_USD` | `50` | Calls `review_equity_order` / `review_option_order` |
| `RH_DAILY_LOSS_LIMIT_USD` | `200` | Halts new orders after daily loss |
| `RH_MAX_DAY_TRADES_5D` | `3` | PDT-style rolling limit |

Audit log: `/data/robinhood_audit.jsonl` (every tool call + safety decision).

## Tests

```bash
python -m pytest tests/ -q
```
# Robinhood-Bot

An autonomous **options + equities trading bot for Robinhood Agentic**. It connects to
Robinhood's official [Trading MCP](https://agent.robinhood.com/mcp/trading) over OAuth and
routes every order through a local safety layer (live-trading kill switch, per-order notional
caps, daily-loss halt, PDT and concentration limits, and Robinhood `review_*` pre-checks).

> Previously this repo also contained a Polymarket BTC "pulse" paper engine. That engine has
> been removed — the Robinhood Agentic plugin is now the only trading bot here.

## Where the bot lives

```
hermes-agent-main/plugins/hermes-trading-engine-robinhood/
├── engine/
│   ├── app.py                     # read-only health/status API (:8810)
│   └── robinhood/
│       ├── robinhood_mcp_adapter.py  # long-lived MCP client (OAuth, reconnect)
│       ├── client.py                 # SafeRobinhoodClient — gates every tool call
│       ├── safety_gates.py           # live flag, notional/loss/PDT/concentration gates
│       ├── oauth_storage.py          # file-backed OAuth token persistence
│       ├── oauth_callback.py         # local OAuth redirect server
│       └── audit_log.py              # append-only JSONL audit
├── scripts/
│   ├── run_robinhood_agent.py     # agent loop (connect + reconnect + status)
│   └── robinhood_oauth_login.py   # one-time desktop OAuth
└── tests/                         # offline safety-gate + adapter + health tests
```

`hermes-agent-main/` is the vendored [Hermes agent](https://github.com/NousResearch/hermes-agent)
framework the plugin ships inside; the plugin itself is self-contained (its own
`requirements.txt`, Dockerfile, and FastAPI app).

## Quick start

```bash
cd hermes-agent-main/plugins/hermes-trading-engine-robinhood
cp .env.example .env
pip install -r requirements.txt -r requirements-dev.txt

# One-time OAuth (desktop browser required by Robinhood)
python scripts/robinhood_oauth_login.py

# Run the agent + API
docker compose --profile robinhood up -d --build
curl http://127.0.0.1:8810/api/health
```

## Options + equities

| Place tool | Review tool |
|------------|-------------|
| `place_option_order` | `review_option_order` |
| `place_equity_order` | `review_equity_order` |

Both asset classes pass through the same safety gates. Option chains and other read tools are
whatever the Robinhood MCP server exposes (logged at OAuth login).

## Safety defaults

| Setting | Default | Meaning |
|---------|---------|---------|
| `RH_LIVE_TRADING_ENABLED` | `0` | Blocks all `place_*` orders |
| `RH_APPROVAL_MODE` | `review_required` | Robinhood `review_*` before place |
| `RH_MAX_ORDER_NOTIONAL_USD` | `100` | Hard cap per order |
| `RH_REVIEW_THRESHOLD_NOTIONAL_USD` | `50` | Triggers `review_*` |
| `RH_DAILY_LOSS_LIMIT_USD` | `200` | Halts new orders after daily loss |
| `RH_MAX_DAY_TRADES_5D` | `3` | PDT-style rolling limit |

Live trading stays **off** until you explicitly set `RH_LIVE_TRADING_ENABLED=1`.

## Tests

```bash
cd hermes-agent-main/plugins/hermes-trading-engine-robinhood
python -m pytest tests/ -q
```

## Deploy

See `AGENTS.md` and `scripts/sync-vps-robinhood.ps1`.

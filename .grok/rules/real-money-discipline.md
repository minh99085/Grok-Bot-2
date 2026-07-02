# Real-money discipline (Robinhood Agentic)

Robinhood orders move **real capital**. Treat every `place_*` path as production money —
protect PnL and avoid catastrophic orders before chasing returns.

## Live-trading kill switch

- `RH_LIVE_TRADING_ENABLED=0` is the default and MUST stay off until the operator explicitly
  enables live trading in a dedicated message.
- When off, `SafeRobinhoodClient` blocks every `place_equity_order` / `place_option_order`.
- Never flip it on in code, `.env` committed to git, or a babysit/automation fix.

## Order safety gates (never bypass)

Every order flows through `RobinhoodSafetyGates` (`engine/robinhood/safety_gates.py`):

| Gate | Env key | Purpose |
|------|---------|---------|
| Max notional | `RH_MAX_ORDER_NOTIONAL_USD` | Hard per-order cap |
| Review threshold | `RH_REVIEW_THRESHOLD_NOTIONAL_USD` | Forces Robinhood `review_*` before place |
| Daily loss halt | `RH_DAILY_LOSS_LIMIT_USD` | Stops new orders after daily loss |
| Position size | `RH_MAX_POSITION_PCT` | Max order as % of portfolio |
| Concentration | `RH_MAX_SYMBOL_CONCENTRATION_PCT` | Max single-symbol exposure |
| PDT | `RH_MAX_DAY_TRADES_5D` | Rolling 5-day day-trade limit |
| Buying-power buffer | `RH_MIN_BUYING_POWER_BUFFER_USD` | Keeps cash reserve |

- `RH_APPROVAL_MODE=review_required`: `place_*` above the threshold must pass `review_option_order`
  / `review_equity_order` first.
- Never widen a cap or disable a gate to "unblock" the bot without an explicit operator request.

## Auditability

- Every tool call + safety decision is written to `/data/robinhood_audit.jsonl`.
- Do not remove or downgrade audit logging.

## When adding a strategy

- Build it on top of `SafeRobinhoodClient`, never around it.
- Prove it against the gates (unit tests) before wiring it to live order placement.
- No martingale / averaging-down: size must not grow after a loss.

# Grok Build Task — Make Grok-Bot-2 Trade ~5× More Profit (Paper-First, Arbitrage-Led)

> Paste this whole file into Grok Build / Cursor as the task spec.
> Workspace: `Grok-Bot-2` repo, branch `main`. Engine: `hermes-agent-main/plugins/hermes-trading-engine/engine/pulse/`.

---

## ROLE

You are the senior quant engineer for Grok-Bot-2 ("Hermes BTC Pulse"). Your job is to raise total **paper** profit ~5× by scaling the bot's *proven, risk-free* edge and stopping its *unproven* bleed — **not** by making the directional predictor smarter. **Live trading stays disabled the entire time.**

---

## GROUND TRUTH — READ BEFORE WRITING CODE (do not rebuild what exists)

Other docs in `docs/polymarket-arbitrage/` were written from public GitHub inspection and wrongly assume no arbitrage infrastructure exists. **It does.** Verify against the real source before creating new modules:

**What already exists and works — extend, don't replace:**
- `engine/pulse/arbitrage.py` — within-window **dutch book** detector. Buy 1 up + 1 down for `< $1`, or mint a $1 set and sell both legs `> $1`. Already uses real VWAP fills, `epsilon=0.05` min margin, `max_depth_consume_frac=0.5`, stale-book + tick guards, full-fill checks, and a **segregated** `ArbLedger`. This is the engine's real profit source.
- `engine/pulse/execution_gate.py` — `vwap_fill()` walks the ladder (no top-of-book fantasy); `evaluate_execution()` enforces spread/depth/EV-after-slippage/underdog-floor/stale rejects.
- `engine/pulse/sizing.py` — half-Kelly with hard cap, daily-loss cap, degradation penalty, **no-martingale** guarantee. **Currently `sizing_enabled=False` → flat size.**
- `engine/pulse/strategy.py`, `decisions.py`, `selectivity.py`, `loops.py`, `grok_decider.py`, `grok_intel.py`, `reconciliation.py`, `settlement.py`, `performance_scoring.py`.
- Promotion discipline already in place: Wilson lower bounds + Benjamini–Hochberg FDR, segregated ledgers, `global_reconciled` accounting, maker-checker `verifier`.

**The evidence (latest paper soak, 1,769 ticks, `vps_full_reports/latest/report.md`):**
- **Arbitrage: +$34.46 from 4 risk-free trades.** (~96% of all profit.)
- **Directional: +$1.49 from 48 trades**, PF 1.02, **avg loss $4.17 > avg win $2.55**.
- Every directional signal grades at/below a coin flip: TV `no_directional_edge`, Grok direction 0.50, CEX-lead 0.469 (loses to market), predictor 0.482.
- One faint, **unproven** asymmetry: DOWN works, UP loses (UP n=8 WR 0.25 −$14.8; UP_STRONG n=6 WR 0.17 −$14.2; DOWN_STRONG n=23 WR 0.74 +$21; 180–240s TTC n=16 WR 0.81 +$25). All buckets below the n≥50 promotion bar → **hypotheses, not edges.**

**Mathematical correction for the heavy machinery:** a single 2-outcome window's marginal polytope is trivial, so Bregman/Frank-Wolfe/IP/Gurobi are **genuinely unnecessary there** (arbitrage.py is right to skip them). They only earn their keep on **dependent markets** — see Workstream 4. Do not add a solver to single-window scanning.

---

## WHERE THE 5× ACTUALLY COMES FROM (honest decomposition)

You will **not** hit 5× by predicting BTC better. You hit it by capturing more guaranteed spread, more often, at more size, plus opening one new risk-free surface:

1. **Breadth** — scan *every* concurrently-open up/down window (5m **and** 15m) and ETH if listed, not one BTC window. Each is an independent dutch book. (~2–4× more opportunities.)
2. **Size** — let actionable arbs consume up to the existing 50%-depth cap with risk-adjusted sizing instead of a tiny flat ceiling. (More $ per opportunity.)
3. **New surface** — cross-window (5m↔15m nesting) and cross-asset (BTC↔ETH) **dependency** arbitrage: the one place the Bible's IP/Bregman/LLM-screening pays. (Net-new risk-free trades.)
4. **Stop the bleed** — cap/observe-only the directional book so it stops giving back arb gains.

Target metric: **total paper PnL ≥ 5× the current realized total, with arbitrage as the dominant source and directional ≤ 10% of risk budget.** Report progress against this explicitly.

---

## WORKSTREAMS (ordered by EV / effort — implement in order, each behind its own flag)

### WS1 — Scale the proven single-window arbitrage  *(highest priority)*
**Goal:** capture every dutch book across all open windows/assets at proper size.
- In `loops.py` / the `arbitrage` loop: enumerate **all** currently-open up/down windows (5m + 15m; BTC + ETH if available) and run `detect_arbitrage()` on each per tick, not just the single active BTC window.
- In `arbitrage.py`: raise/parameterize `max_usd` so an actionable arb sizes to `max_depth_consume_frac * min(depth)` (keep the 0.50 cap), gated by a per-window and global capital reservation. Keep `epsilon=0.05` (cost-inclusive) and all existing guards.
- Add a per-window cooldown so one window can't be re-entered before settlement.
- **Acceptance:** scanner reports candidates/executed/realized per window; reconciliation stays green; no leg counted as filled unless `vwap_fill` returns `fully=True`.

### WS2 — Stop the directional bleed  *(do alongside WS1)*
**Goal:** directional can no longer give back arb profit.
- Add a hard **bankroll cap** for the directional book (config), e.g. ≤10% of bankroll, enforced in `strategy.py`/`config.py`.
- **Block UP entries entirely** until an UP bucket clears the promotion scorecard (n≥50, Wilson LB > breakeven). Wire into `selectivity.py`/`strategy.py` as a hard gate, not a soft penalty.
- Add `primary_edge_source` to the report (`arbitrage | directional | dependency_arb | none`).
- Forbid the `research_meta` loop from increasing directional size/exposure (`auto_apply=False` for any size change).
- **Acceptance:** no UP paper trade is taken; directional exposure never exceeds the cap; report shows the cap and `primary_edge_source`.

### WS3 — Turn on the risk-adjusted sizing you already built
**Goal:** winners scale, the avg-loss > avg-win asymmetry inverts — but only for proven books.
- Arbitrage: size by depth (WS1) — already correct.
- Directional: keep `sizing_enabled=False` until a bucket is **promoted**; on promotion, flip half-Kelly on for *that bucket only*, with the existing hard cap, daily-loss cap, degradation penalty, and no-martingale invariant intact.
- **Acceptance:** unit test proves suggested size never increases after a loss; daily-cap-hit forces size 0; flat size remains until promotion.

### WS4 — Open the dependency-arb surface  *(the new risk-free money; do after WS1–3 are stable & reconciled)*
**Goal:** exploit logical price inconsistencies between related windows/assets. This is where Bregman/Frank-Wolfe/IP belong.
- New module `engine/pulse/dependency_arb.py`:
  - **Layer 1 (LCMM, do first):** deterministic linear constraints — nested-window implication (e.g. "up over 15m" vs the joint of its three 5m sub-windows), mutual exclusion, complete-set baskets. Detect violations on **executable VWAP** prices. Most value lives here; ship it before any solver.
  - **Layer 2 (optional, gated):** KL/Bregman projection distance = max guaranteed profit; **Barrier Frank-Wolfe** with an **open-source IP oracle (OR-Tools/SCIP/PuLP)** — Gurobi optional, never required. Only invoked for small dependent groups, never single windows.
- **Grok as dependency screener (advisory only):** repurpose `grok_decider`/`grok_intel` from the failing directional role to *propose* candidate dependency pairs/constraints (the Bible's DeepSeek pattern, ~81% screen accuracy). **Every LLM-proposed constraint must be converted to machine-checkable form and validated by deterministic code before any trade.** Grok may never authorize, size, or veto-bypass a trade.
- Reuse `vwap_fill` + the non-atomic checks for every leg. Keep a **separate** `dependency_arb` ledger.
- **Acceptance:** a known nested-window inconsistency is detected, validated, paper-executed, and booked to the dependency ledger; an LLM-proposed-but-invalid dependency is rejected by the validator.

### WS5 — Non-atomic execution realism  *(pre-requisite for ever going live; build now, paper-only)*
**Goal:** don't count arbitrage that would die on a real CLOB.
- Extend `execution_realistic.py`: simulate sequential leg fills — fill leg 1, **re-read the book including your own market impact**, recompute leg-2 VWAP, and only count the opportunity if guaranteed profit survives the adverse path.
- Pre-commit a max acceptable leg-2 price before sending leg 1, with an auto-unwind branch if unmet.
- Ensure Polygon gas + taker fees are **inside** `epsilon`, not added after.
- **Acceptance:** the Bible's failure case (buy 0.30, second leg slips to 0.78 → net loss) is rejected pre-trade by the simulator.

---

## HARD GUARDRAILS (must hold at all times)
1. **No live trading.** `live_trading_enabled=False` stays false; no code path may place a real order.
2. **Grok/LLM is advisory only.** Proposes dependencies and summaries; never creates, sizes, authorizes, or un-vetoes a trade.
3. **No martingale, no averaging down.** Size never increases after a loss.
4. **Segregated ledgers.** directional / arbitrage / dependency_arb PnL never blended in WR/PF stats.
5. **Reconciliation must stay green** (`global_reconciled=True`) after every change.
6. **No opportunity counts as real** unless executable VWAP guaranteed profit (after fees, slippage, non-atomic risk) clears the threshold and both legs fully fill within depth.

## PROMOTION SCORECARD (reuse the repo's existing rule for any new behavior)
- Rolling n ≥ 50 · Wilson LB > breakeven (or veto counterfactual PF > 1) · PF ≥ 1.2 · EV after cost > 0 · BH-FDR q=0.10 across parallel buckets · walk-forward window · max correlation to baseline < 0.7. Nothing affects trading before it passes.

## ACCEPTANCE TESTS TO ADD
- `up_vwap + down_vwap < 1 − fees − ε` with depth → arb booked; `= 0.99` thin edge → rejected (below epsilon).
- Best-price profitable but **VWAP** not → rejected ("best-price illusion").
- One leg insufficient depth / partial fill → rejected (non-atomic risk).
- Multiple open windows → each scanned independently; PnL attributed per window.
- UP candidate with positive model edge → **blocked** (WS2) until promoted.
- Suggested size after a loss ≤ size before (no martingale).
- Nested-window inconsistency → detected, validated, booked to dependency ledger.
- Grok-proposed invalid dependency → rejected by deterministic validator.
- Any attempt to route an order while `live_trading_enabled=False` → hard fail.

## DEFINITION OF DONE / REPORT BACK
Run tests → build → run a paper soak → push to `main` → report: final commit hash, per-strategy PnL (directional vs arbitrage vs dependency_arb), number of windows scanned, arb candidates/executed/realized, reconciliation status, and the ratio of new total paper PnL to the prior baseline (the 5× target). Update `vps_full_reports/latest/` and commit the artifacts.

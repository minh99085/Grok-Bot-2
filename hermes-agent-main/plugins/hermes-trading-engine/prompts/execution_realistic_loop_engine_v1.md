# Hermes Execution-Realistic Loop Engine v1 — Build Prompt (PAPER ONLY)

Workspace: `hermes-agent-main/plugins/hermes-trading-engine`
Role: Senior quant / trading-systems engineer. Improve Hermes using the repo, the latest full
report, Roan's Polymarket arbitrage math, and the Loop-Engineering framework. **PAPER ONLY — never
add a client/wallet/signing or enable live trading.**

## Why this prompt exists (synthesis)
The directional digital-option model is structurally negative-EV in a near-efficient binary market
(paper: ~ -13.6% return, profit factor < 0.9, avg loss > avg win, Brier 0.227 > market ~0.21; the
research loop already concluded "edge dies in execution / price ≈ probability"). Two external
frameworks point the same way:
- **Roan (arbitrage):** edge is mathematical infrastructure, not prediction. For a 2-outcome window
  the only real risk-free edge is the within-window dutch book `up_ask + down_ask < 1`. The heavy
  combinatorial machinery (Bregman projection / Frank-Wolfe / integer programming / Gurobi) is for
  multi-condition markets and is **OUT OF SCOPE** for this binary engine — do NOT add it.
- **Loop Engineering:** build ONE self-running loop with the six pieces (heartbeat, SKILL,
  STATE, verifier, worktrees, connectors), a maker-checker with a DIFFERENT verifier model,
  five stages (data → signal → verify → execute → monitor → memory), loss→rule learning, and
  **verifiable stop conditions that are NOT the agent's own opinion.** Lock scope to one strategy.

Decision: make the **risk-free arbitrage the single locked primary strategy**, and **de-risk the
directional engine to proven-winning-only** (it should go mostly quiet — that is the correct,
honest outcome in an efficient market). Keep arb P&L strictly segregated from directional P&L.

## Build tasks (in order; minimal, backward-compatible, paper-safe)

### 1. NEW MODULE `engine/pulse/arbitrage.py` — within-window dutch-book detector (Roan)
- Reuse `execution_gate.vwap_fill()`. For each window with both `up_book` and `down_book`:
  - **BUY-both:** walk `up_asks` + `down_asks` for size X; if `vwap_up + vwap_down < 1 - fees - epsilon`,
    guaranteed profit/share = `1 - (vwap_up + vwap_down)`. Size X = `min(up_ask_depth, down_ask_depth)`
    capped at the existing `exec_max_depth_consume_frac` (0.5).
  - **SELL-both:** if `best_bid_up + best_bid_down > 1 + fees + epsilon` → detect-and-LOG only
    (long-only paper ledger can't short; do not execute).
  - Fees/epsilon via `PULSE_ARB_*`, default `epsilon = 0.05`.
  - Return a typed `ArbOpportunity` (legs, sizes, vwaps, guaranteed_profit_usd, depth_capped).
- HONEST EXPECTATION: on a tight BTC pair the ask-sum is usually `> 1`; the detector will fire
  rarely. It is risk-free WHEN it fires. That is acceptable — correctness over frequency.

### 2. WIRE arb-first into the tick loop (before `decide()`)
- If an `ArbOpportunity` clears threshold, book BOTH legs as ONE linked paper position
  (`entry_mode="arbitrage"`) that settles deterministically to `1 - total_cost` regardless of
  outcome. Arb bypasses the directional/grok/selectivity *view* gates (it is risk-free, not a view)
  but MUST pass execution-realism per leg (full ladder fill, depth cap, tick size).
- CRITICAL: keep `global_reconciled == True` with the new 2-leg structure (accepted == fills ==
  ledger trades must still hold; design the linked position so the reconciler stays exact).

### 3. DE-RISK the directional engine behind env flags (default ON)
- Add `PULSE_DIRECTIONAL_ENABLED` (default keep current) so arb can run standalone.
- Convert selectivity from a blocklist to an ALLOWLIST for directional trades: only take a
  directional trade when the bucket has **Wilson-lower-bound win-rate > its own breakeven AND
  n >= 30** (enforced as a PRE-EXECUTION block, not advisory), AND the model's out-of-sample Brier
  beats the market's (reuse the existing market-beating benchmark). Expect near-zero directional
  trades until a bucket is proven — that is intended.

### 4. EXECUTION-REALISTIC EDGE fields + report (Roan Part IV; consolidate existing)
- Per candidate, emit one structured block: `raw_fair_p, calibrated_fair_p, market_price,
  top_of_book_edge, vwap_entry_price, slippage_bps, depth_available_usd, expected_fill_probability,
  max_win_profit_usd, max_loss_usd, reward_to_risk, breakeven_probability,
  calibrated_probability_margin, execution_realistic_ev`. Most exist already — assemble + add the
  3 new (`expected_fill_probability`, `calibrated_probability_margin`, `execution_realistic_ev`).
- Add the single-binary simplex residuals as DIAGNOSTICS: `abs(best_up + best_down - 1)` and
  `abs(vwap_up + vwap_down - 1)` (the arb signal, already executed in #1).
- Payoff-asymmetry guard: keep the underdog floor; add "reject high entry UNLESS
  calibrated_probability_margin is large" — must be margin-based, NOT a flat block (favorites are
  the +EV trades; do not kill them). Report `rejected_tiny_upside`, `rejected_bad_reward_to_risk`.

### 5. Grok → OBSERVE-ONLY by default; keep the maker-checker (Loop Eng #3)
- `grok_decider_mode` default `shadow` (`affects_trading=false`): Grok/predictor/analyst REPORT and
  are GRADED only; cannot trade/veto/resize/bypass. The deterministic floor owns execution.
- Keep Claude as the INDEPENDENT verifier (different model from the Grok maker), observe-graded.

### 6. VERIFIABLE STOP CONDITIONS — agent-independent kill switches (Loop Eng core)
- Add hard, quantitative, independently-checkable stops (NOT "the agent says it's done"):
  - rolling **win-rate Wilson lower bound** and **realized profit-factor** over the last N settled
    trades per strategy; **max-drawdown %** kill switch (halt a strategy when DD crosses a config %).
  - Surface each strategy's stop state in the loop registry (`stop_condition` becomes *verified*,
    not just declared). Arb has its own trivially-verifiable stop (guaranteed_profit must be > 0).

### 7. SKILL / STATE memory (Loop Eng #2)
- `LESSONS.md` is the SKILL rulebook (already self-grading/retracting) — every loss writes/updates a
  dated rule; stale rules retract. Additionally emit a `STATE.md` snapshot each persist (capital,
  open positions, active strategies, active stop states, active lessons) as the human-readable memory.

### 8. KL feature (Prompt-1, SAFE form only)
- Add `kl_model_vs_market = KL((p,1-p) || (m,1-m))` as an OBSERVE-ONLY graded feature in the report
  and Grok/Claude context. Do NOT use it as a trade trigger (the model is worse than the market, so
  large KL is anti-predictive — it is a no-trade signal, never a buy signal).

### 9. PROVENANCE artifacts (Prompt-2 R12)
- On full-report generation also write: `MANIFEST.txt`, `validation_full.txt`, `validation_light.txt`,
  git proof (commit hash), docker proof (image ids), env proof (key flags), `runtime_metrics`.

### 10. TESTS (`tests/test_pulse_arbitrage.py` + extend)
- arb detected when `up+down < 1-fees`; none when `>= 1`; depth cap respected; partial-fill
  rejected; arb P&L segregated from directional; Grok cannot affect trading by default; directional
  blocked unless Wilson-winning bucket (n>=30); stop-condition kill switch fires on DD breach;
  PAPER_ONLY / live-disabled enforced; `global_reconciled` stays True; provenance artifacts exist.
- Run SMALL first (paper, one asset, current cadence), watch where it breaks, write the lesson to
  LESSONS.md, repeat — do NOT wire many new signals at once.

## Hard constraints
- PAPER ONLY: no client/wallet/signing; do not flip any live flag.
- Do NOT add Frank-Wolfe / Bregman projection / integer programming / Gurobi (out of scope for a
  2-outcome market — arbitrage here is just `up_ask + down_ask < 1`).
- Do NOT blend arb and directional P&L in any win-rate / profit-factor stat.
- Keep all existing tests green; keep reconciliation True; lock scope to these two strategies.

## Deliver after edits
Final commit hash; tests passed; VPS synced hash (full `down --remove-orphans` → `build` →
`up -d --remove-orphans`); Grok observe-only proof; arb detected-vs-executed + guaranteed_profit;
execution_realistic_edge report section; payoff-guard counts; directional active-allowlist buckets;
segregated arb vs directional ledger stats; verifiable stop-condition states; full-report file list.

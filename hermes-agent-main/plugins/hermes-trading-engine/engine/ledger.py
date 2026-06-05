"""Canonical paper ledger (PAPER ONLY, pure, deterministic).

ONE source of truth for every paper decision and trade, used by reports, the
dashboard, the status endpoint, strategy attribution, and backtests — so equity,
attribution, calibration, and risk never disagree across surfaces.

Each :class:`LedgerEntry` records timestamp, market, strategy, signal version,
Bregman certificate id (if any), gross EV, fee-adjusted EV, fill-realism status,
order-book depth, filled/rejected quantity, fees, slippage, realized/unrealized/
after-cost PnL, exploration-vs-validation flag, calibration bucket, and risk
throttle state. From these the ledger derives equity, per-strategy attribution,
Brier/ECE, confidence-bucket + no-trade-bucket performance, Sharpe/Sortino/
Calmar/max-drawdown/CVaR, and strategy-level exposure.

:func:`reconcile_equity` enforces that dashboard / paper-training / report /
ledger equity reconcile within 1% (else the report fails).

Quant responsibilities
----------------------
* **Data ingestion / feature engineering** — callers populate entries from
  already-collected market data; the ledger performs no I/O.
* **Statistical / probabilistic modeling** — Brier/ECE + calibration buckets are
  computed from recorded ``predicted_prob`` / ``outcome`` pairs.
* **Bregman-priority signals** — entries carry the certificate id so executable
  arbitrage PnL is attributable.
* **Risk / portfolio** — risk-throttle state + strategy exposure + CVaR come from
  the same ledger the RiskEngine gated.
* **Backtesting / simulation / robustness** — risk-adjusted ratios reuse the
  backtest module; the ledger is the single return series.
* **CLOB v2 execution** — fill-realism status + depth + rejected qty recorded.
* **Monitoring** — equity reconciliation + attribution surfaced every cycle.
* **Compliance / security / ops** — PAPER-only; no wallet/order path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional

logger = logging.getLogger("hte.ledger")


def _f(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass
class LedgerEntry:
    """One paper decision or trade with full attribution/risk/calibration fields."""

    ts: float
    market: str
    strategy: str
    kind: str = "trade"                  # "trade" | "decision" (no-trade)
    traded: bool = False
    signal_version: str = ""
    bregman_certificate_id: Optional[str] = None
    gross_ev: float = 0.0
    fee_adjusted_ev: float = 0.0
    fill_realism_status: str = "n/a"     # filled | partial | rejected | n/a
    order_book_depth: float = 0.0
    filled_qty: float = 0.0
    rejected_qty: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    after_cost_pnl: float = 0.0
    notional: float = 0.0
    open: bool = False                   # position still open (carries unrealized)
    is_exploration: bool = False
    calibration_bucket: Optional[int] = None
    predicted_prob: Optional[float] = None
    outcome: Optional[int] = None        # resolved 1/0 (for Brier/ECE)
    risk_throttle_state: str = "none"

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class CanonicalLedger:
    """Append-only paper ledger; the single source for equity + metrics (pure)."""

    def __init__(self, *, starting_balance: float = 0.0):
        self.starting_balance = float(starting_balance)
        self.entries: list[LedgerEntry] = []

    # -- recording -----------------------------------------------------------
    def add(self, entry: LedgerEntry) -> LedgerEntry:
        self.entries.append(entry)
        return entry

    def record(self, **fields) -> LedgerEntry:
        return self.add(LedgerEntry(**fields))

    def trades(self) -> list:
        return [e for e in self.entries if e.traded]

    def decisions(self) -> list:
        return [e for e in self.entries if not e.traded]

    # -- equity --------------------------------------------------------------
    def realized_total(self) -> float:
        return round(sum(_f(e.realized_pnl) for e in self.entries), 8)

    def unrealized_total(self) -> float:
        return round(sum(_f(e.unrealized_pnl) for e in self.entries if e.open), 8)

    def after_cost_total(self) -> float:
        return round(sum(_f(e.after_cost_pnl) for e in self.entries), 8)

    def equity(self) -> float:
        """Canonical equity: starting + realized + open-unrealized PnL."""
        return round(self.starting_balance + self.realized_total()
                     + self.unrealized_total(), 8)

    # -- attribution ---------------------------------------------------------
    def attribution(self) -> dict:
        by: dict = {}
        for e in self.trades():
            row = by.setdefault(e.strategy, {
                "trades": 0, "gross_pnl": 0.0, "after_cost_pnl": 0.0,
                "realized_pnl": 0.0, "unrealized_pnl": 0.0,
                "exploration_pnl": 0.0, "validation_pnl": 0.0, "exposure": 0.0})
            row["trades"] += 1
            row["gross_pnl"] = round(row["gross_pnl"] + _f(e.realized_pnl) + _f(e.unrealized_pnl), 8)
            row["after_cost_pnl"] = round(row["after_cost_pnl"] + _f(e.after_cost_pnl), 8)
            row["realized_pnl"] = round(row["realized_pnl"] + _f(e.realized_pnl), 8)
            row["unrealized_pnl"] = round(row["unrealized_pnl"] + _f(e.unrealized_pnl), 8)
            tgt = "exploration_pnl" if e.is_exploration else "validation_pnl"
            row[tgt] = round(row[tgt] + _f(e.after_cost_pnl), 8)
            if e.open:
                row["exposure"] = round(row["exposure"] + _f(e.notional), 8)
        return by

    def strategy_exposure(self) -> dict:
        from engine.portfolio import exposure_summary
        return exposure_summary(self.trades(), key="strategy")

    # -- calibration ---------------------------------------------------------
    def _pairs(self) -> list:
        return [(float(e.predicted_prob), int(e.outcome)) for e in self.entries
                if e.predicted_prob is not None and e.outcome is not None]

    def calibration(self) -> dict:
        from engine.calibration_models import brier, ece
        pairs = self._pairs()
        return {"brier": brier(pairs) if pairs else None,
                "ece": ece(pairs) if pairs else None, "n": len(pairs)}

    def confidence_bucket_pnl(self, bins: int = 10) -> dict:
        """After-cost PnL + hit-rate per predicted-probability bucket."""
        out: dict = {}
        for e in self.trades():
            if e.calibration_bucket is not None:
                b = int(e.calibration_bucket)
            elif e.predicted_prob is not None:
                b = min(bins - 1, max(0, int(float(e.predicted_prob) * bins)))
            else:
                continue
            row = out.setdefault(b, {"n": 0, "after_cost_pnl": 0.0, "wins": 0})
            row["n"] += 1
            row["after_cost_pnl"] = round(row["after_cost_pnl"] + _f(e.after_cost_pnl), 8)
            if e.outcome is not None and int(e.outcome) == 1:
                row["wins"] += 1
        for b, row in out.items():
            row["hit_rate"] = round(row["wins"] / row["n"], 6) if row["n"] else None
        return out

    def no_trade_bucket(self) -> dict:
        """Performance of NO-TRADE decisions (would-be EV, never risked capital)."""
        ds = self.decisions()
        if not ds:
            return {"n": 0, "avg_gross_ev": None, "avg_fee_adjusted_ev": None,
                    "correctly_skipped": None}
        gross = [_f(e.gross_ev) for e in ds]
        fee_adj = [_f(e.fee_adjusted_ev) for e in ds]
        # a no-trade was "correct" when its fee-adjusted EV was <= 0 (rightly skipped)
        correct = sum(1 for e in ds if _f(e.fee_adjusted_ev) <= 0)
        return {"n": len(ds),
                "avg_gross_ev": round(sum(gross) / len(gross), 8),
                "avg_fee_adjusted_ev": round(sum(fee_adj) / len(fee_adj), 8),
                "correctly_skipped": round(correct / len(ds), 6)}

    # -- risk-adjusted metrics ----------------------------------------------
    def returns(self) -> list:
        """Per-resolved-trade after-cost return series (normalized by starting
        balance when available, else raw after-cost PnL)."""
        base = self.starting_balance if self.starting_balance > 0 else 1.0
        return [round(_f(e.after_cost_pnl) / base, 10)
                for e in self.trades() if not e.open]

    def equity_curve(self) -> list:
        eq = self.starting_balance
        curve = [round(eq, 8)]
        for e in self.trades():
            if not e.open:
                eq += _f(e.after_cost_pnl)
                curve.append(round(eq, 8))
        return curve

    def risk_metrics(self) -> dict:
        from engine.backtest import metrics_from_returns
        from engine.portfolio import cvar
        rets = self.returns()
        m = metrics_from_returns(rets)
        m["cvar"] = cvar(rets) if rets else 0.0
        m["n_returns"] = len(rets)
        return m

    # -- summary -------------------------------------------------------------
    def summary(self) -> dict:
        return {
            "starting_balance": self.starting_balance,
            "equity": self.equity(),
            "realized_pnl": self.realized_total(),
            "unrealized_pnl": self.unrealized_total(),
            "after_cost_pnl": self.after_cost_total(),
            "n_entries": len(self.entries),
            "n_trades": len(self.trades()),
            "n_decisions": len(self.decisions()),
            "attribution": self.attribution(),
            "strategy_exposure": self.strategy_exposure(),
            "calibration": self.calibration(),
            "confidence_bucket_pnl": self.confidence_bucket_pnl(),
            "no_trade_bucket": self.no_trade_bucket(),
            "risk_metrics": self.risk_metrics(),
        }

    @classmethod
    def from_entries(cls, entries: Iterable[dict], *, starting_balance: float = 0.0
                     ) -> "CanonicalLedger":
        led = cls(starting_balance=starting_balance)
        for d in entries or []:
            led.add(LedgerEntry(**{k: v for k, v in d.items()
                                   if k in LedgerEntry.__dataclass_fields__}))
        return led


def reconcile_equity(equities: dict, *, tolerance_pct: float = 1.0) -> dict:
    """Reconcile equity across surfaces (dashboard / paper-training / report /
    ledger) within ``tolerance_pct`` percent (pure, deterministic).

    Returns ``{ok, max_rel_diff_pct, values, failed_pairs, tolerance_pct}``. With
    fewer than two non-null values it trivially reconciles. The report MUST fail
    when ``ok`` is False (equity inconsistency above the tolerance)."""
    vals = {k: _f(v) for k, v in (equities or {}).items() if v is not None}
    if len(vals) < 2:
        return {"ok": True, "max_rel_diff_pct": 0.0, "values": vals,
                "failed_pairs": [], "tolerance_pct": tolerance_pct}
    keys = list(vals)
    max_rel = 0.0
    failed: list = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = vals[keys[i]], vals[keys[j]]
            denom = max(abs(a), abs(b), 1.0)
            rel = abs(a - b) / denom * 100.0
            max_rel = max(max_rel, rel)
            if rel > tolerance_pct:
                failed.append({"pair": [keys[i], keys[j]],
                               "values": [round(a, 6), round(b, 6)],
                               "rel_diff_pct": round(rel, 4)})
    ok = not failed
    if not ok:
        logger.warning("equity reconciliation FAILED (> %.2f%%): %s", tolerance_pct, failed)
    return {"ok": bool(ok), "max_rel_diff_pct": round(max_rel, 4), "values": vals,
            "failed_pairs": failed, "tolerance_pct": tolerance_pct}

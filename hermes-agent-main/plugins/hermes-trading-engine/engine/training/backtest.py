"""Tier-1 walk-forward backtest + out-of-sample validation harness (PAPER / RESEARCH ONLY).

Given chronological point-in-time observations (see :mod:`historical_dataset`), this:

* splits TIME-ORDERED into in-sample (train) and out-of-sample (test) — no leakage,
* fits a calibration model on TRAIN only (Platt/temperature/isotonic via the institutional
  calibrator), then measures OOS calibration (Brier / log-loss / ECE / reliability),
* runs a directional after-cost BACKTEST on the TEST set using the calibrated model as the
  signal vs the market price, and reports expectancy, hit-rate, Sharpe, profit factor, and
  trade count — the OOS, settlement-grounded edge evidence an institution requires BEFORE
  allocating.

It NEVER trades, sizes, or touches a live venue — it produces a validation report (and an
optional warm-start dataset). Deterministic given its inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from engine.replay import metrics as _m
from engine.calibration_models import InstitutionalCalibrator


@dataclass
class BacktestConfig:
    train_frac: float = 0.7          # chronological in-sample fraction
    edge_threshold: float = 0.0      # required AFTER-COST edge to take a paper-backtest trade
    cost_per_trade: float = 0.0      # flat per-share cost (fees + half-spread + slippage proxy)
    calibration_method: str = "auto"
    min_calibration_samples: int = 20


def time_split(observations: list, train_frac: float = 0.7) -> "tuple[list, list]":
    """Split CHRONOLOGICALLY (by observed_ts) into (train, test). No shuffling — the test
    set is strictly later than the train set, so the calibration can never see the future."""
    obs = sorted(observations or [], key=lambda o: float(getattr(o, "observed_ts", 0.0)))
    n = len(obs)
    k = max(0, min(n, int(round(n * float(train_frac)))))
    return obs[:k], obs[k:]


def calibration_report(preds: list, outs: list, *, bins: int = 10) -> dict:
    """Brier / log-loss / ECE + reliability buckets for predicted probabilities vs
    realized 0/1 outcomes (all from :mod:`engine.replay.metrics`)."""
    preds = [float(p) for p in preds]
    outs = [float(o) for o in outs]
    n = len(preds)
    rel: dict = {}
    for p, o in zip(preds, outs):
        b = min(bins - 1, int(p * bins))
        r = rel.setdefault(b, {"n": 0, "sum_pred": 0.0, "wins": 0.0})
        r["n"] += 1
        r["sum_pred"] += p
        r["wins"] += o
    buckets = [{"bucket": b, "n": r["n"],
                "predicted": round(r["sum_pred"] / r["n"], 4),
                "actual": round(r["wins"] / r["n"], 4),
                "gap": round(abs(r["sum_pred"] / r["n"] - r["wins"] / r["n"]), 4)}
               for b, r in sorted(rel.items()) if r["n"] > 0]
    return {
        "n": n,
        "brier": _m.brier_score(preds, outs) if n else None,
        "log_loss": _m.log_loss(preds, outs) if n else None,
        "ece": _m.ece(preds, outs, bins=bins) if n else None,
        "base_rate": round(sum(outs) / n, 4) if n else None,
        "reliability_buckets": buckets,
    }


def directional_backtest(observations: list, *, signal: Callable[[float], float],
                         edge_threshold: float = 0.0, cost_per_trade: float = 0.0,
                         starting_bankroll: float = 100.0) -> dict:
    """Backtest a directional paper strategy over OOS observations.

    For each observation the ``signal(observed_prob) -> p_model`` gives the strategy's YES
    probability. We take the side whose AFTER-COST edge clears ``edge_threshold`` (YES edge
    = p_model − price − cost; NO edge = (price − p_model) − cost), then settle the (paper)
    1-share trade against the realized outcome. Returns expectancy, hit-rate, Sharpe (over
    the trade-sequence equity curve), profit factor, and trade count. No real orders."""
    trade_pnls: list[float] = []
    equity = [float(starting_bankroll)]
    wins = sides_yes = sides_no = 0
    for o in (observations or []):
        price = float(getattr(o, "observed_prob", 0.5))
        outcome = int(getattr(o, "outcome", 0))
        p_model = max(0.0, min(1.0, float(signal(price))))
        yes_edge = (p_model - price) - cost_per_trade
        no_edge = (price - p_model) - cost_per_trade
        if yes_edge >= no_edge and yes_edge > edge_threshold:
            pnl = (outcome - price) - cost_per_trade          # buy YES @ price, settle 0/1
            sides_yes += 1
        elif no_edge > edge_threshold:
            pnl = ((1 - outcome) - (1 - price)) - cost_per_trade   # buy NO @ (1-price)
            sides_no += 1
        else:
            continue                                          # no qualifying edge -> no trade
        trade_pnls.append(round(pnl, 6))
        equity.append(equity[-1] + pnl)
        wins += 1 if pnl > 0 else 0
    n = len(trade_pnls)
    return {
        "trades": n,
        "sides": {"yes": sides_yes, "no": sides_no},
        "total_pnl": round(sum(trade_pnls), 6),
        "expectancy": _m.expectancy(trade_pnls) if n else 0.0,
        "hit_rate": round(wins / n, 4) if n else 0.0,
        "profit_factor": _m.profit_factor(trade_pnls) if n else 0.0,
        "sharpe": _m.sharpe(equity) if n else 0.0,
        "max_drawdown_pct": round(_m.max_drawdown(equity)[0], 6) if n else 0.0,
    }


def walk_forward_validate(observations: list, *, cfg: Optional[BacktestConfig] = None) -> dict:
    """Full Tier-1 validation: chronological split, TRAIN-only calibration fit, OOS
    calibration + OOS directional backtest (calibrated model vs raw market). Returns a
    structured report; never trades. ``promotable`` is an advisory flag — the live readiness
    gate (6C) remains the authority."""
    cfg = cfg or BacktestConfig()
    train, test = time_split(observations, cfg.train_frac)
    out = {
        "schema": "backtest_validation/1.0",
        "observations_total": len(observations or []),
        "train_n": len(train), "test_n": len(test),
        "train_frac": cfg.train_frac, "edge_threshold": cfg.edge_threshold,
        "cost_per_trade": cfg.cost_per_trade,
        "no_look_ahead": True, "paper_only": True, "live_trading_enabled": False,
    }
    if len(train) < cfg.min_calibration_samples or not test:
        out["status"] = "insufficient_samples"
        out["promotable"] = False
        return out

    cal = InstitutionalCalibrator(method=cfg.calibration_method,
                                  min_samples=cfg.min_calibration_samples)
    cal.fit([o.as_pair() for o in train])

    test_prices = [o.observed_prob for o in test]
    test_outs = [o.outcome for o in test]
    test_cal = [cal._model.transform(p) for p in test_prices]      # calibrated OOS preds

    out["raw_market_oos_calibration"] = calibration_report(test_prices, test_outs)
    out["calibrated_oos_calibration"] = calibration_report(test_cal, test_outs)
    out["calibration_artifact"] = cal.to_artifact()

    # OOS directional backtest: calibrated model vs the market (the strategy that fitting a
    # calibration on history implies). Also report the raw-market baseline for contrast.
    out["calibrated_model_backtest"] = directional_backtest(
        test, signal=lambda p: cal._model.transform(p),
        edge_threshold=cfg.edge_threshold, cost_per_trade=cfg.cost_per_trade)
    out["raw_market_baseline_backtest"] = directional_backtest(
        test, signal=lambda p: p,            # market == model -> only trades if cost<0 (none)
        edge_threshold=cfg.edge_threshold, cost_per_trade=cfg.cost_per_trade)

    bt = out["calibrated_model_backtest"]
    raw_ece = out["raw_market_oos_calibration"]["ece"] or 0.0
    cal_ece = out["calibrated_oos_calibration"]["ece"] or 0.0
    out["calibration_improved_oos"] = bool(cal_ece <= raw_ece)
    # advisory promotable: OOS calibration did not degrade AND the calibrated strategy is
    # after-cost positive on a non-trivial number of held-out trades. NOT a live gate.
    out["promotable"] = bool(out["calibration_improved_oos"]
                             and bt["trades"] >= 30 and bt["expectancy"] > 0.0)
    out["status"] = "ok"
    return out

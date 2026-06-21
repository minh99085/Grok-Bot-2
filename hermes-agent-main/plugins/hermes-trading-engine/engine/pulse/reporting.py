"""Light-report assembly + learning loop for the BTC 5-min pulse.

Aggregates settled-outcome PnL/calibration across every entry-time tag dimension (Hurst regime,
z-score bucket, half-life bucket, Markov state, time-to-resolution, spread bucket, depth bucket,
confidence tier) and assembles the full latest light report — including candidate lifecycle
reconciliation, execution stats, reject reasons, EV before/after costs, calibration table,
sample sizes, missing-data reasons, and promotion/demotion candidates. Report-only.
"""

from __future__ import annotations

from typing import Optional


def spread_bucket(s: Optional[float]) -> str:
    if s is None:
        return "na"
    if s <= 0.01:
        return "<=0.01"
    if s <= 0.03:
        return "0.01-0.03"
    if s <= 0.06:
        return "0.03-0.06"
    return ">0.06"


def depth_bucket(d: Optional[float]) -> str:
    if d is None:
        return "na"
    if d < 50:
        return "<50"
    if d < 200:
        return "50-200"
    if d < 1000:
        return "200-1000"
    return ">=1000"


def confidence_tier(c: Optional[float]) -> str:
    if c is None:
        return "na"
    if c < 0.34:
        return "low"
    if c < 0.67:
        return "medium"
    return "high"


class OutcomeGroups:
    """Groups settled paper PnL / win-rate / Brier by every entry-time tag dimension."""

    def __init__(self):
        self.dims: dict = {}

    def record(self, tags: dict, *, pnl: float, won: bool, fair_at_entry: Optional[float],
               outcome_up: Optional[bool]) -> None:
        for dim, bucket in (tags or {}).items():
            d = self.dims.setdefault(dim, {})
            g = d.setdefault(str(bucket if bucket is not None else "na"),
                             {"n": 0, "wins": 0, "pnl": 0.0, "brier_sum": 0.0, "brier_n": 0})
            g["n"] += 1
            g["wins"] += int(bool(won))
            g["pnl"] = round(g["pnl"] + float(pnl), 6)
            if fair_at_entry is not None and outcome_up is not None:
                g["brier_sum"] += (float(fair_at_entry) - (1.0 if outcome_up else 0.0)) ** 2
                g["brier_n"] += 1

    def summary(self) -> dict:
        out = {}
        for dim, buckets in self.dims.items():
            out[dim] = {b: {"n": g["n"],
                            "win_rate": (round(g["wins"] / g["n"], 4) if g["n"] else None),
                            "pnl_usd": round(g["pnl"], 4),
                            "brier": (round(g["brier_sum"] / g["brier_n"], 4) if g["brier_n"] else None)}
                        for b, g in buckets.items()}
        return out


def promotion_demotion(tier_table: dict) -> dict:
    """From the report-only tier table, list promotion (A+/A) and demotion (C/D) candidates."""
    table = (tier_table or {}).get("table", {})
    promote = [k for k, v in table.items() if v.get("tier") in ("A+", "A")]
    demote = [k for k, v in table.items() if v.get("tier") in ("C", "D")]
    return {"promotion_candidates": promote, "demotion_candidates": demote}


def build_light_report(*, lifecycle: dict, execution_gate: dict, ledger_stats: dict,
                       calibration: dict, ev_stats: dict, outcome_groups: OutcomeGroups,
                       tier_table: dict, edge_model: dict, sizing: dict,
                       missing_data_reasons: dict, baseline: dict,
                       gate_thresholds: dict, gate_observations: dict) -> dict:
    from engine.pulse.reconciliation import global_reconciliation, zero_reject_diagnostic
    grouped = outcome_groups.summary()
    accepted = lifecycle.get("terminals", {}).get("accepted", 0)
    settled = ledger_stats.get("settled", 0)
    pnl_by = {f"pnl_by_{dim}": g for dim, g in grouped.items()}
    recon = global_reconciliation(lifecycle=lifecycle, exec_gate=execution_gate,
                                  ledger_stats=ledger_stats, baseline=baseline)
    zero_diag = zero_reject_diagnostic(
        exec_gate=execution_gate, thresholds=gate_thresholds, observations=gate_observations,
        rejected_before_execution=recon.get("rejected_before_execution", 0))
    return {
        "schema": "btc_pulse_light_report/1.1", "report_only": True, "live_trading_enabled": False,
        # headline integrity flag — true ONLY when every lifecycle/exec/ledger identity holds
        "global_reconciled": recon["global_reconciled"],
        "reconciliation": recon,
        "execution_gate_zero_reject_diagnostic": zero_diag,
        "candidate_lifecycle": lifecycle,
        "execution_stats": execution_gate,
        "reject_reasons": execution_gate.get("rejected", {}),
        "ev_before_after_costs": ev_stats,
        "ledger": ledger_stats,
        "calibration": calibration,
        "edge_model_calibration": edge_model.get("calibration_table", {}),
        "sample_sizes": {"accepted": accepted, "settled": settled,
                         "candidates": lifecycle.get("created", 0),
                         "edge_model_labeled": edge_model.get("n_labeled", 0)},
        "missing_data_reasons": missing_data_reasons,
        "confidence_tier_table": tier_table,
        "sizing": sizing,
        **pnl_by,
        **promotion_demotion(tier_table),
    }

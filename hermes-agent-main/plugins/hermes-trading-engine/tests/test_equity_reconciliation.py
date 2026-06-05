"""Tests for cross-surface equity reconciliation (dashboard/paper/report/ledger)."""

from __future__ import annotations

from engine.ledger import reconcile_equity


def test_reconciles_when_within_1pct():
    r = reconcile_equity({"dashboard": 500.0, "paper_training": 502.0,
                          "report": 500.5, "ledger": 501.0}, tolerance_pct=1.0)
    assert r["ok"] is True
    assert r["max_rel_diff_pct"] <= 1.0
    assert r["failed_pairs"] == []


def test_fails_when_beyond_1pct():
    r = reconcile_equity({"dashboard": 500.0, "ledger": 600.0}, tolerance_pct=1.0)
    assert r["ok"] is False
    assert r["max_rel_diff_pct"] > 1.0
    assert r["failed_pairs"]
    pair = r["failed_pairs"][0]
    assert set(pair["pair"]) == {"dashboard", "ledger"}


def test_single_value_trivially_reconciles():
    assert reconcile_equity({"ledger": 500.0})["ok"] is True
    assert reconcile_equity({})["ok"] is True


def test_none_values_ignored():
    r = reconcile_equity({"dashboard": None, "ledger": 500.0, "report": 500.0})
    assert r["ok"] is True
    assert "dashboard" not in r["values"]


def test_exactly_1pct_passes():
    # 500 vs 505 -> 5/505 = 0.990% <= 1% tolerance
    r = reconcile_equity({"a": 500.0, "b": 505.0}, tolerance_pct=1.0)
    assert r["ok"] is True


def test_report_generation_flags_equity_mismatch(tmp_path):
    # a ledger equity far from the paper-training equity -> report reconciliation fails
    import json
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"))
    import generate_bot_inspection_report as gen  # noqa: E402

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "polymarket_training.json").write_text(json.dumps({
        "mode": "paper", "pnl": {"equity": 500.0, "after_cost_pnl": 1.0},
        "safety": {"ok": True}}), encoding="utf-8")
    (data_dir / "paper_ledger.json").write_text(json.dumps({
        "starting_balance": 500.0,
        "entries": [{"ts": 1.0, "market": "m", "strategy": "bregman", "traded": True,
                     "realized_pnl": 200.0, "after_cost_pnl": 200.0}]}),  # equity 700 vs 500
        encoding="utf-8")

    def runner(cmd, cwd, timeout):
        return (0, "git" if cmd[:1] == ["git"] else "", "")

    res = gen.generate_report(
        output_dir=str(tmp_path / "out"), repo_root=str(tmp_path), data_dir=str(data_dir),
        skip_tests=True, include_docker=False, include_api=False, include_artifacts=False,
        runner=runner, opener=lambda u, t: (0, "x"))
    assert res["equity_reconciled"] is False
    assert any("EQUITY RECONCILIATION FAILED" in w for w in res["warnings"])

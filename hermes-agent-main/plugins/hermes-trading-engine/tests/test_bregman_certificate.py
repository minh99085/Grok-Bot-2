"""Tests for engine.arbitrage.certificate (cost/depth-aware). Tests-first."""

from __future__ import annotations

from engine.arbitrage.certificate import (Certificate, FeeModel, certify_group,
                                          _worst_case_payoff)
from engine.arbitrage.constraint_graph import ConstraintGraph, Outcome


def _graph_complement(pa: float, pb: float, da: float = 100.0, db: float = 100.0):
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="a", price=pa, ask=pa, ask_depth=da))
    g.add_outcome(Outcome(id="b", price=pb, ask=pb, ask_depth=db))
    c = g.add_complement("a", "b")
    return g, c


def test_worst_case_payoff_is_min_over_atoms():
    atoms = [{"a": 1, "b": 0}, {"a": 0, "b": 1}]
    assert _worst_case_payoff({"a": 1.0, "b": 1.0}, atoms) == 1.0
    atoms_with_zero = atoms + [{"a": 0, "b": 0}]
    assert _worst_case_payoff({"a": 1.0, "b": 1.0}, atoms_with_zero) == 0.0


def test_underpriced_complement_certifies():
    g, c = _graph_complement(0.4, 0.4, da=100, db=50)
    cert = certify_group(g, c, profit_floor=0.005)
    assert cert.certified is True
    assert cert.worst_case_payoff_per_set == 1.0
    assert abs(cert.cost_per_set - 0.8) < 1e-9
    assert abs(cert.after_fee_profit_per_set - 0.2) < 1e-9
    assert cert.size == 50.0                       # depth-bounded (min leg)
    assert abs(cert.total_after_fee_profit - 0.2 * 50) < 1e-6
    assert cert.deterministic is True


def test_fairly_priced_complement_not_certified():
    g, c = _graph_complement(0.5, 0.5)
    cert = certify_group(g, c, profit_floor=0.005)
    assert cert.certified is False
    assert cert.reason == "no_positive_worst_case_profit"


def test_fees_can_block_certification():
    g, c = _graph_complement(0.49, 0.49)            # gross edge 0.02
    cert = certify_group(g, c, fee_model=FeeModel(taker_fee_bps=300), profit_floor=0.005)
    # 0.02 - fees(~0.029) < floor -> not certified
    assert cert.certified is False


def test_zero_depth_is_not_fill_feasible():
    g, c = _graph_complement(0.4, 0.4, da=0, db=0)
    cert = certify_group(g, c, profit_floor=0.005)
    assert cert.certified is False
    assert cert.fill_feasible is False
    assert cert.reason == "no_depth"


def test_mece_underpriced_certifies():
    g = ConstraintGraph()
    for i in ("x", "y", "z"):
        g.add_outcome(Outcome(id=i, price=0.3, ask=0.3, ask_depth=10))
    c = g.add_mece(["x", "y", "z"])
    cert = certify_group(g, c, profit_floor=0.005)
    assert cert.certified is True
    assert abs(cert.after_fee_profit_per_set - 0.1) < 1e-9
    assert cert.atoms_checked == 3


def test_mutually_exclusive_never_certifies_buy_set():
    # ME includes the all-zero state -> worst-case payoff 0 -> no arb.
    g = ConstraintGraph()
    g.add_outcome(Outcome(id="a", price=0.2, ask=0.2, ask_depth=10))
    g.add_outcome(Outcome(id="b", price=0.2, ask=0.2, ask_depth=10))
    c = g.add_mutually_exclusive(["a", "b"])
    cert = certify_group(g, c, profit_floor=0.005)
    assert cert.certified is False
    assert cert.worst_case_payoff_per_set == 0.0


def test_certificate_to_dict():
    g, c = _graph_complement(0.4, 0.4)
    d = certify_group(g, c).to_dict()
    for k in ("certified", "worst_case_payoff_per_set", "after_fee_profit_per_set",
              "size", "portfolio", "atoms_checked", "reason"):
        assert k in d

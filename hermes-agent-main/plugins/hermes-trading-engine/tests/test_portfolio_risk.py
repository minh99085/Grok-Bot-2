"""Tests for engine.portfolio (Kelly, CVaR, drawdown, optimizer) + risk wrappers."""

from __future__ import annotations

from engine.portfolio import (
    Allocation,
    Candidate,
    PortfolioCaps,
    PortfolioOptimizer,
    cvar,
    drawdown_throttle,
    fractional_kelly_size,
    value_at_risk,
)
from engine import risk as risk_mod


# --- fractional Kelly --------------------------------------------------------
def test_kelly_positive_edge_sizes_up():
    s = fractional_kelly_size(edge=0.10, price=0.50, bankroll=1000,
                              fraction=0.5, cap_frac=1.0)
    assert s > 0


def test_kelly_zero_for_nonpositive_edge():
    assert fractional_kelly_size(edge=0.0, price=0.5, bankroll=1000) == 0.0
    assert fractional_kelly_size(edge=-0.1, price=0.5, bankroll=1000) == 0.0


def test_kelly_respects_cap():
    s = fractional_kelly_size(edge=0.9, price=0.10, bankroll=1000,
                              fraction=1.0, cap_frac=0.05)
    assert s <= 0.05 * 1000 + 1e-6


def test_kelly_fraction_scales():
    full = fractional_kelly_size(edge=0.1, price=0.5, bankroll=1000,
                                 fraction=1.0, cap_frac=1.0)
    half = fractional_kelly_size(edge=0.1, price=0.5, bankroll=1000,
                                 fraction=0.5, cap_frac=1.0)
    assert abs(half - full * 0.5) < 1e-6


# --- CVaR / VaR --------------------------------------------------------------
def test_cvar_is_mean_of_worst_tail():
    rets = [-0.5, -0.4, -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    es = cvar(rets, alpha=0.9)  # worst 10% -> just -0.5
    assert es == -0.5
    assert value_at_risk(rets, alpha=0.9) == -0.5


def test_cvar_empty_is_zero():
    assert cvar([]) == 0.0
    assert value_at_risk([]) == 0.0


def test_cvar_worse_than_var():
    rets = [-0.9, -0.5, -0.2, 0.1, 0.3]
    assert cvar(rets, 0.6) <= value_at_risk(rets, 0.6)


# --- drawdown throttle -------------------------------------------------------
def test_drawdown_throttle_band():
    assert drawdown_throttle(0.0, soft=0.1, hard=0.2) == 1.0
    assert drawdown_throttle(0.05, soft=0.1, hard=0.2) == 1.0
    assert drawdown_throttle(0.2, soft=0.1, hard=0.2) == 0.0
    assert drawdown_throttle(0.3, soft=0.1, hard=0.2) == 0.0
    mid = drawdown_throttle(0.15, soft=0.1, hard=0.2)
    assert 0.0 < mid < 1.0


# --- optimizer ---------------------------------------------------------------
def _arb(id, profit, notional, **kw):
    return Candidate(id=id, kind="arbitrage", certified=True,
                     after_cost_profit=profit, desired_notional=notional, **kw)


def _edge(id, edge, price=0.5, **kw):
    return Candidate(id=id, kind="edge", edge=edge, price=price, **kw)


def test_optimizer_prefers_guaranteed_arbitrage():
    opt = PortfolioOptimizer(PortfolioCaps(max_total_exposure_frac=0.30))
    cands = [_edge("e1", 0.2), _arb("a1", 5.0, 200.0)]
    allocs = {a.id: a for a in opt.allocate(cands, equity=1000)}
    assert allocs["a1"].notional > 0
    assert allocs["a1"].reason == "certified_arbitrage_priority"
    # total cap is 300; arb takes 200, edge gets the remainder (<=100)
    assert allocs["a1"].notional + allocs["e1"].notional <= 0.30 * 1000 + 1e-6


def test_uncertified_arb_gets_zero():
    opt = PortfolioOptimizer()
    c = Candidate(id="a", kind="arbitrage", certified=False,
                  after_cost_profit=1.0, desired_notional=100)
    a = opt.allocate([c], equity=1000)[0]
    assert a.notional == 0.0
    assert a.reason == "uncertified_no_size"


def test_fantasy_fill_zero_size():
    opt = PortfolioOptimizer()
    c = _arb("a", 5.0, 100.0)
    c.fantasy = True
    a = opt.allocate([c], equity=1000)[0]
    assert a.notional == 0.0
    assert a.reason == "fantasy_fill_rejected"


def test_drawdown_halt_zeros_edge_but_arb_only_capped():
    opt = PortfolioOptimizer(PortfolioCaps(dd_soft=0.1, dd_hard=0.2))
    cands = [_edge("e1", 0.3), _arb("a1", 5.0, 100.0)]
    allocs = {a.id: a for a in opt.allocate(cands, equity=1000, drawdown=0.25)}
    assert allocs["e1"].notional == 0.0
    assert allocs["e1"].reason == "drawdown_halt"
    assert allocs["a1"].notional > 0  # guaranteed arb still allowed


def test_per_event_cap_enforced():
    opt = PortfolioOptimizer(PortfolioCaps(max_event_exposure_frac=0.10,
                                           max_total_exposure_frac=0.90))
    cands = [_arb("a1", 5.0, 500.0, event_id="E"),
             _arb("a2", 4.0, 500.0, event_id="E")]
    allocs = {a.id: a for a in opt.allocate(cands, equity=1000)}
    # event cap = 100 total across both
    assert allocs["a1"].notional + allocs["a2"].notional <= 0.10 * 1000 + 1e-6


def test_cvar_scaling_reduces_edge_size():
    caps = PortfolioCaps(cvar_limit_frac=0.05, cvar_alpha=0.9,
                         max_total_exposure_frac=1.0)
    opt = PortfolioOptimizer(caps)
    bad_returns = [-0.5] * 5 + [0.1] * 5
    a_no = opt.allocate([_edge("e", 0.2)], equity=1000)[0]
    a_cvar = opt.allocate([_edge("e", 0.2)], equity=1000, returns=bad_returns)[0]
    assert a_cvar.notional < a_no.notional
    assert "cvar_scaled" in a_cvar.reason


# --- risk.py wrappers --------------------------------------------------------
def test_risk_wrappers_delegate():
    assert risk_mod.kelly_position_size(edge=0.1, price=0.5, equity=1000) > 0
    assert risk_mod.portfolio_cvar([-0.5, 0.1, 0.2], 0.9) <= 0
    assert risk_mod.drawdown_throttle_factor(0.0) == 1.0


def test_per_event_and_correlated_caps():
    assert risk_mod.per_event_exposure_ok(new_notional=50, event_exposure=200,
                                          equity=1000, max_event_frac=0.25) is True
    assert risk_mod.per_event_exposure_ok(new_notional=60, event_exposure=200,
                                          equity=1000, max_event_frac=0.25) is False
    assert risk_mod.correlated_exposure_ok(new_notional=50, cluster_exposure=250,
                                           equity=1000, max_cluster_frac=0.30) is True
    assert risk_mod.correlated_exposure_ok(new_notional=60, cluster_exposure=250,
                                           equity=1000, max_cluster_frac=0.30) is False

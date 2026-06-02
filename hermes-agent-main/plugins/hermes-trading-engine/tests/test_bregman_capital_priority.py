"""Certified-Bregman capital priority.

Quant scope — *Signal Generation with Bregman priority* + *Risk Management*:
proves a certified Bregman opportunity is routed to the first-priority capital
bucket and funded ahead of directional edge, that a NON-certified Bregman
candidate gets zero capital (audit/log only), and that the certified-Bregman
bucket exposure cap is honoured. Certification is the only gate that grants
first priority. PAPER ONLY — no live execution.
"""

from __future__ import annotations

from engine.training.capital_allocator import (
    BUCKET_BREGMAN, BUCKET_DIRECTIONAL, CAPITAL_BUCKETS, AdaptiveCapitalAllocator,
    CapitalCandidate)


def _allocator():
    return AdaptiveCapitalAllocator()


def _certified_bregman(net=0.04, market="b1"):
    return CapitalCandidate(
        strategy="bregman", market_id=market, event_group="evt-b",
        price=0.5, p_final=0.7, gross_edge=net, net_after_cost_edge=net,
        bregman=True, bregman_certified=True)


def _directional(net=0.05, market="d1"):
    return CapitalCandidate(
        strategy="directional", market_id=market, event_group="evt-d",
        price=0.5, p_final=0.7, gross_edge=net, net_after_cost_edge=net)


def test_bregman_bucket_is_first_priority():
    assert CAPITAL_BUCKETS[0] == BUCKET_BREGMAN


def test_certified_bregman_is_funded_in_bregman_bucket():
    d = _allocator().allocate(_certified_bregman())
    assert d.approved is True
    assert d.bucket == BUCKET_BREGMAN
    assert d.notional_usd > 0.0


def test_non_certified_bregman_gets_zero_capital():
    cand = _certified_bregman()
    cand.bregman_certified = False
    d = _allocator().allocate(cand)
    assert d.approved is False
    assert d.notional_usd == 0.0
    assert "certif" in d.reason.lower()


def test_certified_bregman_preempts_directional_priority():
    alloc = _allocator()
    decisions = alloc.allocate_batch([_directional(), _certified_bregman()])
    # certified bregman ranked first among the approved decisions
    approved = [d for d in decisions if d.approved]
    assert approved
    assert approved[0].bucket == BUCKET_BREGMAN


def test_bregman_bucket_cap_is_respected():
    # tiny bregman bucket cap -> later certified bundles are rejected by cap
    alloc = AdaptiveCapitalAllocator(bucket_caps={BUCKET_BREGMAN: 6.0})
    first = alloc.allocate(_certified_bregman(market="b1"),
                           bucket_exposure={BUCKET_BREGMAN: 0.0})
    assert first.approved and first.notional_usd > 0.0
    # bucket already (nearly) full -> next certified bregman blocked
    full = alloc.allocate(_certified_bregman(market="b2"),
                          bucket_exposure={BUCKET_BREGMAN: 6.0})
    assert full.approved is False
    assert "bucket" in full.reason.lower() or "cap" in full.reason.lower()


def test_directional_still_allocates_when_bucket_has_room():
    d = _allocator().allocate(_directional())
    assert d.approved is True
    assert d.bucket == BUCKET_DIRECTIONAL
    assert d.notional_usd > 0.0

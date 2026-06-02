"""Bregman group settlement validation across ALL legs.

A certified Bregman opportunity is only validated against settlement TRUTH when
every leg resolves cleanly. Any unresolved leg => cannot validate yet; any
void/ambiguous/stale leg => partially_invalid (excluded from learning); realized
payout below the certified lower bound => violated. PAPER-ONLY; no network.
"""

from __future__ import annotations

from engine.training.settlement import (
    BregmanSettlementValidator,
    LabelState,
    SettlementLabel,
)


def _label(market_id, state, side_winner="YES"):
    return SettlementLabel(market_id=market_id, state=state, confidence=0.95,
                           source="uma", winning_outcome=side_winner)


# A 2-leg hedged group: buy YES on A @0.40 and buy NO on B @0.55, 1 unit each.
# If A resolves YES (leg A settles 1.0) and B resolves NO (leg B settles 1.0):
#   payout = (1-0.40) + (1-0.55) = 0.60 + 0.45 = 1.05  > certified bound 0.02
def _legs():
    return [
        {"market_id": "A", "side": "YES", "entry_price": 0.40, "qty": 1.0},
        {"market_id": "B", "side": "NO", "entry_price": 0.55, "qty": 1.0},
    ]


def test_validated_when_all_legs_clean_and_payout_meets_bound():
    labels = {"A": _label("A", LabelState.RESOLVED_YES),
              "B": _label("B", LabelState.RESOLVED_NO)}
    res = BregmanSettlementValidator().validate(
        group_id="g1", legs=_legs(), labels=labels,
        certified_profit_lower_bound=0.02)
    assert res.all_legs_clean is True
    assert res.valid is True
    assert res.state == "validated"
    assert abs(res.realized_payout - 1.05) < 1e-9
    assert res.margin > 0


def test_unresolved_when_any_leg_unresolved():
    labels = {"A": _label("A", LabelState.RESOLVED_YES),
              "B": _label("B", LabelState.UNRESOLVED)}
    res = BregmanSettlementValidator().validate(
        group_id="g2", legs=_legs(), labels=labels,
        certified_profit_lower_bound=0.02)
    assert res.valid is False
    assert res.state == "unresolved"
    assert res.all_legs_clean is False
    assert res.realized_payout is None


def test_partially_invalid_when_a_leg_is_ambiguous_or_void():
    for bad in (LabelState.AMBIGUOUS, LabelState.VOID, LabelState.STALE_RESOLUTION):
        labels = {"A": _label("A", LabelState.RESOLVED_YES),
                  "B": _label("B", bad)}
        res = BregmanSettlementValidator().validate(
            group_id="g3", legs=_legs(), labels=labels,
            certified_profit_lower_bound=0.02)
        assert res.valid is False, bad
        assert res.state == "partially_invalid", bad
        assert res.all_legs_clean is False


def test_violated_when_realized_payout_below_bound():
    # Both legs lose: A resolves NO, B resolves YES -> payout negative.
    labels = {"A": _label("A", LabelState.RESOLVED_NO),
              "B": _label("B", LabelState.RESOLVED_YES)}
    res = BregmanSettlementValidator().validate(
        group_id="g4", legs=_legs(), labels=labels,
        certified_profit_lower_bound=0.02)
    assert res.all_legs_clean is True
    assert res.valid is False
    assert res.state == "violated"
    assert res.realized_payout < 0.02
    assert res.margin < 0


def test_leg_states_reported():
    labels = {"A": _label("A", LabelState.RESOLVED_YES),
              "B": _label("B", LabelState.AMBIGUOUS)}
    res = BregmanSettlementValidator().validate(
        group_id="g5", legs=_legs(), labels=labels,
        certified_profit_lower_bound=0.02)
    assert res.leg_states["A"] == LabelState.RESOLVED_YES
    assert res.leg_states["B"] == LabelState.AMBIGUOUS
    assert "B" in " ".join(res.reasons) or any("B" in r for r in res.reasons)


def test_missing_leg_label_is_unresolved():
    labels = {"A": _label("A", LabelState.RESOLVED_YES)}  # B missing
    res = BregmanSettlementValidator().validate(
        group_id="g6", legs=_legs(), labels=labels,
        certified_profit_lower_bound=0.02)
    assert res.valid is False
    assert res.state == "unresolved"

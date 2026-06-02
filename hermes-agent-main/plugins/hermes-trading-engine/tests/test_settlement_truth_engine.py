"""Settlement Truth Engine — label-state classification + metadata.

Proves the engine maps raw venue resolutions into clean/dirty label states with
confidence + settlement-source metadata, computes settlement delay, and resolves
the realized 0/1 outcome for a predicted side. PAPER-ONLY; no network.
"""

from __future__ import annotations

from engine.training.settlement import (
    LabelState,
    SettlementLabel,
    SettlementTruthEngine,
    is_trainable_state,
)


def _eng():
    return SettlementTruthEngine(ambiguity_threshold=0.5, min_confidence=0.4,
                                 max_resolution_delay_ms=7 * 24 * 3600 * 1000)


def test_label_states_enumerated():
    # All seven required states exist and only resolved_yes/no are trainable.
    for name in ("UNRESOLVED", "RESOLVED_YES", "RESOLVED_NO", "VOID",
                 "AMBIGUOUS", "PARTIALLY_INVALID", "STALE_RESOLUTION"):
        assert hasattr(LabelState, name)
    assert LabelState.TRAINABLE == frozenset({LabelState.RESOLVED_YES, LabelState.RESOLVED_NO})
    assert is_trainable_state(LabelState.RESOLVED_YES)
    assert is_trainable_state(LabelState.RESOLVED_NO)
    for s in (LabelState.UNRESOLVED, LabelState.VOID, LabelState.AMBIGUOUS,
              LabelState.PARTIALLY_INVALID, LabelState.STALE_RESOLUTION):
        assert not is_trainable_state(s)


def test_unresolved_when_no_resolution():
    lab = _eng().classify({"market_id": "m1", "resolved": False,
                           "settlement_source": "polymarket"})
    assert lab.state == LabelState.UNRESOLVED
    assert lab.trainable is False
    assert lab.confidence == 0.0


def test_resolved_yes_clean_with_source_and_confidence():
    lab = _eng().classify({
        "market_id": "m1", "asset_id": "tok-yes", "resolved": True,
        "winning_outcome": "YES", "ambiguity_score": 0.0,
        "settlement_source": "uma", "close_ts_ms": 1000, "resolved_ts_ms": 5000})
    assert lab.state == LabelState.RESOLVED_YES
    assert lab.trainable is True
    assert lab.source == "uma"
    assert lab.confidence > 0.9
    assert lab.delay_ms == 4000
    # realized outcome for the predicted side
    assert lab.realized_for("YES") == 1
    assert lab.realized_for("NO") == 0


def test_resolved_no_clean():
    lab = _eng().classify({"market_id": "m2", "resolved": True,
                           "winning_outcome": "NO", "settlement_source": "polymarket"})
    assert lab.state == LabelState.RESOLVED_NO
    assert lab.realized_for("YES") == 0
    assert lab.realized_for("NO") == 1


def test_void_is_terminal_but_not_trainable():
    lab = _eng().classify({"market_id": "m3", "resolved": True, "voided": True,
                           "settlement_source": "polymarket"})
    assert lab.state == LabelState.VOID
    assert lab.trainable is False
    assert lab.realized_for("YES") is None


def test_ambiguous_when_high_ambiguity_score():
    lab = _eng().classify({"market_id": "m4", "resolved": True, "winning_outcome": "YES",
                           "ambiguity_score": 0.8, "settlement_source": "manual"})
    assert lab.state == LabelState.AMBIGUOUS
    assert lab.trainable is False


def test_low_confidence_demoted_to_ambiguous():
    # Weak source + some ambiguity pushes confidence below min_confidence.
    lab = _eng().classify({"market_id": "m5", "resolved": True, "winning_outcome": "YES",
                           "ambiguity_score": 0.45, "settlement_source": "unknown"})
    assert lab.state == LabelState.AMBIGUOUS
    assert lab.trainable is False


def test_partially_invalid_flag():
    lab = _eng().classify({"market_id": "m6", "resolved": True, "winning_outcome": "YES",
                           "partial": True, "settlement_source": "polymarket"})
    assert lab.state == LabelState.PARTIALLY_INVALID
    assert lab.trainable is False


def test_stale_resolution_when_delay_exceeds_limit():
    eng = SettlementTruthEngine(max_resolution_delay_ms=1000)
    lab = eng.classify({"market_id": "m7", "resolved": True, "winning_outcome": "YES",
                        "settlement_source": "polymarket",
                        "close_ts_ms": 0, "resolved_ts_ms": 10_000})
    assert lab.state == LabelState.STALE_RESOLUTION
    assert lab.trainable is False


def test_explicit_stale_flag():
    lab = _eng().classify({"market_id": "m8", "resolved": True, "winning_outcome": "NO",
                           "stale": True, "settlement_source": "polymarket"})
    assert lab.state == LabelState.STALE_RESOLUTION
    assert lab.trainable is False


def test_to_dict_carries_metadata():
    lab = _eng().classify({"market_id": "m9", "resolved": True, "winning_outcome": "YES",
                           "settlement_source": "chainlink", "close_ts_ms": 1, "resolved_ts_ms": 2})
    d = lab.to_dict()
    for k in ("market_id", "state", "confidence", "source", "delay_ms", "ambiguity_score"):
        assert k in d
    assert d["source"] == "chainlink"

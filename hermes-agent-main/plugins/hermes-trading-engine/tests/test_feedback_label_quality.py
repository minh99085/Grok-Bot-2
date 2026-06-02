"""Label-quality gating — dirty labels must never train the probability stack.

Proves:
* OnlineLearner refuses ambiguous / void / unresolved / partially_invalid /
  stale_resolution outcomes (no calibration/bucket mutation) and counts them.
* FeedbackLoop suppresses dirty outcomes (learner + calibrator untouched).
* Label-quality metrics (coverage, ambiguous rate, suppression, delay).
* Before/after: filtering changes learner state vs. training everything.
"""

from __future__ import annotations

from engine.training.feedback_loop import FeedbackLoop
from engine.training.metrics import LabelQualityMetrics
from engine.training.online_learner import OnlineLearner
from engine.training.settlement import LabelState

_DIRTY = (LabelState.UNRESOLVED, LabelState.VOID, LabelState.AMBIGUOUS,
          LabelState.PARTIALLY_INVALID, LabelState.STALE_RESOLUTION)


def _outcome(state, prob=0.7, win=True, pnl=1.0):
    return dict(predicted_prob=prob, win=win, realized_pnl=pnl,
                category="crypto", net_edge=0.05, label_state=state)


def test_learner_suppresses_each_dirty_state():
    for state in _DIRTY:
        lrn = OnlineLearner()
        lrn.record_outcome(**_outcome(state))
        assert lrn.closed == 0, f"{state} must not train"
        assert lrn.prob_buckets == {}
        assert lrn.suppressed_outcomes == 1
        assert lrn.label_states.get(state) == 1


def test_learner_trains_on_clean_labels():
    for state in (LabelState.RESOLVED_YES, LabelState.RESOLVED_NO):
        lrn = OnlineLearner()
        lrn.record_outcome(**_outcome(state, win=(state == LabelState.RESOLVED_YES)))
        assert lrn.closed == 1
        assert lrn.prob_buckets != {}
        assert lrn.suppressed_outcomes == 0


def test_legacy_no_label_still_trains():
    # Back-compat: callers that don't pass a label keep training (clean default).
    lrn = OnlineLearner()
    lrn.record_outcome(predicted_prob=0.6, win=True, realized_pnl=1.0)
    assert lrn.closed == 1


def test_feedback_loop_suppresses_dirty_and_counts():
    lrn = OnlineLearner()
    fb = FeedbackLoop(lrn, interval_seconds=0.0)
    # 4 clean, 3 dirty
    for _ in range(4):
        assert fb.record_outcome(predicted_prob=0.7, predicted_edge=0.05,
                                 realized_pnl=1.0, size_usd=10, win=True,
                                 label_state=LabelState.RESOLVED_YES,
                                 label_confidence=0.95, settlement_source="uma") is True
    for st in (LabelState.AMBIGUOUS, LabelState.VOID, LabelState.UNRESOLVED):
        assert fb.record_outcome(predicted_prob=0.7, predicted_edge=0.05,
                                 realized_pnl=1.0, size_usd=10, win=True,
                                 label_state=st) is False
    assert lrn.closed == 4               # only clean labels trained
    assert fb.suppressed == 3
    lq = fb.label_quality_report()
    assert lq["total"] == 7
    assert lq["trainable"] == 4
    assert lq["suppressed"] == 3
    assert abs(lq["ambiguous_rate"] - (1 / 7)) < 1e-5
    assert abs(lq["suppression_rate"] - (3 / 7)) < 1e-5


def test_before_after_label_filtering_changes_learner_state():
    clean = [(0.9, True), (0.85, True), (0.8, False), (0.2, False), (0.15, False)]
    dirty = [(0.5, True), (0.5, True), (0.5, False)]  # ambiguous noise at p=0.5

    # BEFORE: train on everything (treat dirty as clean) — noisy calibration.
    before = OnlineLearner()
    for p, w in clean + dirty:
        before.record_outcome(predicted_prob=p, win=w, realized_pnl=1.0 if w else -1.0,
                              label_state=LabelState.RESOLVED_YES if w else LabelState.RESOLVED_NO)
    # AFTER: same clean, but dirty correctly labelled ambiguous (suppressed).
    after = OnlineLearner()
    for p, w in clean:
        after.record_outcome(predicted_prob=p, win=w, realized_pnl=1.0 if w else -1.0,
                             label_state=LabelState.RESOLVED_YES if w else LabelState.RESOLVED_NO)
    for p, w in dirty:
        after.record_outcome(predicted_prob=p, win=w, realized_pnl=1.0 if w else -1.0,
                             label_state=LabelState.AMBIGUOUS)

    assert before.closed == 8
    assert after.closed == 5
    assert after.suppressed_outcomes == 3
    # The dirty p=0.5 noise pollutes the 0.5 bucket only in BEFORE.
    assert "[0.5,0.6)" in before.prob_buckets
    assert "[0.5,0.6)" not in after.prob_buckets


def test_label_quality_metrics_dataclass():
    m = LabelQualityMetrics()
    m.record(state=LabelState.RESOLVED_YES, trainable=True, confidence=0.9, delay_ms=2000)
    m.record(state=LabelState.RESOLVED_NO, trainable=True, confidence=0.8, delay_ms=4000)
    m.record(state=LabelState.AMBIGUOUS, trainable=False, confidence=0.3)
    m.record(state=LabelState.UNRESOLVED, trainable=False, confidence=0.0)
    d = m.to_dict()
    assert d["total"] == 4
    assert d["trainable"] == 2
    assert d["suppressed"] == 2
    assert abs(d["ambiguous_rate"] - 0.25) < 1e-9
    # coverage = terminal-labelled / total (everything except unresolved)
    assert abs(d["label_coverage"] - 0.75) < 1e-9
    assert abs(d["avg_delay_ms"] - 3000.0) < 1e-9

"""Tests for calibration guardrails.

Covers InstitutionalCalibrator.maybe_fit (redundant-refit guard that fixes the
"repeated isotonic fitting" spam), fit_with_rollback (revert when ECE+Brier
degrade on validation), the standalone CalibrationGuard decision, and the binned
Calibrator's new ECE stats.
"""

from __future__ import annotations

from engine.calibration_models import InstitutionalCalibrator
from engine.calibration import Calibrator
from engine.models.probability_ensemble import CalibrationGuard


# Well-separated, well-ordered data: low p -> 0, high p -> 1.
_GOOD = [(0.1, 0)] * 10 + [(0.2, 0)] * 10 + [(0.8, 1)] * 10 + [(0.9, 1)] * 10
# Anti-correlated data: high p -> 0, low p -> 1 (a bad calibrator on _GOOD).
_BAD = [(0.1, 1)] * 10 + [(0.2, 1)] * 10 + [(0.8, 0)] * 10 + [(0.9, 0)] * 10


# --------------------------------------------------------------------------- #
# maybe_fit: skip redundant refits (fixes the repeated-isotonic-fit spam)
# --------------------------------------------------------------------------- #
def test_maybe_fit_skips_unchanged_data():
    cal = InstitutionalCalibrator(method="platt", min_samples=2)
    assert cal.maybe_fit(_GOOD) is True            # first fit runs
    assert cal.maybe_fit(_GOOD) is False           # unchanged -> skipped
    assert cal.maybe_fit(_GOOD + [(0.5, 1)]) is True  # changed -> refit


# --------------------------------------------------------------------------- #
# fit_with_rollback: revert a degrading refit
# --------------------------------------------------------------------------- #
def test_fit_with_rollback_reverts_degrading_candidate():
    cal = InstitutionalCalibrator(method="platt", min_samples=2, bins=5)
    cal.fit(_GOOD)
    good_method = cal.fitted_method
    # Refit on anti-correlated data but validate against the good distribution:
    # the candidate must be worse on ECE+Brier -> rollback.
    cal.fit_with_rollback(_BAD, validation_pairs=_GOOD)
    assert cal.rollbacks == 1
    assert cal.fitted_method == good_method  # reverted to the previous model
    # And the kept model still calibrates a high prob upward.
    assert cal.transform(0.9) > cal.transform(0.1)


def test_fit_with_rollback_keeps_non_degrading_candidate():
    cal = InstitutionalCalibrator(method="platt", min_samples=2, bins=5)
    cal.fit(_GOOD)
    cal.fit_with_rollback(_GOOD, validation_pairs=_GOOD)  # same/!worse -> keep
    assert cal.rollbacks == 0


# --------------------------------------------------------------------------- #
# CalibrationGuard decision logic
# --------------------------------------------------------------------------- #
def test_calibration_guard_decisions():
    g = CalibrationGuard()
    assert g.consider({"ece": 0.2, "brier": 0.2}, None)["decision"] == "keep"
    d = g.consider({"ece": 0.3, "brier": 0.3}, {"ece": 0.1, "brier": 0.1})
    assert d["decision"] == "rollback" and g.rollbacks == 1
    k = g.consider({"ece": 0.05, "brier": 0.05}, {"ece": 0.1, "brier": 0.1})
    assert k["decision"] == "keep"
    # degraded on only one metric -> keep (avoid churn)
    one = g.consider({"ece": 0.3, "brier": 0.05}, {"ece": 0.1, "brier": 0.1})
    assert one["decision"] == "keep"


# --------------------------------------------------------------------------- #
# isotonic guard: not eligible below 2*min_samples (avoids over-fit)
# --------------------------------------------------------------------------- #
def test_auto_does_not_pick_isotonic_when_data_thin():
    cal = InstitutionalCalibrator(method="auto", min_samples=20, bins=5)
    cal.fit([(0.1, 0), (0.9, 1), (0.2, 0)])  # well below 2*min_samples
    assert cal.fitted_method != "isotonic"


# --------------------------------------------------------------------------- #
# binned Calibrator ECE stats
# --------------------------------------------------------------------------- #
class _FakeStore:
    def __init__(self):
        self._preds: list = []

    def add_prediction(self, p, o):
        self._preds.append((float(p), int(o)))

    def get_predictions(self, n):
        return list(self._preds[-n:])


def test_binned_calibrator_reports_ece():
    cal = Calibrator(_FakeStore(), min_samples=2)
    for p, o in _GOOD:
        cal.record(p, o)
    st = cal.stats()
    assert set(("ece_raw", "ece_cal", "brier_raw", "brier_cal")) <= set(st)
    assert st["ece_raw"] is not None and st["ece_cal"] is not None

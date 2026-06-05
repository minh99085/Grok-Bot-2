"""Online probability calibration for the pulse model.

A raw model probability of "UP" is not necessarily *true* — a model can be
systematically over- or under-confident. This calibrator learns the mapping
from predicted probability to the empirically realized up-frequency, using
binned reliability with shrinkage toward the identity (so it degrades to the
raw probability when data is thin). It also reports the Brier score (mean
squared error of probabilistic forecasts) for raw vs calibrated, which is the
metric that actually matters for an EV-driven bettor.

Persisted via the Store's `predictions` table so calibration survives restarts.
"""

from __future__ import annotations


class Calibrator:
    def __init__(self, store, bins: int = 20, shrink: float = 25.0, min_samples: int = 40):
        self.store = store
        self.bins = bins
        self.shrink = shrink          # pseudo-count pulling empirical rate toward p
        self.min_samples = min_samples

    def record(self, p_raw: float, outcome: int) -> None:
        """outcome = 1 if the round closed UP, else 0."""
        self.store.add_prediction(float(p_raw), int(outcome))

    def _data(self):
        return self.store.get_predictions(3000)

    def calibrate(self, p: float) -> float:
        p = min(0.98, max(0.02, float(p)))
        data = self._data()
        if len(data) < self.min_samples:
            return p  # not enough evidence — trust the raw model
        b = min(self.bins - 1, max(0, int(p * self.bins)))
        lo, hi = b / self.bins, (b + 1) / self.bins
        pts = [o for (pr, o) in data if lo <= pr < hi]
        n = len(pts)
        if n == 0:
            return p
        ups = sum(pts)
        cal = (ups + self.shrink * p) / (n + self.shrink)
        return min(0.98, max(0.02, cal))

    def _ece(self, pairs: list, bins: int = 10) -> float:
        """Expected calibration error: |mean(p) - mean(outcome)| per bin,
        sample-weighted. Lower is better; 0 = perfectly calibrated."""
        if not pairs:
            return 0.0
        buckets: list[list] = [[] for _ in range(bins)]
        for pr, o in pairs:
            b = min(bins - 1, max(0, int(float(pr) * bins)))
            buckets[b].append((float(pr), int(o)))
        n = len(pairs)
        err = 0.0
        for bk in buckets:
            if not bk:
                continue
            mp = sum(p for p, _ in bk) / len(bk)
            mo = sum(o for _, o in bk) / len(bk)
            err += (len(bk) / n) * abs(mp - mo)
        return err

    def stats(self) -> dict:
        data = self._data()
        n = len(data)
        if n == 0:
            return {"samples": 0, "brier_raw": None, "brier_cal": None,
                    "ece_raw": None, "ece_cal": None, "calibrated": False}
        brier_raw = sum((pr - o) ** 2 for pr, o in data) / n
        # calibrated Brier (uses the current mapping on each stored raw prob)
        cal = [(self.calibrate(pr), o) for pr, o in data]
        brier_cal = sum((c - o) ** 2 for c, o in cal) / n
        return {
            "samples": n,
            "brier_raw": round(brier_raw, 4),
            "brier_cal": round(brier_cal, 4),
            "ece_raw": round(self._ece([(pr, o) for pr, o in data]), 4),
            "ece_cal": round(self._ece(cal), 4),
            "calibrated": n >= self.min_samples,
        }

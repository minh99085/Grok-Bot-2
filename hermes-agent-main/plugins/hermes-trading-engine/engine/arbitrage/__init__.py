"""Bregman arbitrage core (PAPER ONLY).

Pure, dependency-free building blocks for prediction-market coherence arbitrage:

* :mod:`engine.arbitrage.constraint_graph` — the market constraint graph
  (complement / mutually-exclusive / collectively-exhaustive / MECE / range /
  hierarchy / cross-market relationships).
* :mod:`engine.arbitrage.bregman_projection` — KL/Bregman projection of the
  market-implied probabilities onto the coherent set (finds incoherence).
* :mod:`engine.arbitrage.certificate` — cost/depth-aware certification of a
  worst-case nonnegative payoff with positive after-fee profit.

No I/O, no trading, no wallet/order paths. Certification is required before any
trade ("no certified proof means no trade").
"""

from __future__ import annotations

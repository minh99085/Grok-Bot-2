"""Trading strategies for the Hermes Trading Engine (PAPER ONLY).

Bregman coherence arbitrage is the primary strategy (see
:mod:`engine.strategies.bregman`). Strategies here are pure planners: they emit
*certified, fill-feasible* opportunities; the deterministic RiskEngine + paper
OMS remain the only execution path. No live orders, no wallet.
"""

from __future__ import annotations

"""Deterministic execution-simulation primitives (PAPER ONLY).

Pure, offline models used by the backtester / replay to make paper fills honest:
order-book depth walking, partial fills, latency + stale-book rejection, fees,
and Bregman multi-leg (all-or-nothing) execution feasibility. Nothing here
performs I/O or places a real order.
"""

from __future__ import annotations

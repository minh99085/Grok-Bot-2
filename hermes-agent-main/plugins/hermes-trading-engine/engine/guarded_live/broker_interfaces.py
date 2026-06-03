"""Future live-broker INTERFACE (Phase 8) — design only.

This defines the shape a real broker would implement later. The execution
methods (submit/cancel/replace) raise LiveExecutionDisabled in the base class so
no subclass can accidentally ship a working live path without explicitly (and
visibly) overriding them in a future, separately-reviewed phase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .errors import LiveExecutionDisabled


class LiveBrokerInterface(ABC):
    venue: str = "unknown"

    @abstractmethod
    def preflight_check(self) -> dict: ...

    @abstractmethod
    def validate_order(self, order: dict) -> dict: ...

    @abstractmethod
    def reconcile(self) -> dict: ...

    @abstractmethod
    def health(self) -> dict: ...

    # --- execution methods are LOCKED ---------------------------------- #
    def submit_order(self, *a, **k):
        raise LiveExecutionDisabled("submit_order", f"venue={self.venue}")

    def cancel_order(self, *a, **k):
        raise LiveExecutionDisabled("cancel_order", f"venue={self.venue}")

    def replace_order(self, *a, **k):
        raise LiveExecutionDisabled("replace_order", f"venue={self.venue}")

    # common aliases venue SDKs use — all locked
    post_order = submit_order
    create_order = submit_order
    create_and_post_order = submit_order
    create_market_order = submit_order
    create_and_post_market_order = submit_order

    @staticmethod
    def canary_execution_locked() -> bool:
        """Invariant: the design-only broker interface NEVER ships a working live
        execution path. The micro-live canary framework adds gating ON TOP of
        this lock (readiness certificate, manual-enable, caps, rollback); it does
        not unlock execution here. Always True. Compliance/Security."""
        return True

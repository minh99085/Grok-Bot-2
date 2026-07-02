"""Append-only JSONL audit log for every MCP tool call and safety decision."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class AuditLog:
    """Writes structured audit events to ``<data_dir>/robinhood_audit.jsonl``."""

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "robinhood_audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        event: str,
        *,
        tool: str | None = None,
        allowed: bool | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        row = {
            "ts": time.time(),
            "event": event,
            "tool": tool,
            "allowed": allowed,
            "reason": reason,
            "details": details or {},
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
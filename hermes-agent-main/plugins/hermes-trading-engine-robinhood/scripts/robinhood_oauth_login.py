#!/usr/bin/env python3
"""Desktop OAuth login for Robinhood Trading MCP — run once to seed VPS token file.

Usage (local or VPS with SSH port-forward):
  python scripts/robinhood_oauth_login.py

After auth, copy ``/data/robinhood_oauth_tokens.json`` to the VPS volume if you
ran this locally, or re-run inside the container with RH_DATA_DIR mounted.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.robinhood.audit_log import AuditLog
from engine.robinhood.config import RobinhoodConfig
from engine.robinhood.robinhood_mcp_adapter import RobinhoodMCPAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def _main() -> None:
    cfg = RobinhoodConfig.from_env()
    adapter = RobinhoodMCPAdapter(cfg, AuditLog(cfg.data_dir))
    print(f"Data dir: {cfg.data_dir}")
    print(f"MCP URL:  {cfg.mcp_url}")
    print("Complete OAuth in your desktop browser when prompted.\n")
    await adapter.connect(interactive_oauth=True)
    tools = await adapter.list_tools()
    print(f"\nSuccess — {len(tools)} MCP tools available:")
    for name in tools:
        print(f"  - {name}")
    await adapter.disconnect()


if __name__ == "__main__":
    asyncio.run(_main())
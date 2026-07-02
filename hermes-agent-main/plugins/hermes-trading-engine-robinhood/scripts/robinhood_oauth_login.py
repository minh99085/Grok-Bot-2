#!/usr/bin/env python3
"""Robinhood Trading MCP OAuth — seeds ``/data/robinhood_oauth_tokens.json``.

VPS flow (operator machine):
  1. SSH tunnel: ssh -L 53682:127.0.0.1:53682 -i <key> root@45.32.224.147
  2. Run: docker compose --profile robinhood run --rm -p 53682:53682 \\
           hermes-robinhood-agent python scripts/robinhood_oauth_login.py
  3. Open the printed URL in a desktop browser; callback hits localhost:53682 via tunnel.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.robinhood.audit_log import AuditLog
from engine.robinhood.config import RobinhoodConfig
from engine.robinhood.oauth_callback import parse_redirect_uri, start_callback_server
from engine.robinhood.robinhood_mcp_adapter import RobinhoodMCPAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def _main() -> None:
    cfg = RobinhoodConfig.from_env()
    host, port, _path = parse_redirect_uri(cfg.oauth_redirect_uri)
    bind_host = os.getenv("RH_OAUTH_BIND_HOST", host)
    use_server = os.getenv("RH_OAUTH_USE_CALLBACK_SERVER", "1").lower() in ("1", "true", "yes")

    import queue as queue_mod

    callback_server = None
    callback_queue: queue_mod.Queue | None = None

    async def redirect_handler(auth_url: str) -> None:
        print(f"\n=== Robinhood OAuth ===\nOpen in desktop browser:\n{auth_url}\n")
        if os.getenv("RH_OAUTH_OPEN_BROWSER", "").lower() in ("1", "true", "yes"):
            webbrowser.open(auth_url)

    async def callback_handler() -> tuple[str, str | None]:
        if callback_queue is None:
            return await RobinhoodMCPAdapter._default_callback_handler()
        print(f"Waiting for OAuth callback on http://127.0.0.1:{port}/callback ...")
        code, state = await asyncio.to_thread(callback_queue.get, True, 600.0)
        if not code:
            raise ValueError("callback missing authorization code")
        return code, state

    if use_server:
        callback_server, callback_queue = start_callback_server(bind_host, port)
        print(f"Callback server listening on {bind_host}:{port}")

    adapter = RobinhoodMCPAdapter(
        cfg,
        AuditLog(cfg.data_dir),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )
    print(f"Data dir: {cfg.data_dir}")
    print(f"MCP URL:  {cfg.mcp_url}")

    try:
        await adapter.connect(interactive_oauth=True)
        tools = await adapter.list_tools()
        print(f"\nSuccess — {len(tools)} MCP tools available:")
        for name in tools:
            print(f"  - {name}")
        token_path = Path(cfg.data_dir) / "robinhood_oauth_tokens.json"
        print(f"\nTokens saved: {token_path}")
    finally:
        await adapter.disconnect()
        if callback_server is not None:
            callback_server.shutdown()


if __name__ == "__main__":
    asyncio.run(_main())
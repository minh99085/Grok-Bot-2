"""Local HTTP callback server for Robinhood MCP OAuth (VPS + SSH tunnel friendly)."""

from __future__ import annotations

import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class _OAuthHandler(BaseHTTPRequestHandler):
    result: queue.Queue[tuple[str, str | None]] | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        code = (params.get("code") or [""])[0]
        state = (params.get("state") or [None])[0]
        if _OAuthHandler.result is not None:
            _OAuthHandler.result.put((code, state))
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        body = (
            "<html><body><h2>Robinhood OAuth complete</h2>"
            "<p>You can close this tab and return to the terminal.</p></body></html>"
        )
        self.wfile.write(body.encode())

    def log_message(self, format: str, *args: object) -> None:
        return


def start_callback_server(host: str, port: int) -> tuple[HTTPServer, queue.Queue]:
    """Start a background HTTP server; returns (server, queue of (code, state))."""
    result_q: queue.Queue[tuple[str, str | None]] = queue.Queue(maxsize=1)
    _OAuthHandler.result = result_q

    server = HTTPServer((host, port), _OAuthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, result_q


def parse_redirect_uri(redirect_uri: str) -> tuple[str, int, str]:
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/callback"
    return host, port, path
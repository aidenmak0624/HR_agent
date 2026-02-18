"""
MCP Transport Layer — stdio and SSE transport implementations.

Provides transport abstractions for the HR Agent MCP Server:
- StdioTransport: JSON-RPC over stdin/stdout (for IDE/CLI integration)
- SSETransport: Server-Sent Events over HTTP (for web clients)

Usage:
    from src.mcp.server import create_mcp_server
    from src.mcp.transport import StdioTransport

    server = create_mcp_server()
    transport = StdioTransport(server)
    transport.run()
"""

import json
import logging
import sys
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from src.mcp.server import HRMCPServer

logger = logging.getLogger(__name__)


class StdioTransport:
    """
    MCP stdio transport — reads JSON-RPC from stdin, writes to stdout.

    Follows MCP specification for stdio transport:
    - One JSON-RPC message per line
    - Responses written as single-line JSON to stdout
    - Notifications (no id field) receive no response
    - Supports batch requests (JSON arrays)

    Suitable for:
    - IDE integration (VS Code, Cursor, etc.)
    - CLI tool usage
    - Process-based MCP clients
    """

    def __init__(self, server: "HRMCPServer"):
        self.server = server
        self._running = False

    def run(self):
        """
        Start the stdio transport loop.

        Blocks until stdin is closed (EOF) or interrupted (Ctrl+C).
        """
        self._running = True
        logger.info("MCP stdio transport: ready")
        print(
            f"HR Agent MCP Server v{self.server.version} ready (stdio)",
            file=sys.stderr,
        )

        try:
            for line in sys.stdin:
                if not self._running:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    response_json = self.server.handle_request_json(line)
                    if response_json:
                        sys.stdout.write(response_json + "\n")
                        sys.stdout.flush()
                except Exception as e:
                    error = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32603, "message": str(e)},
                    }
                    sys.stdout.write(json.dumps(error) + "\n")
                    sys.stdout.flush()
        except KeyboardInterrupt:
            logger.info("MCP stdio transport: stopped (Ctrl+C)")
        except EOFError:
            logger.info("MCP stdio transport: stopped (EOF)")
        finally:
            self._running = False

    def stop(self):
        """Signal the transport to stop."""
        self._running = False


class SSETransport:
    """
    MCP SSE transport — provides HTTP endpoints for Server-Sent Events.

    Follows MCP specification for SSE transport:
    1. Client connects to GET /sse to receive SSE stream
    2. Server sends `endpoint` event with the POST URL
    3. Client sends JSON-RPC requests via POST to that endpoint
    4. Server responds via the SSE stream

    This class creates a standalone HTTP server. For integration with
    an existing Flask app, use HRMCPServer.get_flask_blueprint() instead.
    """

    def __init__(self, server: "HRMCPServer", host: str = "0.0.0.0", port: int = 8080):
        self.server = server
        self.host = host
        self.port = port
        self._app = None

    def _create_app(self):
        """Create a minimal Flask app for the SSE transport."""
        try:
            from flask import Flask
        except ImportError:
            raise ImportError(
                "Flask is required for SSE transport. Install with: pip install flask"
            )

        app = Flask(__name__)
        bp = self.server.get_flask_blueprint()
        app.register_blueprint(bp, url_prefix="/mcp")

        # Also register at root for convenience
        @app.route("/health")
        def health():
            from flask import jsonify

            return jsonify(
                {
                    "status": "ok",
                    "server": self.server.name,
                    "version": self.server.version,
                    "transport": "sse",
                }
            )

        self._app = app
        return app

    def run(self):
        """
        Start the SSE transport HTTP server.

        Blocks until interrupted.
        """
        app = self._create_app()
        logger.info(f"MCP SSE transport: starting on {self.host}:{self.port}")
        print(
            f"HR Agent MCP Server v{self.server.version} ready (SSE) at "
            f"http://{self.host}:{self.port}/mcp",
            file=sys.stderr,
        )
        app.run(host=self.host, port=self.port, debug=False, threaded=True)

    def get_app(self):
        """Get the Flask app (for testing or WSGI deployment)."""
        if self._app is None:
            self._create_app()
        return self._app

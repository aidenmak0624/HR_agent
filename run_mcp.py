#!/usr/bin/env python3
"""
HR Agent MCP Server — Standalone Runner.

Runs the MCP server as a standalone process with configurable transport.

Usage:
    # Official MCP SDK (default — recommended):
    python run_mcp.py                          # stdio transport
    python run_mcp.py --transport sse          # SSE HTTP on port 8080
    python run_mcp.py --transport streamable-http  # Streamable HTTP on port 8080

    # Legacy hand-rolled server (backward compat):
    python run_mcp.py --legacy
    python run_mcp.py --legacy --transport sse --port 8080

    # With verbose logging:
    python run_mcp.py --verbose

Environment:
    DATABASE_URL: Database connection string (default: sqlite:///hr_platform.db)
    OPENAI_API_KEY: Required for ask_hr_question tool (optional otherwise)
"""

import argparse
import logging
import os
import sys

# Ensure project root is on path
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(
        description="HR Agent MCP Server — Model Context Protocol server for HR operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_mcp.py                              # Official SDK, stdio mode (default)
  python run_mcp.py --transport sse              # Official SDK, SSE HTTP on 8080
  python run_mcp.py --transport streamable-http  # Official SDK, streamable HTTP
  python run_mcp.py --legacy                     # Legacy server, stdio mode
  python run_mcp.py --legacy --transport sse     # Legacy server, SSE mode
  python run_mcp.py --verbose                    # Enable debug logging
        """,
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port for SSE/HTTP transport (default: 8080)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host for SSE/HTTP transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--name",
        default="hr-agent-platform",
        help="MCP server name (default: hr-agent-platform)",
    )
    parser.add_argument(
        "--version",
        default="3.0.0",
        help="MCP server version (default: 3.0.0)",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy hand-rolled MCP server instead of official SDK",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--no-db-init",
        action="store_true",
        help="Skip database initialization on startup",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # Log to stderr so stdout is clean for stdio transport
    )
    log = logging.getLogger(__name__)

    # Initialize database (unless skipped)
    if not args.no_db_init:
        try:
            from src.core.database import init_db
            init_db()
            log.info("Database initialized")
        except Exception as e:
            log.warning(f"Database init skipped: {e}")

    # ----- Legacy server path -----
    if args.legacy:
        log.info("Starting LEGACY MCP server (hand-rolled JSON-RPC)")
        from src.mcp.server import create_mcp_server
        server = create_mcp_server(name=args.name, version=args.version)

        if args.transport == "stdio":
            from src.mcp.transport import StdioTransport
            transport = StdioTransport(server)
            transport.run()
        elif args.transport == "sse":
            from src.mcp.transport import SSETransport
            transport = SSETransport(server, host=args.host, port=args.port)
            transport.run()
        else:
            log.error("Legacy server only supports stdio and sse transports")
            sys.exit(1)
        return

    # ----- Official MCP SDK path (default) -----
    log.info(f"Starting MCP server (official SDK) — transport={args.transport}")
    from src.mcp.fastmcp_server import mcp as fastmcp

    if args.transport == "stdio":
        fastmcp.run(transport="stdio")
    elif args.transport == "sse":
        fastmcp.run(transport="sse", host=args.host, port=args.port)
    elif args.transport == "streamable-http":
        fastmcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()

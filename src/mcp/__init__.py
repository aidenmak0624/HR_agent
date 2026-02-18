"""
MCP (Model Context Protocol) server for HR Agent Platform.

Provides:
- HRMCPServer: Full MCP v2.0 server with 22 tools, 8 resources, 5 prompts
- MCPServer: Legacy JSON-RPC 2.0 server (backward compatible)
- MCPToolRegistry: Tool registry for agent tool discovery
- StdioTransport / SSETransport: Transport layer implementations
- create_mcp_server: Factory function for quick setup

Usage:
    from src.mcp import create_mcp_server
    server = create_mcp_server()
    response = server.handle_request({"jsonrpc": "2.0", "method": "tools/list", "id": 1})
"""

from src.mcp.server import HRMCPServer, create_mcp_server
from src.mcp.mcp_server import MCPServer
from src.mcp.tool_registry import MCPToolRegistry
from src.mcp.fastmcp_server import mcp as fastmcp_server

__all__ = [
    "HRMCPServer",
    "create_mcp_server",
    "MCPServer",
    "MCPToolRegistry",
    "fastmcp_server",
]

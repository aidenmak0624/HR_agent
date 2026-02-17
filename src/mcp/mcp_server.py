"""
MCP Server — JSON-RPC 2.0 compatible server for HR Agent tools.

Implements the Model Context Protocol server interface that exposes
all specialist agent tools via a standardised protocol. Supports:
- initialize: Server capabilities and info
- tools/list: Dynamic tool discovery
- tools/call: Tool invocation with arguments

This bridges the gap between native Python tool functions and the
MCP standard, enabling any MCP client to use HR agent tools.

Usage:
    server = MCPServer("hr-agent-platform", "1.0.0")
    server.register_agent("leave_request", LeaveRequestAgent(llm))
    response = server.handle_request({"jsonrpc": "2.0", "method": "tools/list", "id": 1})
"""

import json
import logging
from typing import Any, Dict, List, Optional

from src.mcp.tool_registry import MCPToolRegistry

logger = logging.getLogger(__name__)


class MCPServer:
    """
    JSON-RPC 2.0 server implementing the Model Context Protocol.

    Provides three core methods:
    1. initialize — Returns server info and capabilities
    2. tools/list — Returns all available tool descriptors
    3. tools/call — Executes a tool and returns the result

    Attributes:
        name: Server name (e.g., "hr-agent-platform")
        version: Server version string
        registry: MCPToolRegistry managing all tool descriptors
    """

    # MCP Protocol version
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, name: str = "hr-agent-platform", version: str = "1.0.0"):
        """
        Initialize MCP server.

        Args:
            name: Server name for identification
            version: Semantic version of this server
        """
        self.name = name
        self.version = version
        self.registry = MCPToolRegistry()
        self._initialized = False

        # Method dispatch table
        self._methods = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "ping": self._handle_ping,
        }

        logger.info(f"MCPServer: Created '{name}' v{version}")

    def register_agent(self, agent_type: str, agent_instance: Any) -> int:
        """
        Register a specialist agent's tools with the MCP server.

        Args:
            agent_type: Agent identifier
            agent_instance: Agent with get_tools() method

        Returns:
            Number of tools registered.
        """
        return self.registry.register_agent(agent_type, agent_instance)

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a JSON-RPC 2.0 request.

        Args:
            request: JSON-RPC request dict with:
                - jsonrpc: "2.0"
                - method: Method name
                - params: Optional parameters
                - id: Request ID

        Returns:
            JSON-RPC 2.0 response dict.
        """
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        logger.info(f"MCPServer: Handling request — method={method}, id={req_id}")

        # Validate JSON-RPC version
        if request.get("jsonrpc") != "2.0":
            return self._error_response(req_id, -32600, "Invalid JSON-RPC version")

        # Dispatch to method handler
        handler = self._methods.get(method)
        if not handler:
            return self._error_response(req_id, -32601, f"Method not found: {method}")

        try:
            result = handler(params)
            return self._success_response(req_id, result)
        except Exception as e:
            logger.error(f"MCPServer: Error handling {method}: {e}")
            return self._error_response(req_id, -32603, str(e))

    def handle_request_json(self, json_str: str) -> str:
        """
        Handle a JSON-RPC request from a raw JSON string.

        Args:
            json_str: JSON-encoded request string

        Returns:
            JSON-encoded response string.
        """
        try:
            request = json.loads(json_str)
        except json.JSONDecodeError as e:
            return json.dumps(self._error_response(None, -32700, f"Parse error: {e}"))

        response = self.handle_request(request)
        return json.dumps(response)

    # ==================== Method Handlers ====================

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle initialize request — return server capabilities.

        Returns:
            Server info including name, version, protocol version, and capabilities.
        """
        self._initialized = True
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                },
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tools/list request — return all available tools.

        Returns:
            Dict with "tools" key containing list of tool descriptors.
        """
        agent_filter = params.get("agent_type")
        tools = self.registry.list_tools(agent_type=agent_filter)
        return {"tools": tools}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tools/call request — execute a tool.

        Args:
            params: Must contain:
                - name: Fully qualified tool name
                - arguments: Dict with tool arguments

        Returns:
            Tool execution result in MCP content format.
        """
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required")

        result = self.registry.call_tool(tool_name, arguments)
        return result

    def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request — health check."""
        return {"status": "ok"}

    # ==================== Response Helpers ====================

    @staticmethod
    def _success_response(req_id: Any, result: Any) -> Dict[str, Any]:
        """Build a JSON-RPC 2.0 success response."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    @staticmethod
    def _error_response(req_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Build a JSON-RPC 2.0 error response."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    # ==================== Convenience Methods ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            "server_name": self.name,
            "version": self.version,
            "protocol_version": self.PROTOCOL_VERSION,
            "initialized": self._initialized,
            "total_tools": self.registry.get_tool_count(),
            "agent_types": self.registry.get_agent_types(),
        }

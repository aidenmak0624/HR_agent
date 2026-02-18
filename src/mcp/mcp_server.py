"""
MCP Server — JSON-RPC 2.0 compatible server for HR Agent tools.

Legacy wrapper that preserves backward compatibility while delegating to
the new HRMCPServer (v2.0) for full MCP protocol support.

The MCPServer class is kept for existing code that uses:
    server = MCPServer("hr-agent-platform", "1.0.0")
    server.register_agent("leave_request", LeaveRequestAgent(llm))
    response = server.handle_request({"jsonrpc": "2.0", "method": "tools/list", "id": 1})

For new code, prefer:
    from src.mcp.server import create_mcp_server
    server = create_mcp_server()
"""

import json
import logging
from typing import Any, Dict, List, Optional

from src.mcp.tool_registry import MCPToolRegistry

logger = logging.getLogger(__name__)


class MCPServer:
    """
    JSON-RPC 2.0 server implementing the Model Context Protocol.

    This is the LEGACY interface. It supports agent-registered tools via
    MCPToolRegistry. For the full MCP v2.0 server with resources, prompts,
    and transport support, use HRMCPServer from src.mcp.server.

    Provides three core methods:
    1. initialize — Returns server info and capabilities
    2. tools/list — Returns all available tool descriptors
    3. tools/call — Executes a tool and returns the result

    Also proxies to HRMCPServer methods when available:
    4. resources/list, resources/read — Data resources
    5. prompts/list, prompts/get — Workflow prompts
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

        # Try to create the new v2 server for extended capabilities
        self._v2_server = None
        try:
            from src.mcp.server import HRMCPServer

            self._v2_server = HRMCPServer(name=name, version=version)
            logger.info(
                f"MCPServer: v2 server available ({self._v2_server.get_stats()['tools']} built-in tools)"
            )
        except Exception as e:
            logger.debug(f"MCPServer: v2 server not available ({e}), using legacy mode")

        # Method dispatch table
        self._methods = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "ping": self._handle_ping,
            # Extended methods (delegated to v2 server)
            "resources/list": self._handle_v2_delegate,
            "resources/read": self._handle_v2_delegate,
            "resources/templates/list": self._handle_v2_delegate,
            "prompts/list": self._handle_v2_delegate,
            "prompts/get": self._handle_v2_delegate,
            "logging/setLevel": self._handle_v2_delegate,
            "notifications/initialized": self._handle_v2_delegate,
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
            if handler == self._handle_v2_delegate:
                result = self._handle_v2_delegate(params, method=method)
            else:
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
        capabilities = {
            "tools": {"listChanged": False},
        }
        # Add extended capabilities if v2 server is available
        if self._v2_server:
            capabilities["resources"] = {"subscribe": False, "listChanged": False}
            capabilities["prompts"] = {"listChanged": False}
            capabilities["logging"] = {}

        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": capabilities,
            "serverInfo": {
                "name": self.name,
                "version": self.version,
            },
        }

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tools/list request — return all available tools.

        Merges agent-registered tools with v2 built-in tools.
        """
        # Agent-registered tools
        agent_filter = params.get("agent_type")
        legacy_tools = self.registry.list_tools(agent_type=agent_filter)

        # v2 built-in tools
        v2_tools = []
        if self._v2_server and not agent_filter:
            v2_result = self._v2_server._handle_tools_list(params)
            v2_tools = v2_result.get("tools", [])

        # Merge (v2 tools first, then agent-registered)
        seen_names = set()
        merged = []
        for tool in v2_tools:
            if tool["name"] not in seen_names:
                merged.append(tool)
                seen_names.add(tool["name"])
        for tool in legacy_tools:
            if tool["name"] not in seen_names:
                merged.append(tool)
                seen_names.add(tool["name"])

        return {"tools": merged}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tools/call request — execute a tool.

        Tries v2 built-in tools first, then falls back to agent-registered tools.
        """
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required")

        # Try v2 built-in tools first
        if self._v2_server:
            try:
                return self._v2_server._handle_tools_call(params)
            except KeyError:
                pass  # Not a v2 tool, try legacy

        # Fall back to agent-registered tools
        result = self.registry.call_tool(tool_name, arguments)
        return result

    def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request — health check."""
        return {"status": "ok"}

    def _handle_v2_delegate(self, params: Dict[str, Any], method: str = "") -> Dict[str, Any]:
        """Delegate to v2 server for extended MCP methods."""
        if not self._v2_server:
            raise ValueError(f"Method {method} requires v2 server (not available)")
        response = self._v2_server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": "delegate",
            }
        )
        if "error" in response:
            raise Exception(response["error"]["message"])
        return response.get("result", {})

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
        stats = {
            "server_name": self.name,
            "version": self.version,
            "protocol_version": self.PROTOCOL_VERSION,
            "initialized": self._initialized,
            "agent_registered_tools": self.registry.get_tool_count(),
            "agent_types": self.registry.get_agent_types(),
        }
        if self._v2_server:
            v2_stats = self._v2_server.get_stats()
            stats["v2_builtin_tools"] = v2_stats["tools"]
            stats["v2_resources"] = v2_stats["resources"]
            stats["v2_resource_templates"] = v2_stats["resource_templates"]
            stats["v2_prompts"] = v2_stats["prompts"]
        return stats

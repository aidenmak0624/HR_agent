"""
MCP Tool Registry — Centralised registry of all agent tools as MCP-compatible descriptors.

Maps each specialist agent's native Python functions to MCP tool schema format
(JSON-RPC 2.0 compatible). Enables dynamic tool discovery and invocation.

Usage:
    registry = MCPToolRegistry()
    registry.register_agent("leave_request", LeaveRequestAgent(llm))
    tools = registry.list_tools()          # MCP tool descriptors
    result = registry.call_tool("submit_leave_request", {"query": "..."})
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPToolDescriptor:
    """
    MCP-compatible tool descriptor following the Model Context Protocol spec.

    Fields:
        name: Unique tool identifier (e.g., "leave_request.submit_leave_request")
        description: Human-readable description of what the tool does
        agent_type: Which specialist agent owns this tool
        input_schema: JSON Schema describing expected input parameters
        callable_fn: Reference to the actual Python function
    """

    name: str
    description: str
    agent_type: str
    input_schema: Dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Query or JSON payload for the tool"}
            },
            "required": ["query"],
        }
    )
    callable_fn: Optional[Callable] = None

    def to_mcp_format(self) -> Dict[str, Any]:
        """
        Convert to MCP tools/list response format.

        Returns:
            Dict matching MCP protocol tool descriptor schema.
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPToolRegistry:
    """
    Central registry that maps all agent tools to MCP-compatible descriptors.

    Supports:
    - Registering agents and auto-discovering their tools
    - Listing all tools in MCP format (for tools/list response)
    - Calling any tool by fully-qualified name (for tools/call request)
    - Filtering tools by agent type
    """

    def __init__(self):
        self._tools: Dict[str, MCPToolDescriptor] = {}
        self._agents: Dict[str, Any] = {}

    def register_agent(self, agent_type: str, agent_instance: Any) -> int:
        """
        Register a specialist agent and auto-discover its tools.

        Args:
            agent_type: Agent identifier (e.g., "leave_request", "benefits")
            agent_instance: Agent instance with get_tools() method

        Returns:
            Number of tools registered from this agent.

        Raises:
            ValueError: If agent has no get_tools() method.
        """
        if not hasattr(agent_instance, "get_tools"):
            raise ValueError(f"Agent {agent_type} has no get_tools() method")

        self._agents[agent_type] = agent_instance
        tools = agent_instance.get_tools()
        count = 0

        for tool_name, tool_fn in tools.items():
            fq_name = f"{agent_type}.{tool_name}"

            # Extract description from docstring or function name
            doc = getattr(tool_fn, "__doc__", None) or f"{tool_name} tool"
            description = doc.strip().split("\n")[0]  # First line only

            descriptor = MCPToolDescriptor(
                name=fq_name,
                description=description,
                agent_type=agent_type,
                callable_fn=tool_fn,
            )
            self._tools[fq_name] = descriptor
            count += 1

        logger.info(f"MCPRegistry: Registered {count} tools from {agent_type}")
        return count

    def list_tools(self, agent_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all tools in MCP format (for tools/list JSON-RPC response).

        Args:
            agent_type: Optional filter — only tools from this agent.

        Returns:
            List of MCP tool descriptors.
        """
        tools = self._tools.values()
        if agent_type:
            tools = [t for t in tools if t.agent_type == agent_type]
        return [t.to_mcp_format() for t in tools]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool by its fully-qualified MCP name (for tools/call JSON-RPC request).

        Args:
            tool_name: Fully qualified name (e.g., "leave_request.submit_leave_request")
            arguments: Dict with at least {"query": "..."} matching the input schema

        Returns:
            Dict with tool result, wrapped in MCP content format.

        Raises:
            KeyError: If tool_name is not registered.
            Exception: If tool execution fails (wrapped in error response).
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool not found: {tool_name}")

        descriptor = self._tools[tool_name]
        fn = descriptor.callable_fn

        if fn is None:
            return {
                "content": [{"type": "text", "text": "Tool has no callable function"}],
                "isError": True,
            }

        query = arguments.get("query", "")

        try:
            result = fn(query)
            return {
                "content": [{"type": "text", "text": str(result)}],
                "isError": False,
            }
        except Exception as e:
            logger.error(f"MCPRegistry: Tool {tool_name} failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }

    def get_tool_count(self) -> int:
        """Return total number of registered tools."""
        return len(self._tools)

    def get_agent_types(self) -> List[str]:
        """Return list of registered agent types."""
        return list(self._agents.keys())

    def get_tool_descriptor(self, tool_name: str) -> Optional[MCPToolDescriptor]:
        """Get a specific tool descriptor by name."""
        return self._tools.get(tool_name)

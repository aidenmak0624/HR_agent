"""
LangSmith tracing integration for LangGraph agent monitoring.
Iteration 4: Provides global tracing setup + custom callback handler.

Usage:
    # Global tracing (auto-traces ALL LangChain/LangGraph calls):
    LangSmithTracer.setup_tracing(enabled=True, api_key="...", project="hr-multi-agent")

    # Custom per-agent callback (enriched metadata):
    callback = LangSmithTracer.create_callback("PolicyAgent", correlation_id="req-123")
    result = graph.invoke(state, {"callbacks": [callback]})
"""

import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentTraceCallback:
    """
    Custom callback handler for enriched agent tracing.

    Logs LLM calls, tool usage, node transitions, and errors with
    structured metadata (trace_id, agent_name, correlation_id).

    Compatible with LangChain's callback protocol via duck-typing.
    Works independently of LangSmith — logs locally even when tracing is off.
    """

    def __init__(
        self,
        trace_id: str,
        agent_name: str,
        correlation_id: Optional[str] = None,
    ):
        self.trace_id = trace_id
        self.agent_name = agent_name
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.start_time = datetime.utcnow()
        self.events: List[Dict[str, Any]] = []
        self._step_count = 0

        # LangChain callback protocol attributes
        self.raise_error = False
        self.run_inline = False
        self.ignore_llm = False
        self.ignore_chain = False
        self.ignore_agent = False
        self.ignore_retriever = False

    # ==================== LLM CALLBACKS ====================

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """Log when an LLM call starts."""
        self._step_count += 1
        model = serialized.get("kwargs", {}).get("model", "unknown")
        event = {
            "type": "llm_start",
            "step": self._step_count,
            "agent": self.agent_name,
            "model": model,
            "prompts_count": len(prompts),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        logger.debug(
            f"[TRACE:{self.trace_id}] [{self.agent_name}] LLM start "
            f"model={model} prompts={len(prompts)}"
        )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Log when an LLM call completes."""
        generations = (
            len(response.generations) if hasattr(response, "generations") else 0
        )
        event = {
            "type": "llm_end",
            "step": self._step_count,
            "agent": self.agent_name,
            "generations": generations,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        logger.debug(
            f"[TRACE:{self.trace_id}] [{self.agent_name}] LLM end "
            f"generations={generations}"
        )

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Log LLM errors."""
        event = {
            "type": "llm_error",
            "step": self._step_count,
            "agent": self.agent_name,
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        logger.warning(
            f"[TRACE:{self.trace_id}] [{self.agent_name}] LLM error: {error}"
        )

    # ==================== TOOL CALLBACKS ====================

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Log when a tool execution starts."""
        self._step_count += 1
        tool_name = serialized.get("name", "unknown")
        event = {
            "type": "tool_start",
            "step": self._step_count,
            "agent": self.agent_name,
            "tool": tool_name,
            "input_preview": input_str[:200],
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        logger.debug(
            f"[TRACE:{self.trace_id}] [{self.agent_name}] Tool start: {tool_name}"
        )

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Log when a tool execution completes."""
        event = {
            "type": "tool_end",
            "step": self._step_count,
            "agent": self.agent_name,
            "output_length": len(output) if output else 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        logger.debug(
            f"[TRACE:{self.trace_id}] [{self.agent_name}] Tool end "
            f"output_len={len(output) if output else 0}"
        )

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """Log tool errors."""
        event = {
            "type": "tool_error",
            "step": self._step_count,
            "agent": self.agent_name,
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        logger.warning(
            f"[TRACE:{self.trace_id}] [{self.agent_name}] Tool error: {error}"
        )

    # ==================== CHAIN CALLBACKS ====================

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Log when a chain (graph node) starts."""
        self._step_count += 1
        if serialized:
            chain_name = serialized.get("name", serialized.get("id", ["unknown"])[-1])
        else:
            chain_name = "unknown"
        event = {
            "type": "chain_start",
            "step": self._step_count,
            "agent": self.agent_name,
            "chain": chain_name,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        logger.debug(
            f"[TRACE:{self.trace_id}] [{self.agent_name}] Node start: {chain_name}"
        )

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Log when a chain (graph node) completes."""
        event = {
            "type": "chain_end",
            "step": self._step_count,
            "agent": self.agent_name,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        """Log chain errors."""
        event = {
            "type": "chain_error",
            "step": self._step_count,
            "agent": self.agent_name,
            "error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        logger.warning(
            f"[TRACE:{self.trace_id}] [{self.agent_name}] Chain error: {error}"
        )

    # ==================== SUMMARY ====================

    def get_trace_summary(self) -> Dict[str, Any]:
        """Get a summary of all traced events."""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        return {
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "agent_name": self.agent_name,
            "total_steps": self._step_count,
            "total_events": len(self.events),
            "elapsed_seconds": round(elapsed, 3),
            "llm_calls": sum(1 for e in self.events if e["type"] == "llm_start"),
            "tool_calls": sum(1 for e in self.events if e["type"] == "tool_start"),
            "errors": sum(1 for e in self.events if "error" in e["type"]),
            "events": self.events,
        }


class LangSmithTracer:
    """
    Wrapper for LangSmith tracing setup and management.

    LangSmith tracing can work in two modes:
    1. Global (env var) — set LANGCHAIN_TRACING_V2=true to auto-trace everything
    2. Per-agent callback — use create_callback() for enriched per-run metadata

    Both can be used simultaneously.
    """

    _initialized = False

    @staticmethod
    def setup_tracing(
        enabled: bool = False,
        api_key: str = "",
        project: str = "hr-multi-agent",
    ) -> None:
        """
        Setup LangSmith global tracing via environment variables.

        When enabled, ALL LangChain/LangGraph operations are automatically
        traced to LangSmith. This requires no code changes to agents.

        Args:
            enabled: Whether to enable global tracing
            api_key: LangSmith API key
            project: LangSmith project name
        """
        if LangSmithTracer._initialized:
            return

        if not enabled:
            logger.info("LangSmith tracing: disabled")
            LangSmithTracer._initialized = True
            return

        if not api_key:
            logger.warning(
                "LangSmith tracing enabled but LANGCHAIN_API_KEY not set. "
                "Get your key at https://smith.langchain.com"
            )
            LangSmithTracer._initialized = True
            return

        # Set environment variables for LangSmith global auto-tracing
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project

        logger.info(f"✅ LangSmith tracing enabled → project: {project}")
        LangSmithTracer._initialized = True

    @staticmethod
    def create_callback(
        agent_name: str,
        correlation_id: Optional[str] = None,
    ) -> AgentTraceCallback:
        """
        Create a callback handler for a single agent execution.

        This callback enriches traces with agent-specific metadata:
        - trace_id (unique per execution)
        - agent_name (e.g., "PolicyAgent", "RouterAgent")
        - correlation_id (request ID for cross-service tracing)

        Args:
            agent_name: Name of the agent being traced
            correlation_id: Optional request/correlation ID

        Returns:
            AgentTraceCallback instance
        """
        trace_id = str(uuid.uuid4())[:8]
        return AgentTraceCallback(
            trace_id=trace_id,
            agent_name=agent_name,
            correlation_id=correlation_id,
        )

    @staticmethod
    def is_enabled() -> bool:
        """Check if LangSmith tracing is currently enabled."""
        return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"

    @staticmethod
    def reset() -> None:
        """Reset tracing state (useful for testing)."""
        LangSmithTracer._initialized = False

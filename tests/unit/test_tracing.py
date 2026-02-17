"""
Unit tests for LangSmith tracing module.
Iteration 4: Tests for AgentTraceCallback and LangSmithTracer.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.core.tracing import AgentTraceCallback, LangSmithTracer

# ==================== AgentTraceCallback Tests ====================


class TestAgentTraceCallbackInit:
    """Tests for AgentTraceCallback initialization."""

    def test_init_with_all_params(self):
        """Callback initializes with trace_id, agent_name, correlation_id."""
        cb = AgentTraceCallback(
            trace_id="t-001",
            agent_name="PolicyAgent",
            correlation_id="req-abc",
        )
        assert cb.trace_id == "t-001"
        assert cb.agent_name == "PolicyAgent"
        assert cb.correlation_id == "req-abc"
        assert cb.events == []
        assert cb._step_count == 0

    def test_init_auto_correlation_id(self):
        """Callback generates correlation_id if not provided."""
        cb = AgentTraceCallback(trace_id="t-002", agent_name="LeaveAgent")
        assert cb.correlation_id is not None
        assert len(cb.correlation_id) > 0

    def test_init_sets_start_time(self):
        """Callback records start time on creation."""
        cb = AgentTraceCallback(trace_id="t-003", agent_name="TestAgent")
        assert isinstance(cb.start_time, datetime)


class TestLLMCallbacks:
    """Tests for LLM-related callbacks."""

    def test_on_llm_start(self):
        """on_llm_start records event with model and prompt count."""
        cb = AgentTraceCallback(trace_id="t-010", agent_name="TestAgent")
        cb.on_llm_start(
            serialized={"kwargs": {"model": "gpt-4o-mini"}},
            prompts=["Hello", "World"],
        )
        assert len(cb.events) == 1
        assert cb.events[0]["type"] == "llm_start"
        assert cb.events[0]["model"] == "gpt-4o-mini"
        assert cb.events[0]["prompts_count"] == 2
        assert cb._step_count == 1

    def test_on_llm_end(self):
        """on_llm_end records event with generation count."""
        cb = AgentTraceCallback(trace_id="t-011", agent_name="TestAgent")
        mock_response = MagicMock()
        mock_response.generations = [["gen1"], ["gen2"]]
        cb.on_llm_end(response=mock_response)
        assert len(cb.events) == 1
        assert cb.events[0]["type"] == "llm_end"
        assert cb.events[0]["generations"] == 2

    def test_on_llm_error(self):
        """on_llm_error records error event."""
        cb = AgentTraceCallback(trace_id="t-012", agent_name="TestAgent")
        cb.on_llm_error(error=ValueError("API timeout"))
        assert len(cb.events) == 1
        assert cb.events[0]["type"] == "llm_error"
        assert "API timeout" in cb.events[0]["error"]


class TestToolCallbacks:
    """Tests for tool-related callbacks."""

    def test_on_tool_start(self):
        """on_tool_start records tool name and input preview."""
        cb = AgentTraceCallback(trace_id="t-020", agent_name="TestAgent")
        cb.on_tool_start(
            serialized={"name": "rag_search"},
            input_str="What is the leave policy?",
        )
        assert len(cb.events) == 1
        assert cb.events[0]["type"] == "tool_start"
        assert cb.events[0]["tool"] == "rag_search"
        assert "leave policy" in cb.events[0]["input_preview"]

    def test_on_tool_end(self):
        """on_tool_end records output length."""
        cb = AgentTraceCallback(trace_id="t-021", agent_name="TestAgent")
        cb.on_tool_end(output="The leave policy states that...")
        assert cb.events[0]["type"] == "tool_end"
        assert cb.events[0]["output_length"] > 0

    def test_on_tool_end_empty_output(self):
        """on_tool_end handles empty output."""
        cb = AgentTraceCallback(trace_id="t-022", agent_name="TestAgent")
        cb.on_tool_end(output="")
        assert cb.events[0]["output_length"] == 0

    def test_on_tool_error(self):
        """on_tool_error records error event."""
        cb = AgentTraceCallback(trace_id="t-023", agent_name="TestAgent")
        cb.on_tool_error(error=RuntimeError("Tool failed"))
        assert cb.events[0]["type"] == "tool_error"
        assert "Tool failed" in cb.events[0]["error"]


class TestChainCallbacks:
    """Tests for chain/node-related callbacks."""

    def test_on_chain_start(self):
        """on_chain_start records chain name."""
        cb = AgentTraceCallback(trace_id="t-030", agent_name="TestAgent")
        cb.on_chain_start(
            serialized={"name": "planner"},
            inputs={"query": "test"},
        )
        assert cb.events[0]["type"] == "chain_start"
        assert cb.events[0]["chain"] == "planner"

    def test_on_chain_start_id_fallback(self):
        """on_chain_start falls back to id[-1] if name missing."""
        cb = AgentTraceCallback(trace_id="t-031", agent_name="TestAgent")
        cb.on_chain_start(
            serialized={"id": ["langchain", "chains", "MyChain"]},
            inputs={},
        )
        assert cb.events[0]["chain"] == "MyChain"

    def test_on_chain_end(self):
        """on_chain_end records completion event."""
        cb = AgentTraceCallback(trace_id="t-032", agent_name="TestAgent")
        cb.on_chain_end(outputs={"result": "done"})
        assert cb.events[0]["type"] == "chain_end"

    def test_on_chain_error(self):
        """on_chain_error records error event."""
        cb = AgentTraceCallback(trace_id="t-033", agent_name="TestAgent")
        cb.on_chain_error(error=RuntimeError("Node failed"))
        assert cb.events[0]["type"] == "chain_error"
        assert "Node failed" in cb.events[0]["error"]


class TestTraceSummary:
    """Tests for trace summary generation."""

    def test_empty_summary(self):
        """Empty callback produces valid summary."""
        cb = AgentTraceCallback(trace_id="t-040", agent_name="TestAgent")
        summary = cb.get_trace_summary()
        assert summary["trace_id"] == "t-040"
        assert summary["agent_name"] == "TestAgent"
        assert summary["total_steps"] == 0
        assert summary["total_events"] == 0
        assert summary["llm_calls"] == 0
        assert summary["tool_calls"] == 0
        assert summary["errors"] == 0

    def test_summary_counts_events(self):
        """Summary correctly counts LLM calls, tool calls, and errors."""
        cb = AgentTraceCallback(trace_id="t-041", agent_name="TestAgent")
        # Simulate a full agent run
        cb.on_chain_start(serialized={"name": "planner"}, inputs={})
        cb.on_llm_start(serialized={"kwargs": {}}, prompts=["plan"])
        cb.on_llm_end(response=MagicMock(generations=[]))
        cb.on_chain_end(outputs={})
        cb.on_tool_start(serialized={"name": "rag"}, input_str="q")
        cb.on_tool_end(output="result")
        cb.on_tool_start(serialized={"name": "web"}, input_str="q")
        cb.on_tool_error(error=RuntimeError("fail"))

        summary = cb.get_trace_summary()
        assert summary["llm_calls"] == 1
        assert summary["tool_calls"] == 2
        assert summary["errors"] == 1
        assert summary["total_events"] == 8

    def test_summary_elapsed_time(self):
        """Summary includes elapsed time > 0."""
        cb = AgentTraceCallback(trace_id="t-042", agent_name="TestAgent")
        cb.on_llm_start(serialized={"kwargs": {}}, prompts=["hi"])
        summary = cb.get_trace_summary()
        assert summary["elapsed_seconds"] >= 0


class TestStepCounting:
    """Tests for step counter incrementing."""

    def test_steps_increment_on_starts(self):
        """Step count increments on llm_start, tool_start, chain_start."""
        cb = AgentTraceCallback(trace_id="t-050", agent_name="TestAgent")
        cb.on_llm_start(serialized={"kwargs": {}}, prompts=[])
        cb.on_tool_start(serialized={"name": "t"}, input_str="")
        cb.on_chain_start(serialized={"name": "c"}, inputs={})
        assert cb._step_count == 3

    def test_steps_dont_increment_on_ends(self):
        """Step count does NOT increment on end events."""
        cb = AgentTraceCallback(trace_id="t-051", agent_name="TestAgent")
        cb.on_llm_end(response=MagicMock(generations=[]))
        cb.on_tool_end(output="")
        cb.on_chain_end(outputs={})
        assert cb._step_count == 0


# ==================== LangSmithTracer Tests ====================


class TestLangSmithTracerSetup:
    """Tests for LangSmithTracer.setup_tracing()."""

    def setup_method(self):
        """Reset tracer state before each test."""
        LangSmithTracer.reset()
        # Clean env vars
        for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
            os.environ.pop(key, None)

    def teardown_method(self):
        """Clean up env vars after each test."""
        LangSmithTracer.reset()
        for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
            os.environ.pop(key, None)

    def test_disabled_by_default(self):
        """Tracing is disabled when enabled=False."""
        LangSmithTracer.setup_tracing(enabled=False)
        assert os.environ.get("LANGCHAIN_TRACING_V2") is None

    def test_enabled_sets_env_vars(self):
        """Enabling tracing sets all required env vars."""
        LangSmithTracer.setup_tracing(
            enabled=True,
            api_key="lsv2_test_key_123",
            project="test-project",
        )
        assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
        assert os.environ["LANGCHAIN_API_KEY"] == "lsv2_test_key_123"
        assert os.environ["LANGCHAIN_PROJECT"] == "test-project"

    def test_enabled_without_api_key_warns(self):
        """Enabling without API key does NOT set env vars."""
        LangSmithTracer.setup_tracing(enabled=True, api_key="")
        assert os.environ.get("LANGCHAIN_TRACING_V2") is None

    def test_idempotent_setup(self):
        """Calling setup twice is safe (only first call takes effect)."""
        LangSmithTracer.setup_tracing(enabled=True, api_key="key1", project="proj1")
        LangSmithTracer.setup_tracing(enabled=True, api_key="key2", project="proj2")
        # First call wins
        assert os.environ["LANGCHAIN_API_KEY"] == "key1"
        assert os.environ["LANGCHAIN_PROJECT"] == "proj1"


class TestLangSmithTracerCreateCallback:
    """Tests for LangSmithTracer.create_callback()."""

    def test_create_callback_returns_instance(self):
        """create_callback returns AgentTraceCallback."""
        cb = LangSmithTracer.create_callback("PolicyAgent")
        assert isinstance(cb, AgentTraceCallback)
        assert cb.agent_name == "PolicyAgent"

    def test_create_callback_with_correlation_id(self):
        """create_callback passes correlation_id through."""
        cb = LangSmithTracer.create_callback("LeaveAgent", correlation_id="req-xyz")
        assert cb.correlation_id == "req-xyz"

    def test_create_callback_unique_trace_ids(self):
        """Each callback gets a unique trace_id."""
        cb1 = LangSmithTracer.create_callback("A")
        cb2 = LangSmithTracer.create_callback("B")
        assert cb1.trace_id != cb2.trace_id


class TestLangSmithTracerHelpers:
    """Tests for helper methods."""

    def setup_method(self):
        LangSmithTracer.reset()
        os.environ.pop("LANGCHAIN_TRACING_V2", None)

    def teardown_method(self):
        LangSmithTracer.reset()
        os.environ.pop("LANGCHAIN_TRACING_V2", None)

    def test_is_enabled_false(self):
        """is_enabled returns False when env var not set."""
        assert LangSmithTracer.is_enabled() is False

    def test_is_enabled_true(self):
        """is_enabled returns True when env var is 'true'."""
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        assert LangSmithTracer.is_enabled() is True

    def test_reset_allows_reinit(self):
        """reset() allows setup to run again."""
        LangSmithTracer.setup_tracing(enabled=False)
        assert LangSmithTracer._initialized is True
        LangSmithTracer.reset()
        assert LangSmithTracer._initialized is False

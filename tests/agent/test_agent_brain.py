# tests/agent/test_agent_brain.py

import pytest
from src.agent.agent_brain import HRAssistantAgent


def test_agent_simple_query():
    """Test agent on simple factual query."""
    agent = HRAssistantAgent(api_key="test_key")

    result = agent.run(query="What is the PTO policy?", topic="benefits", difficulty="quick")

    assert result["answer"]
    assert len(result["sources"]) > 0
    assert result["confidence"] > 0.5
    assert "rag_search" in result["tools_used"]


def test_agent_comparison_query():
    """Test agent on comparison query."""
    agent = HRAssistantAgent(api_key="test_key")

    result = agent.run(
        query="Compare PPO and HMO health plans", topic="benefits", difficulty="detailed"
    )

    assert "compare" in result["answer"].lower() or "differ" in result["answer"].lower()
    assert "comparator" in result["tools_used"]


def test_agent_max_iterations():
    """Test that agent respects max iterations."""
    agent = HRAssistantAgent(api_key="test_key")

    result = agent.run(
        query="Complex multi-step query about benefits and employment law", topic="benefits"
    )

    assert len(result["tools_used"]) <= 5  # max_iterations

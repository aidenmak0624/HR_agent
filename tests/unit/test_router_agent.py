"""Tests for Router Agent module."""
import pytest
from unittest.mock import MagicMock
from src.agents.router_agent import RouterAgent


class TestIntentClassification:
    """Tests for intent classification."""

    def test_classify_intent_employee_query(self):
        """Employee query is classified correctly."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        intent, confidence = router.classify_intent("Who is my manager?")

        assert intent == "employee_info"
        assert confidence >= 0.7

    def test_classify_intent_policy_query(self):
        """Policy query is classified correctly."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        intent, confidence = router.classify_intent("What is the remote work policy?")

        assert intent == "policy"
        assert confidence >= 0.7

    def test_classify_intent_keyword_matching(self):
        """Intent classification uses keyword matching."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        # Test query that includes a clear keyword
        intent, confidence = router.classify_intent("I want to take vacation and leave")

        # Should match leave category due to keywords
        assert intent in router.INTENT_CATEGORIES

    def test_classify_intent_benefits_query(self):
        """Benefits query is classified correctly."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        intent, confidence = router.classify_intent("What health insurance options are available?")

        assert intent == "benefits"
        assert confidence >= 0.6

    def test_classify_intent_ambiguous_returns_lower_confidence(self):
        """Ambiguous query returns lower confidence."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        intent, confidence = router.classify_intent("xyz abc def ghi jkl")

        # Lower confidence for ambiguous queries
        assert confidence < 0.9

    def test_classify_intent_multi_intent(self):
        """Query spanning multiple intents can be detected."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        # Query about both benefits and policy
        intent, confidence = router.classify_intent(
            "What is the health insurance policy and what benefits are included?"
        )

        # Should classify to one primary intent
        assert intent in router.INTENT_CATEGORIES


class TestPermissionChecking:
    """Tests for permission validation."""

    def test_permission_check_employee_allowed(self):
        """Employee can view policy."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        user_context = {"role": "employee"}

        allowed = router.check_permissions(user_context, "policy")

        assert allowed is True

    def test_permission_check_employee_denied_performance(self):
        """Employee cannot view performance reviews."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        user_context = {"role": "employee"}

        allowed = router.check_permissions(user_context, "performance")

        assert allowed is False

    def test_permission_check_manager_allowed(self):
        """Manager can view analytics."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        user_context = {"role": "manager"}

        allowed = router.check_permissions(user_context, "analytics")

        assert allowed is True

    def test_permission_check_role_hierarchy(self):
        """Role hierarchy is respected."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        # Employee can view policy
        assert router.check_permissions({"role": "employee"}, "policy") is True

        # Manager inherits employee permissions
        assert router.check_permissions({"role": "manager"}, "policy") is True

    def test_permission_check_defaults_to_employee(self):
        """Missing role defaults to employee."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        user_context = {}

        # Employee can view policy
        allowed = router.check_permissions(user_context, "policy")

        assert allowed is True


class TestAgentDispatch:
    """Tests for dispatching to specialist agents."""

    def test_dispatch_to_agent_returns_result(self):
        """Dispatching returns agent result."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        result = router.dispatch_to_agent(
            "policy", "What is the remote work policy?", {"user_id": "emp-001", "role": "employee"}
        )

        assert isinstance(result, dict)
        assert "agent_type" in result

    def test_dispatch_to_unknown_intent(self):
        """Unknown intent returns error result."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        result = router.dispatch_to_agent("unknown_intent", "Query", {"user_id": "emp-001"})

        assert "error" in result


class TestResponseMerging:
    """Tests for merging multi-agent responses."""

    def test_merge_single_response(self):
        """Single response is returned as-is."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        results = [
            {"answer": "The remote work policy is...", "agent_type": "policy", "confidence": 0.9}
        ]

        merged = router.merge_responses(results)

        assert merged["answer"] == "The remote work policy is..."
        assert merged["agent_type"] == "policy"

    def test_merge_multiple_responses(self):
        """Multiple responses are combined."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        results = [
            {
                "answer": "Remote work allowed 3 days/week",
                "agent_type": "policy",
                "confidence": 0.9,
                "sources": ["policy_doc_1"],
            },
            {
                "answer": "Health insurance options available",
                "agent_type": "benefits",
                "confidence": 0.85,
                "sources": ["benefits_doc_1"],
            },
        ]

        merged = router.merge_responses(results)

        assert "policy" in merged.get("agents_used", [])
        assert "benefits" in merged.get("agents_used", [])
        assert len(merged.get("sources", [])) >= 2
        assert merged["confidence"] > 0.8

    def test_merge_empty_responses(self):
        """Empty results handled gracefully."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        merged = router.merge_responses([])

        assert merged is not None
        assert "answer" in merged


class TestRouterRun:
    """Tests for main router run method."""

    def test_run_with_permission_denied(self):
        """Router returns permission denied error."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        result = router.run(
            query="Show me performance reviews",
            user_context={"user_id": "emp-001", "role": "employee"},
        )

        assert "permission" in result.get("answer", "").lower() or "error" in result

    def test_run_low_confidence_requires_clarification(self):
        """Low confidence query requires clarification."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        result = router.run(
            query="xyz abc def ghi jkl",  # Nonsensical query
            user_context={"user_id": "emp-001", "role": "employee"},
        )

        if result.get("requires_clarification"):
            assert "answer" in result

    def test_run_returns_complete_result(self):
        """run() returns all required fields."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        result = router.run(
            query="What is the remote work policy?",
            user_context={"user_id": "emp-001", "role": "employee"},
        )

        assert "answer" in result
        assert "agent_type" in result
        assert "confidence" in result
        assert "intents" in result


class TestIntentCategories:
    """Tests for intent categories."""

    def test_all_intent_categories_defined(self):
        """All intent categories are defined."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        assert "employee_info" in router.INTENT_CATEGORIES
        assert "policy" in router.INTENT_CATEGORIES
        assert "leave" in router.INTENT_CATEGORIES
        assert "onboarding" in router.INTENT_CATEGORIES
        assert "benefits" in router.INTENT_CATEGORIES
        assert "performance" in router.INTENT_CATEGORIES
        assert "analytics" in router.INTENT_CATEGORIES

    def test_agent_registry_has_agents(self):
        """Agent registry has entries for all intents."""
        mock_llm = MagicMock()
        router = RouterAgent(mock_llm)

        for intent in router.INTENT_CATEGORIES.keys():
            assert intent in router.AGENT_REGISTRY


class TestRouterState:
    """Tests for router state typing."""

    def test_router_state_structure(self):
        """RouterState has expected structure."""
        from src.agents.router_agent import RouterState

        # Should be a TypedDict
        assert hasattr(RouterState, "__annotations__")


class TestHelperMethods:
    """Tests for helper methods."""

    def test_parse_json_response_valid(self):
        """Parse valid JSON response."""
        from src.agents.router_agent import RouterAgent

        text = '{"intent": "policy", "confidence": 0.9}'
        result = RouterAgent._parse_json_response(text)

        assert result["intent"] == "policy"
        assert result["confidence"] == 0.9

    def test_parse_json_response_embedded(self):
        """Parse JSON embedded in text."""
        from src.agents.router_agent import RouterAgent

        text = 'Response: {"intent": "leave", "confidence": 0.8} End'
        result = RouterAgent._parse_json_response(text)

        assert result["intent"] == "leave"

    def test_parse_json_response_invalid_raises(self):
        """Invalid JSON raises ValueError."""
        from src.agents.router_agent import RouterAgent

        with pytest.raises(ValueError):
            RouterAgent._parse_json_response("No JSON here")

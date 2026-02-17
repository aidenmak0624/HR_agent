"""
Unit tests for agent tools.
"""

import pytest
from src.agent.tools.rag_tool import RAGSearchTool
from src.agent.tools.fact_checker import FactVerifierTool
from src.agent.tools.comparator import ComparatorTool
from src.agent.tools.planner import EducationalPlannerTool


def test_rag_tool():
    """Test RAG search tool."""
    tool = RAGSearchTool()

    result = tool.run(query="What is the PTO policy?", topic="benefits", top_k=5)

    assert "answer" in result
    assert "sources" in result
    assert len(result["sources"]) > 0
    assert tool.call_count == 1


def test_fact_verifier_tool():
    """Test fact verification tool."""
    tool = FactVerifierTool()

    result = tool.run(claim="TechNova matches 5% on 401k contributions", topic="benefits")

    assert "verified" in result
    assert "confidence" in result
    assert isinstance(result["verified"], bool)
    assert 0.0 <= result["confidence"] <= 1.0


def test_comparator_tool():
    """Test comparison tool."""
    tool = ComparatorTool()

    result = tool.run(aspect="health insurance plans", topic="benefits")

    assert "comparison" in result
    assert "similarities" in result
    assert "differences" in result
    assert "documents_analyzed" in result


def test_educational_planner_lesson():
    """Test educational planner - lesson plan."""
    tool = EducationalPlannerTool()

    result = tool.run(
        content_type="lesson_plan",
        topic="employee_handbook",
        level="high_school",
        details={"duration": "45 minutes"},
    )

    assert "content" in result
    assert "format" in result
    assert result["content_type"] == "lesson_plan"
    assert len(result["content"]) > 500  # Should be substantial


def test_educational_planner_quiz():
    """Test educational planner - quiz."""
    tool = EducationalPlannerTool()

    result = tool.run(
        content_type="quiz", topic="benefits", level="high_school", details={"num_questions": 10}
    )

    assert "content" in result
    assert result["content_type"] == "quiz"

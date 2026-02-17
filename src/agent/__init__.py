# src/agent/__init__.py
from typing import Any, Dict

# Fallback descriptions
_DESC_RAG = "Query the HR knowledge base using RAG."
_DESC_VER = "Verify a claim against retrieved HR policy sources."
_DESC_CMP = "Compare two HR policies and highlight differences."
_DESC_EDU = "Create a staged training plan for an HR topic."

# Import your concrete tools; if you renamed them, fix here.
from src.agent.tools.rag_tool import RAGSearchTool
from src.agent.tools.fact_checker import FactVerifierTool
from src.agent.tools.comparator import ComparatorTool
from src.agent.tools.planner import EducationalPlannerTool

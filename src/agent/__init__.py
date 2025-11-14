# src/agent/tools/__init__.py
from typing import Any, Dict

# Fallback descriptions
_DESC_RAG = "Query the human-rights knowledge base using RAG."
_DESC_VER = "Verify a claim against retrieved sources."
_DESC_CMP = "Compare two documents and highlight differences."
_DESC_EDU = "Create a staged learning plan for a topic."

# Import your concrete tools; if you renamed them, fix here.
from src.agent.tools.rag_tool import RAGSearchTool
from src.agent.tools.fact_checker import FactVerifierTool
from src.agent.tools.comparator import ComparatorTool
from src.agent.tools.planner import EducationalPlannerTool

class RAGSearchTool:
    description = _DESC_RAG
    def __init__(self):
        # RAGTool expects a RAGSystem; in the scaffold it was injected in FastAPI.
        # For standalone use, we construct a minimal in-memory instance.
        try:
           
            from src.core.rag_system import SimpleRAG
            self._vs = VectorStore()
            self._rag = SimpleRAG(self._vs)
            self._impl = RAGSearchTool(self._rag)
        except Exception:
            self._impl = None

    def run(self, **kwargs) -> Dict[str, Any]:
        if self._impl is None:
            return {"answer": "(stub) RAG not initialized", "sources": []}
        q = kwargs.get("query") or kwargs.get("q") or ""
        k = int(kwargs.get("k", 4))
        out = self._impl.run(query=q, k=k)
        # normalize keys for the agent
        return {"answer": out.get("answer"), "context": out.get("context"), "sources": out.get("top_k", [])}

class FactVerifierTool:
    description = _DESC_VER
    def __init__(self):
        try:
            
            from src.core.rag_system import SimpleRAG
            self._vs = VectorStore()
            self._rag = RAGSearchTool(self._vs)
            self._impl = FactVerifierTool(self._rag)
        except Exception:
            self._impl = None

    def run(self, **kwargs) -> Dict[str, Any]:
        if self._impl is None:
            return {"verdict": "inconclusive", "evidence": []}
        claim = kwargs.get("claim") or kwargs.get("query") or ""
        return self._impl.run(claim=claim)

class ComparatorTool:
    description = _DESC_CMP
    def __init__(self):
        self._impl = ComparatorTool()

    def run(self, **kwargs) -> Dict[str, Any]:
        a = kwargs.get("a", "")
        b = kwargs.get("b", "")
        return self._impl.run(a=a, b=b)

class EducationalPlannerTool:
    description = _DESC_EDU
    def __init__(self):
        self._impl = EducationalPlannerTool()

    def run(self, **kwargs) -> Dict[str, Any]:
        topic = kwargs.get("topic") or kwargs.get("query") or "Human rights"
        level = kwargs.get("level", "beginner")
        sessions = int(kwargs.get("sessions", 5))
        return self._impl.run(topic=topic, level=level, sessions=sessions)

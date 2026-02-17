# Quick Start Guide - Router Agent & RAG Pipeline

## Installation Requirements

```bash
pip install langgraph langchain langchain-google-genai sentence-transformers chromadb
```

## 1. Using BaseAgent - Create a Specialist Agent

```python
from src.agents.base_agent import BaseAgent, UserContext
from langchain_google_genai import ChatGoogleGenerativeAI

class LeaveAgent(BaseAgent):
    """Example specialist agent for leave management."""
    
    def __init__(self, llm: ChatGoogleGenerativeAI):
        super().__init__(llm)
    
    def get_tools(self):
        """Return available tools."""
        return {
            "leave_balance": LeaveBalanceTool(),
            "leave_policy": LeavePolicyTool(),
        }
    
    def get_system_prompt(self) -> str:
        """Return system prompt."""
        return """You are an expert HR agent specializing in leave management.
Help employees understand their leave balance and company policies."""
    
    def get_agent_type(self) -> str:
        """Return agent type."""
        return "leave_agent"

# Usage
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
agent = LeaveAgent(llm)

result = agent.run(
    query="How much PTO do I have left?",
    user_context={
        "user_id": "emp123",
        "role": "employee",
        "department": "engineering"
    }
)

print(result["answer"])
print(f"Confidence: {result['confidence']}")
print(f"Tools used: {result['tools_used']}")
```

## 2. Using RouterAgent - Multi-Agent Dispatch

```python
from src.agents.router_agent import RouterAgent
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
router = RouterAgent(llm)

# Single intent query
result = router.run(
    query="What is the remote work policy?",
    user_context={
        "user_id": "emp123",
        "role": "employee",
        "department": "sales"
    }
)

print(f"Intent detected: {result['intents']}")
print(f"Answer: {result['answer']}")
print(f"Agents used: {result['agents_used']}")

# Multi-intent query
result = router.run(
    query="What's the PTO policy and my remaining balance?",
    user_context={
        "user_id": "emp456",
        "role": "employee",
        "department": "marketing"
    }
)

print(f"Handled by agents: {result['agents_used']}")
print(result["answer"])
```

## 3. Using RAGPipeline - Document Retrieval

```python
from src.core.rag_pipeline import RAGPipeline

# Initialize RAG
rag = RAGPipeline(collection_name="hr_policies")

# Ingest documents
num_chunks = rag.ingest_document(
    file_path="docs/remote_work_policy.md",
    doc_type="policy",
    metadata={
        "last_updated": "2024-01-15",
        "section": "Work Arrangements"
    }
)
print(f"Ingested {num_chunks} chunks")

# Search documents
results = rag.search(
    query="remote work from home policy",
    collection="hr_policies",
    top_k=3,
    min_score=0.5
)

for result in results:
    print(f"\n{result.source} (score: {result.score:.2f})")
    print(f"Content: {result.content[:200]}...")
    print(f"Metadata: {result.metadata}")

# Get statistics
stats = rag.get_collection_stats()
print(stats)

# Health check
is_healthy = rag.health_check()
print(f"RAG healthy: {is_healthy}")
```

## 4. Integrating RAG with Agents

```python
from src.agents.base_agent import BaseAgent
from src.core.rag_pipeline import RAGPipeline

class PolicyAgent(BaseAgent):
    """Agent that uses RAG for policy lookup."""
    
    def __init__(self, llm):
        super().__init__(llm)
        # Initialize RAG for policy documents
        self.rag = RAGPipeline(collection_name="hr_policies")
    
    def get_tools(self):
        return {
            "policy_search": RAGSearchTool(self.rag),
        }
    
    def get_system_prompt(self) -> str:
        return "You are an HR policy expert. Answer policy questions using search results."
    
    def get_agent_type(self) -> str:
        return "policy_agent"

class RAGSearchTool:
    """Tool that wraps RAG search."""
    
    def __init__(self, rag: RAGPipeline):
        self.rag = rag
        self.description = "Search HR policy documents"
    
    def invoke(self, query: str) -> dict:
        """Execute RAG search."""
        results = self.rag.search(query, top_k=3)
        return {
            "sources": [r.source for r in results],
            "documents": [r.content for r in results],
            "scores": [r.score for r in results],
        }
```

## 5. Common Patterns

### Pattern A: Check Permissions Before Dispatch

```python
router = RouterAgent(llm)

# Check if user can access analytics
can_access = router.check_permissions(
    user_context={"role": "employee"},
    intent="analytics"
)

if not can_access:
    print("User doesn't have permission for analytics")
else:
    result = router.dispatch_to_agent("analytics", query, user_context)
```

### Pattern B: Handle Multi-Intent Queries

```python
router = RouterAgent(llm)

# Get all possible intents for a query
intent_a, conf_a = router.classify_intent("What's the PTO policy?")
intent_b, conf_b = router.classify_intent("How much leave do I have?")

intents = [(intent_a, conf_a), (intent_b, conf_b)]
results = router.handle_multi_intent(intents, query, user_context)

# Merge results from multiple agents
merged = router.merge_responses(results)
```

### Pattern C: Document Ingestion Workflow

```python
rag = RAGPipeline()

# Ingest multiple documents
docs = [
    ("policies/pto.md", "policy", {"section": "Time Off"}),
    ("policies/remote.md", "policy", {"section": "Work"}),
    ("handbook/benefits.md", "handbook", {"section": "Benefits"}),
]

for path, doc_type, metadata in docs:
    chunks = rag.ingest_document(path, doc_type, metadata)
    print(f"✓ {path}: {chunks} chunks")

# Verify ingestion
stats = rag.get_collection_stats()
for col, stat in stats.items():
    print(f"{col}: {stat['doc_count']} docs")
```

## 6. Error Handling

```python
# BaseAgent handles errors gracefully
agent = LeaveAgent(llm)

try:
    result = agent.run(
        query="My PTO question",
        user_context={"user_id": "emp123"}
    )
    
    # Check for failures
    if not result["answer"]:
        print("No answer generated")
    
    if result["confidence"] < 0.5:
        print("Low confidence answer")
    
    print(f"Success: {result['answer']}")
    
except Exception as e:
    print(f"Agent failed: {e}")

# RAG handles missing collections
rag = RAGPipeline()

results = rag.search(
    query="...",
    collection="nonexistent"  # Falls back to default
)
# Returns empty list, no exception
```

## 7. Debugging & Monitoring

```python
# Get reasoning trace from agent execution
result = agent.run(query="...", user_context=...)

print("Execution Trace:")
for trace_item in result["reasoning_trace"]:
    print(f"  → {trace_item}")

print(f"Tools used: {result['tools_used']}")
print(f"Confidence: {result['confidence']:.2f}")
print(f"Sources: {result['sources']}")

# Check RAG health
rag = RAGPipeline()
if not rag.health_check():
    print("RAG system unhealthy!")
else:
    print("RAG operational")

# List all documents
docs = rag.list_documents()
for doc in docs:
    print(f"  {doc['doc_id']}: {doc['metadata']}")
```

## 8. Configuration

### BaseAgent Max Iterations

```python
# Limit iterations to 3 (default is 5)
result = agent.run(
    query="...",
    user_context=...,
    max_iterations=3
)
```

### RAG Backend Selection

```python
# Force ChromaDB (will fail if not installed)
rag = RAGPipeline(use_chromadb=True)

# Force in-memory (no persistence)
rag = RAGPipeline(use_chromadb=False)

# Auto-select (tries ChromaDB, falls back to in-memory)
rag = RAGPipeline(use_chromadb=True)  # Default
```

### RAG Collection Switching

```python
rag = RAGPipeline()

# Switch collections
rag.search(query, collection="hr_policies")
rag.search(query, collection="employee_handbook")
rag.search(query, collection="compliance_docs")
rag.search(query, collection="benefits_guides")
```

### RAG Similarity Thresholds

```python
rag = RAGPipeline()

# Strict matching (high threshold)
results = rag.search(query, min_score=0.8, top_k=3)

# Loose matching (low threshold)
results = rag.search(query, min_score=0.3, top_k=10)
```

## 9. Integration Checklist

- [ ] Implement all specialist agents extending BaseAgent
- [ ] Register agents in RouterAgent.AGENT_REGISTRY
- [ ] Create RAGPipeline instance for document collections
- [ ] Ingest all HR documents into RAG
- [ ] Test intent classification
- [ ] Test permission checking
- [ ] Test agent dispatch
- [ ] Test multi-agent orchestration
- [ ] Monitor confidence scores
- [ ] Set up logging aggregation

## 10. Troubleshooting

**Q: Agent returns low confidence**
A: Check tool results quality, verify RAG documents are indexed

**Q: Router dispatches to wrong agent**
A: Add more keywords to INTENT_CATEGORIES for that intent

**Q: RAG search returns no results**
A: Lower min_score threshold, verify documents are ingested

**Q: ChromaDB connection fails**
A: Check /chromadb_hr directory exists, falls back to in-memory automatically

**Q: Agent takes too long**
A: Reduce max_iterations, limit tool count, check LLM latency

---

## Files Reference

- `src/agents/__init__.py` - Package exports
- `src/agents/base_agent.py` - BaseAgent class
- `src/agents/router_agent.py` - RouterAgent class
- `src/core/rag_pipeline.py` - RAGPipeline class

All files include comprehensive docstrings and type hints.

# Router Agent and RAG Migration - Implementation Complete

## Overview

Successfully created three core modules for the HR multi-agent platform:

1. **Base Agent Framework** (`src/agents/base_agent.py`) - Abstract base class for all specialist agents
2. **Router Agent** (`src/agents/router_agent.py`) - Supervisor/dispatcher for multi-agent orchestration  
3. **RAG Pipeline** (`src/core/rag_pipeline.py`) - Document retrieval and semantic search system

All modules feature:
- Full type hints and docstrings
- Production-ready error handling
- Comprehensive logging
- Support for fallback implementations

---

## 1. Base Agent Framework (`src/agents/base_agent.py`)

### Purpose
Provides abstract base class for all specialist agents using LangGraph-style execution pattern.

### Key Classes

#### `BaseAgentState` (TypedDict)
Complete state passed between graph nodes:

**Input Fields:**
- `query: str` - User question/request
- `topic: Optional[str]` - Context topic
- `user_context: UserContext` - User info (id, role, department, permissions)

**Planning Fields:**
- `plan: List[str]` - Execution steps (1-4 steps)
- `current_step: int` - Current position in plan

**Execution Fields:**
- `tool_calls: List[Dict]` - History of tool invocations
- `tool_results: Dict[str, Any]` - Results per tool name

**Reflection Fields:**
- `confidence_score: float` - Answer quality (0.0-1.0)
- `force_next_tool: Optional[str]` - Override tool selection
- `iterations: int` - Execution count
- `max_iterations: int` - Execution limit

**Output Fields:**
- `final_answer: str` - Synthesized response
- `sources_used: List[str]` - Source references
- `reasoning_trace: List[str]` - Execution trace for debugging

#### `UserContext` (TypedDict)
User information for authorization and personalization:
```python
user_id: str        # Employee ID
role: str           # "employee", "manager", "hr_generalist", "hr_admin"
department: str     # Department name
can_view_all: bool  # Data access scope
can_modify: bool    # Write permission
```

#### `BaseAgent` (ABC)
Abstract class for specialist agents with LangGraph execution pattern.

**Required Implementation (Abstract Methods):**
```python
def get_tools() -> Dict[str, Any]
    """Return available tools dict"""
    
def get_system_prompt() -> str
    """Return system context for LLM"""
    
def get_agent_type() -> str
    """Return agent identifier (e.g., "policy_agent")"""
```

**Graph Structure (5 Nodes):**

```
Entry: planner
  ↓
planner: Analyze query, create 1-4 step plan
  ↓
decide_tool: Select next tool from plan
  ├→ execute (if steps remain)
  └→ finish (if plan done)
       ↓
execute_tool: Run selected tool, capture results
  ↓
reflect: Assess quality, decide iteration
  ├→ continue (more steps or forced tool)
  └→ finish (sufficient info)
       ↓
finish: Synthesize final answer
  ↓
Output (answer, sources, confidence, trace)
```

**Node Implementations:**

1. **_plan_node**: Uses LLM to create minimal execution plan
   - Analyzes query and available tools
   - Returns plan with 1-4 steps max
   - Stores reasoning in trace

2. **_decide_tool_node**: Selects next tool
   - Checks forced tool first (quality override)
   - Extracts tool from current plan step
   - Handles plan completion

3. **_execute_tool_node**: Runs selected tool
   - Calls tool.invoke(query)
   - Stores result and metadata
   - Increments iteration counter
   - Logs success/failure

4. **_reflect_node**: Quality assessment
   - Uses LLM to evaluate information completeness
   - Scores confidence (0.0-1.0)
   - May set forced tool for fallback
   - Clears forced tool to prevent loops

5. **_finish_node**: Answer synthesis
   - Uses LLM to synthesize final answer
   - Extracts source references
   - Handles missing information gracefully

**Conditional Edges:**

- `_should_continue()`: Execute → Finish
  - Finish if: plan complete OR max iterations reached
  - Execute otherwise

- `_should_iterate()`: Continue → Finish
  - Continue if: plan incomplete OR forced tool set
  - Finish if: max iterations OR no more steps

**Public Interface:**
```python
def run(
    query: str,
    user_context: Optional[UserContext] = None,
    topic: Optional[str] = None,
    max_iterations: int = 5,
) -> Dict[str, Any]
```

Returns:
- `answer`: Final synthesized response
- `sources`: List of source references
- `confidence`: Score (0.0-1.0)
- `tools_used`: List of tools invoked
- `reasoning_trace`: Execution trace
- `agent_type`: Agent identifier

**Helper Methods:**

- `_extract_tool_from_step()`: Parse tool name from plan step
- `_format_tool_descriptions()`: Generate tool list for prompts
- `_extract_sources()`: Collect sources from tool results
- `_parse_json_response()`: Extract JSON from LLM response

---

## 2. Router Agent (`src/agents/router_agent.py`) - CORE-001

### Purpose
Supervisor agent that classifies queries, checks permissions, and dispatches to specialist agents.

### Architecture

**NOT extending BaseAgent** - Router is a coordinator, not a specialist.

#### `RouterState` (TypedDict)
State for routing decisions:

**Input:**
- `query: str` - User query
- `user_context: Dict[str, Any]` - User info
- `conversation_history: List[Dict]` - Prior context

**Classification:**
- `intent: str` - Classified intent category
- `confidence: float` - Classification confidence (0.0-1.0)
- `target_agents: List[str]` - Agents to dispatch to
- `requires_clarification: bool` - Ambiguous query?
- `clarification_question: Optional[str]` - Follow-up question

**Execution:**
- `agent_results: List[Dict]` - Results from specialist agents

**Output:**
- `final_response: Dict[str, Any]` - Merged response

#### Intent Categories & Registry

```python
INTENT_CATEGORIES = {
    "employee_info": ["who is", "employee profile", "contact", ...],
    "policy": ["policy", "procedure", "compliance", ...],
    "leave": ["leave", "vacation", "pto", ...],
    "onboarding": ["onboarding", "new hire", ...],
    "benefits": ["benefits", "health", "insurance", ...],
    "performance": ["performance", "review", "goal", ...],
    "analytics": ["report", "analytics", "dashboard", ...],
}

AGENT_REGISTRY = {
    "employee_info": "EmployeeInfoAgent",
    "policy": "PolicyAgent",
    "leave": "LeaveAgent",
    "onboarding": "OnboardingAgent",
    "benefits": "BenefitsAgent",
    "performance": "PerformanceAgent",
    "analytics": "AnalyticsAgent",
}
```

### Core Methods

#### `classify_intent(query: str) -> tuple[str, float]`

Fast, two-stage intent classification:

**Stage 1: Keyword Matching**
- Checks query against keywords per intent
- Returns immediately if clear match (confidence=0.9)
- Efficient for common queries

**Stage 2: LLM Classification** (for ambiguous queries)
- Uses LLM for complex/multi-intent queries
- Returns intent with confidence score
- Falls back to "unclear" if LLM fails

**Returns:** `(intent, confidence)` tuple

#### `check_permissions(user_context: Dict, intent: str) -> bool`

RBAC permission checking:

**Permission Matrix:**
- employee_info: employee, manager, hr_generalist
- policy: employee, manager, hr_generalist
- leave: employee, manager, hr_generalist
- onboarding: manager, hr_generalist, hr_admin
- benefits: employee, manager, hr_generalist
- performance: manager, hr_generalist, hr_admin
- analytics: manager, hr_generalist, hr_admin

**Returns:** `True` if user's role allowed for intent, `False` otherwise

#### `dispatch_to_agent(intent: str, query: str, user_context: Dict) -> Dict`

Dispatch to specialist agent:

1. Look up agent in AGENT_REGISTRY
2. Instantiate if not cached
3. Run agent with query and user_context
4. Return agent result

**Returns:** Agent result dict with answer, confidence, sources, etc.

#### `handle_multi_intent(intents: List[tuple], query: str, user_context: Dict) -> List[Dict]`

Handle queries spanning multiple intents:

1. Check permission for each intent (skip if denied)
2. Dispatch to each agent in parallel
3. Collect all results
4. Return list of agent results

#### `merge_responses(results: List[Dict]) -> Dict`

Merge multi-agent results:

1. Combine answers with numbered list
2. Deduplicate sources
3. Average confidence scores
4. Return unified response

### Public Interface

```python
def run(
    query: str,
    user_context: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict]] = None,
) -> Dict[str, Any]
```

**Returns:**
- `answer`: Final response
- `sources`: Source references
- `agent_type`: "router"
- `confidence`: Overall confidence
- `intents`: List of (intent, confidence) tuples
- `agents_used`: Names of specialist agents invoked
- `requires_clarification`: Boolean flag
- `clarification_question`: If ambiguous

### Error Handling

- Falls back gracefully when agents unavailable
- Returns permission denial messages clearly
- Handles LLM failures with sensible defaults
- Logs all decisions for debugging

---

## 3. RAG Pipeline (`src/core/rag_pipeline.py`) - CORE-003

### Purpose
Retrieval-Augmented Generation system for semantic search over HR documents.

### Architecture

#### Collections

Four default collections managed by RAGPipeline:

1. **hr_policies** - Company HR policies and procedures
2. **employee_handbook** - Employee handbook and guidelines
3. **compliance_docs** - Legal and compliance documents
4. **benefits_guides** - Benefits program documentation

#### `RAGResult` (Dataclass)

Result object from search:

```python
@dataclass
class RAGResult:
    content: str                    # Document text
    source: str                     # Source filename
    score: float                    # Similarity score (0.0-1.0)
    metadata: Dict[str, Any]        # Metadata dict
```

Metadata includes:
- `doc_title`: Document title
- `section`: Document section
- `page_number`: If applicable
- `doc_type`: Document type
- `last_updated`: Last update timestamp
- `source`: Source filename
- `file_path`: Full file path
- `chunk_index`: Chunk index in document

#### `InMemoryVectorStore` (Fallback)

Simple in-memory vector store for testing/fallback:

- Stores documents with embeddings
- Computes cosine similarity
- Supports add, search, delete, list operations
- Not recommended for production

#### `RAGPipeline` (Main Class)

RAG system supporting both ChromaDB and in-memory backends.

**Initialization:**
```python
RAGPipeline(
    collection_name="hr_policies",
    embedding_model="all-MiniLM-L6-v2",
    use_chromadb=True  # Falls back to in-memory if unavailable
)
```

**Features:**
- Automatic ChromaDB fallback to in-memory
- Lazy embedding model loading
- Multiple collection support
- Comprehensive error handling

### Core Methods

#### `search(query: str, collection: Optional[str], top_k: int, min_score: float) -> List[RAGResult]`

Semantic search over documents:

**Args:**
- `query`: Search text
- `collection`: Collection name (default: default collection)
- `top_k`: Number of results (default: 5)
- `min_score`: Minimum similarity threshold (default: 0.3)

**Returns:** Sorted list of RAGResult objects

**Workflow:**
1. Embed query text
2. Compute similarity with stored documents
3. Filter by min_score
4. Return top_k results sorted by score

#### `ingest_document(file_path: str, doc_type: str, metadata: Dict, collection: Optional[str]) -> int`

Ingest document into RAG system:

**Args:**
- `file_path`: Path to document (.txt, .md, .pdf)
- `doc_type`: Type (policy, handbook, compliance, benefit)
- `metadata`: Custom metadata dict
- `collection`: Target collection

**Returns:** Number of chunks created

**Workflow:**
1. Extract text from file
2. Split into overlapping chunks
3. Embed each chunk
4. Store in collection
5. Return chunk count

**Supported Formats:**
- `.txt` - Plain text files
- `.md` - Markdown files
- `.pdf` - PDF files (placeholder for future)

#### `_chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]`

Split text into overlapping chunks:

**Args:**
- `text`: Input text
- `chunk_size`: Characters per chunk (default: 512)
- `overlap`: Character overlap (default: 50)

**Returns:** List of text chunks

**Example:**
```
Text: "ABCDEFGHIJ..." (100 chars)
chunk_size=30, overlap=10

Chunk 1: "ABCDEFGHIJ...XYZ" (chars 0-30)
Chunk 2: "UVW...XYZ..." (chars 20-50)
Chunk 3: "...GHIJ..." (chars 40-70)
```

#### `_extract_text(file_path: str) -> str`

Extract text from file:

**Supports:**
- `.txt` - Direct read with UTF-8
- `.md` - Direct read with UTF-8  
- `.pdf` - Placeholder (returns placeholder text)

**Returns:** Extracted text string

#### `delete_document(doc_id: str, collection: Optional[str]) -> bool`

Delete document by ID:

**Args:**
- `doc_id`: Document identifier
- `collection`: Collection name

**Returns:** `True` if deleted, `False` otherwise

#### `list_documents(collection: Optional[str]) -> List[Dict]`

List documents in collection:

**Args:**
- `collection`: Collection name (all if None)

**Returns:** List of document metadata dicts with:
- `collection`: Collection name
- `doc_id`: Document ID
- `metadata`: Full metadata
- `content_length`: Text length

#### `get_collection_stats() -> Dict[str, Dict]`

Get statistics for all collections:

**Returns:** Dict mapping collection_name to stats:
```python
{
    "hr_policies": {
        "doc_count": 5,
        "chunk_count": 47,
        "backend": "chromadb"
    },
    ...
}
```

#### `health_check() -> bool`

Check RAG pipeline health:

**Returns:** `True` if system operational, `False` otherwise

**Checks:**
- Vector store accessibility
- Collection availability
- Embedding model functionality

### Backend Support

#### ChromaDB Backend (Default)

**When Available:**
- Uses PersistentClient for persistence
- Stores at `./chromadb_hr/`
- Enables true production deployment
- Cosine similarity in HNSW space

**Configuration:**
```python
chromadb.PersistentClient(
    path="./chromadb_hr",
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)
```

#### In-Memory Fallback

**When ChromaDB Unavailable:**
- Uses InMemoryVectorStore
- Suitable for testing and development
- Limited to session lifetime
- Pure Python implementation

**Automatic Selection:**
```python
RAGPipeline(use_chromadb=True)
# Tries ChromaDB, falls back to in-memory if needed
```

### Embedding Model

**Default:** `all-MiniLM-L6-v2`
- Sentence-Transformers model
- 384-dimensional embeddings
- Fast inference
- Good general-purpose model

**Alternative Models:**
- `all-mpnet-base-v2` (larger, more accurate)
- `multi-qa-MiniLM-L6-cos-v1` (QA-optimized)
- Custom models supported

### Error Handling

All methods include:
- Try-except blocks with logging
- Graceful fallbacks
- Clear error messages
- No silent failures

**Example:**
```python
try:
    results = rag.search("...", collection="hr_policies")
except Exception as e:
    logger.error(f"RAG: Search failed: {e}")
    # Returns empty list, not exception
    return []
```

---

## Integration Guide

### For Specialist Agents

Extend `BaseAgent`:

```python
from src.agents.base_agent import BaseAgent, UserContext

class PolicyAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm)
        self.rag = RAGPipeline(collection="hr_policies")
    
    def get_tools(self):
        return {
            "rag_search": RAGSearchTool(self.rag),
            "policy_checker": PolicyCheckerTool(),
        }
    
    def get_system_prompt(self):
        return "You are an HR policy expert..."
    
    def get_agent_type(self):
        return "policy_agent"
```

Run agent:
```python
result = policy_agent.run(
    query="What is the remote work policy?",
    user_context=UserContext(
        user_id="emp123",
        role="employee",
        department="engineering"
    )
)
# Returns: {
#     "answer": "...",
#     "sources": ["policy_doc.md"],
#     "confidence": 0.95,
#     "tools_used": ["rag_search"],
#     "reasoning_trace": [...],
#     "agent_type": "policy_agent"
# }
```

### For Multi-Agent Orchestration

Use Router Agent:

```python
from src.agents.router_agent import RouterAgent

router = RouterAgent(llm)

result = router.run(
    query="What's the PTO policy and my balance?",
    user_context={
        "user_id": "emp123",
        "role": "employee",
        "department": "sales"
    }
)
# Routes to both PolicyAgent (policy) and LeaveAgent (leave)
# Merges results into single response
```

### For RAG Usage

Use RAGPipeline directly:

```python
from src.core.rag_pipeline import RAGPipeline

rag = RAGPipeline(collection_name="hr_policies")

# Ingest documents
rag.ingest_document(
    "policies/remote_work.md",
    doc_type="policy",
    metadata={"last_updated": "2024-01-01"}
)

# Search
results = rag.search(
    "remote work from home",
    top_k=5,
    min_score=0.5
)

for result in results:
    print(f"{result.source}: {result.content[:200]}...")
    print(f"Score: {result.score}")
```

---

## File Locations

```
/sessions/beautiful-amazing-lamport/mnt/HR_agent/
├── src/
│   ├── agents/
│   │   ├── __init__.py              # Package initialization
│   │   ├── base_agent.py            # BaseAgent abstract class
│   │   └── router_agent.py          # RouterAgent supervisor
│   └── core/
│       └── rag_pipeline.py          # RAGPipeline for retrieval
```

## Code Statistics

- **base_agent.py**: 22 KB, ~700 lines
  - BaseAgentState: State TypedDict
  - UserContext: User info TypedDict
  - BaseAgent: Abstract base class with LangGraph pattern
  - 5 node implementations
  - 2 conditional edge functions
  - Helper methods and public interface

- **router_agent.py**: 19 KB, ~500 lines
  - RouterState: Routing state TypedDict
  - RouterAgent: Multi-agent supervisor
  - Intent classification with fallback
  - Permission checking via RBAC
  - Agent dispatch and caching
  - Response merging for multi-intent
  - Helper methods and public interface

- **rag_pipeline.py**: 23 KB, ~700 lines
  - RAGResult: Result dataclass
  - InMemoryVectorStore: Fallback implementation
  - RAGPipeline: Main RAG class
  - ChromaDB integration with auto-fallback
  - Document ingestion and chunking
  - Semantic search with scoring
  - Collection management
  - Health check utilities

**Total:** 64 KB, ~1,900 lines of production-ready code

---

## Testing Recommendations

### Unit Tests

```python
# Test BaseAgent
def test_base_agent_planning():
    """Test plan generation"""
    
def test_base_agent_tool_selection():
    """Test tool extraction from plan"""
    
def test_base_agent_graph_execution():
    """Test full agent execution graph"""

# Test RouterAgent
def test_router_classification():
    """Test intent classification"""
    
def test_router_permissions():
    """Test RBAC permission checking"""
    
def test_router_dispatch():
    """Test agent dispatch"""
    
def test_router_multi_intent():
    """Test multi-intent handling"""

# Test RAGPipeline
def test_rag_chunking():
    """Test text chunking"""
    
def test_rag_ingestion():
    """Test document ingestion"""
    
def test_rag_search():
    """Test semantic search"""
    
def test_rag_backend_fallback():
    """Test ChromaDB → in-memory fallback"""
```

### Integration Tests

- End-to-end agent execution
- Multi-agent orchestration via router
- RAG integration with agents
- Permission enforcement
- Error recovery and fallbacks

---

## Production Checklist

- [ ] Configure ChromaDB persistence path
- [ ] Load initial documents into RAG collections
- [ ] Implement all specialist agents extending BaseAgent
- [ ] Register agents in RouterAgent.AGENT_REGISTRY
- [ ] Test permission matrix with real user roles
- [ ] Set up logging aggregation
- [ ] Monitor token usage and costs
- [ ] Implement rate limiting
- [ ] Add prompt caching for common queries
- [ ] Set up alerting for failed agents
- [ ] Document custom specialist agents
- [ ] Test multi-intent scenarios
- [ ] Validate RAG chunk sizes for your documents
- [ ] Benchmark agent response times

---

## Future Enhancements

1. **Agent Improvements:**
   - Streaming output support
   - Long-context handling
   - Cross-agent communication
   - Persistent memory/context

2. **RAG Enhancements:**
   - Hybrid search (semantic + keyword)
   - Multi-modal documents (images, tables)
   - Document versioning
   - Fine-tuned embedding models
   - Query expansion

3. **Router Improvements:**
   - Confidence-based fallback chains
   - Agent affinity scoring
   - Load balancing
   - Circuit breaker pattern

4. **Observability:**
   - Detailed trace visualization
   - Cost tracking per agent
   - Performance benchmarks
   - Error analysis dashboard

---

## Summary

Three production-ready modules have been created:

✅ **BaseAgent** - Abstract pattern for 10+ specialist agents
✅ **RouterAgent** - Intent classification + permission checking + multi-agent dispatch
✅ **RAGPipeline** - Semantic search with ChromaDB + in-memory fallback

All modules feature:
- Complete type hints and docstrings
- LangGraph-style execution patterns
- Comprehensive error handling and logging
- Support for fallback implementations
- Permission-aware dispatch
- Multi-collection document management

Ready for integration with specialist agent implementations.


# src/agent/agent_state.py

from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    State passed between LangGraph nodes.
    Fields can be Annotated[...] with reducers (e.g., operator.add) so
    the graph knows how to merge updates.
    """

    # ----- Inputs -----
    query: str
    topic: str
    difficulty: str  # "beginner" | "intermediate" | "advanced"

    # ----- Planning -----
    plan: List[str]  # steps to execute
    current_step: int  # index into plan

    # ----- Execution -----
    # Use a list here so operator.add can concatenate message buffers.
    messages: Annotated[List[BaseMessage], operator.add]
    tool_calls: List[Dict[str, Any]]  # history of tool invocations
    tool_results: Dict[str, Any]  # latest results per tool name

    # ----- Reflection -----
    needs_more_info: bool
    confidence_score: float
    # Optional control flags & bookkeeping (preserve across nodes)
    force_next_tool: Optional[str] = None  # ← Add default None
    current_tool: Optional[str]
    iterations: Optional[int]
    max_iterations: Optional[int]
    query_type: Optional[str]
    primary_tool: Optional[str]

    # ----- Output -----
    final_answer: str
    sources_used: List[str]
    reasoning_trace: List[str]  # brief, user-safe trace

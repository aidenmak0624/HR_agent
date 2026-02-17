"""
Base Agent class for HR multi-agent platform.

This module defines the abstract base class and state for all specialist agents
using a LangGraph-style pattern inspired by the HRAssistantAgent architecture.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional, TypedDict
import logging
import json

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class UserContext(TypedDict, total=False):
    """User context information for authorization and personalization."""
    
    user_id: str
    role: str  # "employee", "manager", "hr_generalist", "hr_admin"
    department: str
    can_view_all: bool
    can_modify: bool


class BaseAgentState(TypedDict, total=False):
    """
    State passed between LangGraph nodes in BaseAgent workflow.
    
    Fields represent:
    - Input: query, user_context
    - Planning: plan, current_step
    - Execution: tool_calls, tool_results
    - Reflection: confidence_score, force_next_tool, iterations
    - Output: final_answer, sources_used, reasoning_trace
    """
    
    # --- Input ---
    query: str
    topic: Optional[str]
    user_context: UserContext
    
    # --- Planning ---
    plan: List[str]
    current_step: int
    
    # --- Execution ---
    tool_calls: List[Dict[str, Any]]
    tool_results: Dict[str, Any]
    
    # --- Reflection & Control ---
    confidence_score: float
    force_next_tool: Optional[str]
    iterations: int
    max_iterations: int
    
    # --- Output ---
    final_answer: str
    sources_used: List[str]
    reasoning_trace: List[str]


class BaseAgent(ABC):
    """
    Abstract base class for specialist agents in HR multi-agent platform.
    
    Uses LangGraph StateGraph pattern with 5 main nodes:
    1. _plan_node: Create execution plan from query
    2. _decide_tool_node: Select next tool from plan
    3. _execute_tool_node: Run selected tool
    4. _reflect_node: Assess quality and decide iteration
    5. _finish_node: Synthesize final answer
    
    Subclasses must implement:
    - get_tools() -> Dict[str, Any]: Return available tools
    - get_system_prompt() -> str: Return system context
    - get_agent_type() -> str: Return agent identifier
    """
    
    def __init__(self, llm: Any = None):
        """
        Initialize base agent.

        Args:
            llm: Language model instance (e.g., ChatOpenAI, ChatGoogleGenerativeAI).
                 If None, subclass must set self.llm in __init__.
        """
        self.llm = llm
        self.graph = self._build_graph()
    
    # ==================== Abstract Methods ====================
    
    @abstractmethod
    def get_tools(self) -> Dict[str, Any]:
        """
        Get tools available to this agent.
        
        Returns:
            Dict mapping tool name (str) to tool instance (Any).
            Example: {"rag_search": RAGSearchTool(), "web_search": WebSearchTool()}
        """
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get system prompt for this agent's LLM.
        
        Returns:
            System prompt describing the agent's role and capabilities.
        """
        pass
    
    @abstractmethod
    def get_agent_type(self) -> str:
        """
        Get unique identifier for this agent type.
        
        Returns:
            Agent type string (e.g., "policy_agent", "leave_agent").
        """
        pass
    
    # ==================== Graph Building ====================
    
    def _build_graph(self) -> Any:
        """
        Build LangGraph StateGraph with planning, execution, reflection pattern.
        
        Graph structure:
        - Entry: planner
        - planner -> decide_tool
        - decide_tool -> {execute_tool | finish} [conditional]
        - execute_tool -> reflect
        - reflect -> {decide_tool | finish} [conditional]
        - finish -> END
        
        Returns:
            Compiled StateGraph.
        """
        workflow = StateGraph(BaseAgentState)
        
        # Add nodes
        workflow.add_node("planner", self._plan_node)
        workflow.add_node("decide_tool", self._decide_tool_node)
        workflow.add_node("execute_tool", self._execute_tool_node)
        workflow.add_node("reflect", self._reflect_node)
        workflow.add_node("finish", self._finish_node)
        
        # Set entry point
        workflow.set_entry_point("planner")
        
        # Fixed edges
        workflow.add_edge("planner", "decide_tool")
        workflow.add_edge("execute_tool", "reflect")
        workflow.add_edge("finish", END)
        
        # Conditional edges
        workflow.add_conditional_edges(
            "decide_tool",
            self._should_continue,
            {"execute": "execute_tool", "finish": "finish"},
        )
        
        workflow.add_conditional_edges(
            "reflect",
            self._should_iterate,
            {"continue": "decide_tool", "finish": "finish"},
        )
        
        return workflow.compile()
    
    # ==================== Node Implementations ====================
    
    def _plan_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Create execution plan from query.
        
        Uses LLM to analyze query and create 1-4 step plan.
        
        Args:
            state: Current agent state
            
        Returns:
            State with plan, current_step=0, reasoning_trace updated
        """
        logger.info(f"PLAN: Analyzing query: {state.get('query', '')[:50]}...")

        # Graceful fallback when LLM is not available
        if self.llm is None:
            tools = self.get_tools()
            first_tool = list(tools.keys())[0] if tools else "default_tool"
            state["plan"] = [f"Use {first_tool} to answer query"]
            state["current_step"] = 0
            state.setdefault("reasoning_trace", []).append(
                f"PLAN: Fallback (no LLM) — using {first_tool}"
            )
            logger.info(f"Plan created (no LLM): 1 step using {first_tool}")
            return state

        tools_desc = self._format_tool_descriptions()

        planning_prompt = f"""You are a specialized HR agent. Analyze the query and create a MINIMAL plan.

QUERY: {state.get('query', '')}
AGENT TYPE: {self.get_agent_type()}

AVAILABLE TOOLS:
{tools_desc}

Create a plan with 1-4 steps to answer the query efficiently.

Return ONLY JSON:
{{
  "plan": ["Step 1: Use [TOOL] to [action]"],
  "reasoning": "Brief explanation",
  "expected_steps": 1
}}"""

        messages = [
            SystemMessage(content=self.get_system_prompt()),
            HumanMessage(content=planning_prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            raw = getattr(response, "content", str(response))
            logger.debug(f"PLAN raw response: {raw[:100]}...")

            # Try to parse JSON from response
            plan_data = self._parse_json_response(raw)

            state["plan"] = plan_data.get("plan", ["Use primary tool"])
            if len(state["plan"]) > 4:
                logger.warning(f"Plan has {len(state['plan'])} steps; capping at 4")
                state["plan"] = state["plan"][:4]

            state["current_step"] = 0
            reasoning = plan_data.get("reasoning", "No reasoning")
            state.setdefault("reasoning_trace", []).append(
                f"PLAN: {reasoning} | Steps: {len(state['plan'])}"
            )

            logger.info(f"Plan created: {len(state['plan'])} steps")

        except Exception as e:
            logger.error(f"Planning failed: {e}")
            state["plan"] = ["Use primary tool to answer query"]
            state["current_step"] = 0
            state.setdefault("reasoning_trace", []).append(
                f"PLAN: Fallback due to error: {e}"
            )

        return state
    
    def _decide_tool_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Select next tool based on plan or forced tool.
        
        Args:
            state: Current agent state
            
        Returns:
            State with force_next_tool or next_tool selected
        """
        logger.info(f"DECIDE: step {state.get('current_step')}/{len(state.get('plan', []))}")
        
        # Use forced tool if set
        if state.get("force_next_tool"):
            state["next_tool"] = state.get("force_next_tool")
            logger.info(f"DECIDE: Using forced tool: {state['next_tool']}")
            return state
        
        # Extract tool from plan
        current_step = state.get("current_step", 0)
        plan = state.get("plan", [])
        
        if current_step < len(plan):
            step = plan[current_step]
            tool_name = self._extract_tool_from_step(step)
            state["next_tool"] = tool_name
            logger.info(f"DECIDE: Selected tool from plan: {tool_name}")
        else:
            logger.info(f"DECIDE: Plan complete, no tool selected")
            state["next_tool"] = None
        
        return state
    
    def _execute_tool_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Execute the selected tool.

        Args:
            state: Current agent state (must have next_tool set)

        Returns:
            State with tool_results updated, iterations incremented
        """
        tool_name = state.get("next_tool")
        query = state.get("query", "")

        if not tool_name:
            logger.warning("EXECUTE: No tool selected")
            # Always advance step to prevent infinite loops
            state["current_step"] = state.get("current_step", 0) + 1
            state["iterations"] = state.get("iterations", 0) + 1
            return state

        tools = self.get_tools()
        if tool_name not in tools:
            logger.warning(f"EXECUTE: Tool '{tool_name}' not available")
            state.setdefault("reasoning_trace", []).append(
                f"EXECUTE: Tool '{tool_name}' not found"
            )
            # Always advance step to prevent infinite loops
            state["current_step"] = state.get("current_step", 0) + 1
            state["iterations"] = state.get("iterations", 0) + 1
            return state

        tool = tools[tool_name]
        logger.info(f"EXECUTE: Running {tool_name} for query: {query[:50]}...")

        try:
            # Call tool — support both callable functions and LangChain tools
            if callable(tool) and not hasattr(tool, "invoke"):
                result = tool(query)
            else:
                result = tool.invoke(query)
            state["tool_results"][tool_name] = result

            state["tool_calls"].append({
                "tool": tool_name,
                "query": query,
                "success": True,
            })

            state["current_step"] = state.get("current_step", 0) + 1
            state["iterations"] = state.get("iterations", 0) + 1

            logger.info(f"EXECUTE: {tool_name} completed in {state['iterations']} iteration(s)")

        except Exception as e:
            logger.error(f"EXECUTE: {tool_name} failed: {e}")
            state["tool_results"][tool_name] = {"error": str(e)}
            state["tool_calls"].append({
                "tool": tool_name,
                "query": query,
                "success": False,
                "error": str(e),
            })
            # Always advance step AND iterations to prevent infinite loops
            state["current_step"] = state.get("current_step", 0) + 1
            state["iterations"] = state.get("iterations", 0) + 1

        return state
    
    def _reflect_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Assess quality of current information and decide iteration strategy.
        
        May decide to:
        - Continue to next tool
        - Force a fallback tool
        - Finish (sufficient information)
        
        Args:
            state: Current agent state
            
        Returns:
            State with confidence_score, force_next_tool, reasoning_trace updated
        """
        logger.info(f"REFLECT: Assessing quality (iteration {state.get('iterations', 0)})")

        tool_results = state.get("tool_results", {})
        query = state.get("query", "")

        # Graceful fallback when LLM is not available
        if self.llm is None:
            has_results = any(
                isinstance(v, dict) and "error" not in v
                for v in tool_results.values()
            )
            state["confidence_score"] = 0.6 if has_results else 0.3
            state.setdefault("reasoning_trace", []).append(
                f"REFLECT: Fallback (no LLM) — confidence={state['confidence_score']}"
            )
            logger.info(f"REFLECT (no LLM): confidence={state['confidence_score']}")
            if "force_next_tool" in state:
                state["force_next_tool"] = None
            return state

        reflection_prompt = f"""Assess the quality of information gathered.

QUERY: {query}
TOOLS USED: {list(tool_results.keys())}
CURRENT INFORMATION:
{json.dumps(tool_results, indent=2)[:500]}

Return ONLY JSON:
{{
  "sufficient_info": true | false,
  "confidence": 0.0-1.0,
  "gaps": ["list of missing info"],
  "next_action": "finish" | "continue"
}}"""

        messages = [
            SystemMessage(content="You are a quality assessment expert."),
            HumanMessage(content=reflection_prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            raw = getattr(response, "content", str(response))
            reflection = self._parse_json_response(raw)

            confidence = float(reflection.get("confidence", 0.7))
            state["confidence_score"] = confidence

            state.setdefault("reasoning_trace", []).append(
                f"REFLECT: confidence={confidence}, gaps={reflection.get('gaps', [])}"
            )

            logger.info(f"REFLECT: confidence={confidence}")

        except Exception as e:
            logger.error(f"REFLECT: Assessment failed: {e}")
            state["confidence_score"] = 0.5
            state.setdefault("reasoning_trace", []).append(
                f"REFLECT: fallback due to {e}"
            )
        
        # Clear forced tool to prevent loops
        if "force_next_tool" in state:
            state["force_next_tool"] = None
        
        return state
    
    def _finish_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Synthesize final answer from accumulated tool results.
        
        Args:
            state: Current agent state
            
        Returns:
            State with final_answer, sources_used set
        """
        logger.info("FINISH: Synthesizing answer")

        tool_results = state.get("tool_results", {})
        query = state.get("query", "")

        # Graceful fallback when LLM is not available
        if self.llm is None:
            # Build a basic answer from raw tool results
            if tool_results:
                summary_parts = []
                for tool_name, result in tool_results.items():
                    if isinstance(result, dict) and "error" in result:
                        summary_parts.append(f"{tool_name}: {result['error']}")
                    else:
                        summary_parts.append(f"{tool_name}: {json.dumps(result)[:200]}")
                state["final_answer"] = (
                    f"Results for '{query}':\n" + "\n".join(summary_parts)
                )
            else:
                state["final_answer"] = (
                    f"I was unable to find information for: {query}. "
                    "Please try rephrasing or contact HR directly."
                )
            state["sources_used"] = self._extract_sources(tool_results)
            logger.info("FINISH (no LLM): Built answer from raw tool results")
            return state

        synthesis_prompt = f"""Synthesize a clear, helpful answer.

QUERY: {query}
INFORMATION GATHERED:
{json.dumps(tool_results, indent=2)[:1000]}

Provide a direct, concise answer based on the gathered information."""

        messages = [
            SystemMessage(content=self.get_system_prompt()),
            HumanMessage(content=synthesis_prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            state["final_answer"] = getattr(response, "content", str(response))
        except Exception as e:
            logger.error(f"FINISH: Synthesis failed: {e}")
            state["final_answer"] = f"Unable to generate answer: {e}"
        
        # Extract sources from tool results
        state["sources_used"] = self._extract_sources(tool_results)
        
        return state
    
    # ==================== Conditional Edges ====================
    
    def _should_continue(self, state: BaseAgentState) -> Literal["execute", "finish"]:
        """
        Decide whether to execute next tool or finish.
        
        Args:
            state: Current agent state
            
        Returns:
            "execute" if more plan steps remain and max iterations not reached,
            "finish" otherwise
        """
        current_step = state.get("current_step", 0)
        plan_length = len(state.get("plan", []))
        iterations = state.get("iterations", 0)
        max_iter = state.get("max_iterations", 5)
        
        logger.info(f"SHOULD_CONTINUE: step={current_step}/{plan_length}, iter={iterations}/{max_iter}")
        
        if current_step >= plan_length:
            logger.info("SHOULD_CONTINUE: Plan complete → finish")
            return "finish"
        if iterations >= max_iter:
            logger.info("SHOULD_CONTINUE: Max iterations → finish")
            return "finish"
        
        logger.info("SHOULD_CONTINUE: → execute next step")
        return "execute"
    
    def _should_iterate(self, state: BaseAgentState) -> Literal["continue", "finish"]:
        """
        Decide whether to iterate or finish after reflection.
        
        Args:
            state: Current agent state
            
        Returns:
            "continue" if more steps remain or forced tool set,
            "finish" otherwise
        """
        current_step = state.get("current_step", 0)
        plan_length = len(state.get("plan", []))
        iterations = state.get("iterations", 0)
        max_iter = state.get("max_iterations", 5)
        
        logger.info(f"SHOULD_ITERATE: step={current_step}/{plan_length}, iter={iterations}/{max_iter}")
        
        # Hard stop at max iterations
        if iterations >= max_iter:
            logger.info("SHOULD_ITERATE: Max iterations reached → finish")
            return "finish"
        
        # Check for forced tool (from quality check)
        if state.get("force_next_tool"):
            logger.info(f"SHOULD_ITERATE: Forced tool set → continue")
            return "continue"
        
        # Check if plan incomplete
        if current_step < plan_length:
            logger.info(f"SHOULD_ITERATE: Plan incomplete → continue")
            return "continue"
        
        logger.info("SHOULD_ITERATE: Plan complete → finish")
        return "finish"
    
    # ==================== Helper Methods ====================
    
    def _extract_tool_from_step(self, step: str) -> str:
        """
        Extract tool name from plan step string.
        
        Example:
            "Use rag_search to find policies" -> "rag_search"
        
        Args:
            step: Plan step string
            
        Returns:
            Tool name (string), or first tool if none found
        """
        tools = self.get_tools()
        step_lower = step.lower()
        
        # Check longest tool names first to avoid substring matching issues
        sorted_tools = sorted(tools.keys(), key=len, reverse=True)
        
        for tool_name in sorted_tools:
            if tool_name.lower() in step_lower:
                logger.info(f"EXTRACT: Found '{tool_name}' in step")
                return tool_name
        
        # Default to first tool
        default = list(tools.keys())[0] if tools else "default_tool"
        logger.warning(f"EXTRACT: No tool found in step, using {default}")
        return default
    
    def _format_tool_descriptions(self) -> str:
        """
        Format tool descriptions for LLM prompt.
        
        Returns:
            Formatted string of tool names and descriptions
        """
        lines = []
        for name, tool in self.get_tools().items():
            desc = getattr(tool, "description", name)
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)
    
    def _extract_sources(self, tool_results: Dict[str, Any]) -> List[str]:
        """
        Extract source references from tool results.
        
        Args:
            tool_results: Dict of tool_name -> result
            
        Returns:
            List of source strings
        """
        sources = []
        for _tool, result in tool_results.items():
            if isinstance(result, dict):
                if "sources" in result and isinstance(result["sources"], list):
                    sources.extend(result["sources"])
                if "source" in result:
                    sources.append(result["source"])
        return list({str(s) for s in sources})
    
    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response text.
        
        Handles responses with surrounding text by extracting JSON block.
        
        Args:
            text: Response text from LLM
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If no valid JSON found
        """
        import re
        
        # First try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON block
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"No valid JSON found in response: {text[:100]}")
    
    # ==================== Public Interface ====================
    
    def run(
        self,
        query: str,
        user_context: Optional[UserContext] = None,
        topic: Optional[str] = None,
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        """
        Run agent to answer query.
        
        Main entry point for executing agent workflow.
        
        Args:
            query: User question/request
            user_context: User info (id, role, department, etc.)
            topic: Optional topic/context for the query
            max_iterations: Max tool execution loops (default 5)
            
        Returns:
            Dict with keys:
            - answer: Final synthesized answer
            - sources: List of source references
            - confidence: Confidence score (0.0-1.0)
            - tools_used: List of tools invoked
            - reasoning_trace: Execution trace for debugging
            - agent_type: This agent's type
        """
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "department": "unknown",
            }
        
        initial_state: BaseAgentState = {
            "query": query,
            "topic": topic or self.get_agent_type(),
            "user_context": user_context,
            "plan": [],
            "current_step": 0,
            "tool_calls": [],
            "tool_results": {},
            "confidence_score": 0.0,
            "force_next_tool": None,
            "iterations": 0,
            "max_iterations": max_iterations,
            "final_answer": "",
            "sources_used": [],
            "reasoning_trace": [],
        }
        
        logger.info(f"RUN: Starting {self.get_agent_type()} for query: {query[:50]}...")

        # Build LangGraph config with optional tracing callbacks
        config: Dict[str, Any] = {}
        try:
            from src.core.tracing import LangSmithTracer
            callback = LangSmithTracer.create_callback(
                agent_name=self.get_agent_type(),
                correlation_id=user_context.get("user_id"),
            )
            config["callbacks"] = [callback]
        except Exception:
            callback = None

        try:
            config["recursion_limit"] = 50  # Safety net — prevent GraphRecursionError
            final_state = self.graph.invoke(initial_state, config=config)
        except Exception as e:
            logger.error(f"RUN: Graph execution failed: {e}")
            final_state = initial_state
            final_state["final_answer"] = f"Agent execution failed: {e}"

        # Log trace summary if callback was used
        if callback:
            summary = callback.get_trace_summary()
            logger.info(
                f"TRACE: {self.get_agent_type()} completed — "
                f"steps={summary['total_steps']} "
                f"llm_calls={summary['llm_calls']} "
                f"tool_calls={summary['tool_calls']} "
                f"elapsed={summary['elapsed_seconds']}s"
            )

        tools_used = [call["tool"] for call in final_state.get("tool_calls", [])]

        return {
            "answer": final_state.get("final_answer", ""),
            "sources": final_state.get("sources_used", []),
            "confidence": final_state.get("confidence_score", 0.0),
            "tools_used": tools_used,
            "reasoning_trace": final_state.get("reasoning_trace", []),
            "agent_type": self.get_agent_type(),
        }

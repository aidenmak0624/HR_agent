# src/agent/agent_brain.py

import os
from typing import Literal, Dict, Any, List
import json
import logging

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.agent_state import AgentState
from src.agent.tools.rag_tool import RAGSearchTool
from src.agent.tools.fact_checker import FactVerifierTool
from src.agent.tools.comparator import ComparatorTool
from src.agent.tools.planner import EducationalPlannerTool
from src.agent.tools.web_search_tool import WebSearchTool

# google.generativeai kept for RAG system compatibility

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _infer_content_type(query: str) -> str:
    """Infer educational content type from query."""
    query_lower = query.lower()
    if "quiz" in query_lower or "test" in query_lower:
        return "quiz"
    elif "study guide" in query_lower:
        return "study_guide"
    else:
        return "lesson_plan"  # default


def _extract_comparison_items(query: str) -> tuple:
    """
    Extract two items to compare from a comparison query.

    Examples:
        "Compare freedom of speech and freedom of expression"
        → ("freedom of speech", "freedom of expression")

        "What's the difference between UDHR and ICCPR?"
        → ("UDHR", "ICCPR")
    """
    query_lower = query.lower()

    # Try different comparison patterns
    separators = [" and ", " vs ", " versus ", " vs. ", " compared to ", " with "]

    for sep in separators:
        if sep in query_lower:
            # Split on the separator
            parts = query_lower.split(sep, 1)
            if len(parts) == 2:
                item_a = parts[0].strip()
                item_b = parts[1].strip()

                # Clean up common question words from the start
                remove_words = [
                    "compare",
                    "difference between",
                    "what's the",
                    "what is the",
                    "how does",
                    "how is",
                ]
                for word in remove_words:
                    if item_a.startswith(word):
                        item_a = item_a[len(word) :].strip()
                    if item_b.startswith(word):
                        item_b = item_b[len(word) :].strip()

                # Remove trailing punctuation
                item_a = item_a.rstrip("?,!.")
                item_b = item_b.rstrip("?,!.")

                if item_a and item_b:  # Make sure we have both items
                    return (item_a, item_b)

    # Fallback: split the query in half (comparator tool's LLM will handle it)
    words = query.split()
    mid = len(words) // 2
    item_a = " ".join(words[:mid])
    item_b = " ".join(words[mid:])
    return (item_a, item_b)


class HRAssistantAgent:
    """
    Main agent that orchestrates tools to answer HR policy and employment questions.
    Uses a simple ReAct-like loop wired as a LangGraph StateGraph.
    """

    def __init__(self, api_key: str):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=api_key,
            temperature=0.1,
        )
        self.tools: Dict[str, Any] = {
            "rag_search": RAGSearchTool(),
            "web_search": WebSearchTool(),
            "fact_verifier": FactVerifierTool(),
            "comparator": ComparatorTool(),
            "educational_planner": EducationalPlannerTool(),
        }
        self.graph = self._build_graph()

    # ---------- GRAPH ----------
    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("planner", self._plan_node)
        workflow.add_node("decide_tool", self._decide_tool_node)
        workflow.add_node("execute_tool", self._execute_tool_node)
        workflow.add_node("reflect", self._reflect_node)
        workflow.add_node("finish", self._finish_node)

        # Entry point
        workflow.set_entry_point("planner")

        # Fixed edges - NO DIRECT EDGES FROM decide_tool!
        workflow.add_edge("planner", "decide_tool")
        workflow.add_edge("execute_tool", "reflect")  # ✅ Execute always goes to reflect
        workflow.add_edge("finish", END)

        # Conditional edges
        workflow.add_conditional_edges(
            "decide_tool",
            self._should_continue,
            {"execute": "execute_tool", "finish": "finish"},  # ✅ Only these two paths
        )

        workflow.add_conditional_edges(
            "reflect",
            self._should_iterate,
            {"continue": "decide_tool", "finish": "finish"},
        )

        return workflow.compile()

    # ---------- NODES ----------
    def _plan_node(self, state: AgentState) -> AgentState:
        logger.info("PLAN: Analyzing query: %s", state.get("query"))

        planning_prompt = f"""You are an HR policy and employment expert. Analyze the query and create a MINIMAL plan.

    USER QUERY: {state.get('query','')}
    TOPIC: {state.get('topic','')}
    DIFFICULTY: {state.get('difficulty','intermediate')}

    AVAILABLE TOOLS:
    - rag_search: Search local HR knowledge base (policies, benefits, employment law)
    - web_search: Search the internet for current/external HR information
    - educational_planner: Create training materials, onboarding guides, HR curriculum
    - comparator: Compare HR policies, benefits plans, or employment regulations
    - fact_verifier: Verify specific claims about employment law or company policies

    QUERY TYPE GUIDELINES:
    1. **Simple search queries** (e.g., "What is X?", "How many days?", "What is the policy?")
    → Use 1 tool only: web_search (for current events/regulations) OR rag_search (for HR policies and benefits)

    2. **Creation requests** (e.g., "Create a lesson plan", "Make a quiz", "Design curriculum")
    → Use educational_planner only (1 step)

    3. **Comparison requests** (e.g., "Compare X and Y", "What's the difference between...")
    → Use comparator only (1 step)

    4. **Verification requests** (e.g., "Is it true that...", "Verify that...")
    → Use fact_verifier only (1 step)

    5. **Complex analysis** (e.g., "Analyze X in context of Y", "Deep dive into...")
    → Use 2-3 tools: Start with search (rag_search/web_search), then analysis tools

    IMPORTANT:
    - Keep plans SHORT (1-2 steps for most queries, max 3-4 for complex ones)
    - Don't chain tools unnecessarily (e.g., web_search → fact_verifier is redundant for simple queries)
    - Only suggest multiple tools if they serve DIFFERENT purposes

    Return ONLY JSON:
    {{
    "plan": [
        "Step 1: Use [TOOL] to [specific action]"
    ],
    "reasoning": "Brief explanation of why this plan",
    "query_type": "simple_search|creation|comparison|verification|complex_analysis",
    "primary_tool": "tool_name",
    "expected_steps": 1
    }}"""

        messages = [
            SystemMessage(
                content="You are a planning expert for HR policy questions. Create MINIMAL, efficient plans."
            ),
            HumanMessage(content=planning_prompt),
        ]

        def _parse_plan_response(resp_text: str):
            import re, json

            if not resp_text:
                raise ValueError("empty response")
            try:
                return json.loads(resp_text)
            except Exception:
                m = re.search(r"(\{(?:.|\n)*\})", resp_text)
                if m:
                    try:
                        return json.loads(m.group(1))
                    except Exception:
                        pass
                raise

        try:
            response = self.llm.invoke(messages)
            raw = getattr(response, "content", str(response))
            logger.debug("PLAN raw response: %s", raw)

            try:
                plan_data = _parse_plan_response(raw)
            except Exception:
                logger.warning("Planning parse failed, retrying LLM once")
                response = self.llm.invoke(messages)
                raw = getattr(response, "content", str(response))
                logger.debug("PLAN retry raw response: %s", raw)
                plan_data = _parse_plan_response(raw)

            # Get the plan
            state["plan"] = plan_data.get("plan", ["Use rag_search to find information"])

            # ✅ Cap at 4 steps but warn if plan is too long
            if len(state["plan"]) > 4:
                logger.warning(f"Plan has {len(state['plan'])} steps; capping at 4")
                state["plan"] = state["plan"][:4]

            state["query_type"] = plan_data.get("query_type", "simple_search")
            state["primary_tool"] = plan_data.get("primary_tool", "rag_search")
            state["current_step"] = 0

            # Add reasoning to trace
            reasoning = plan_data.get("reasoning", "No reasoning provided")
            state.setdefault("reasoning_trace", []).append(
                f"PLAN: {reasoning} | Type: {state['query_type']} | Steps: {len(state['plan'])}"
            )

            logger.info(
                "Plan created: %d steps (type=%s, primary=%s)",
                len(state["plan"]),
                state["query_type"],
                state["primary_tool"],
            )

        except Exception as e:
            logger.error("Planning failed: %s", e)
            state.setdefault("reasoning_trace", []).append(
                f"PLAN: fallback due to planning error: {e}"
            )
            state["plan"] = ["Use rag_search to search documents"]
            state["query_type"] = "simple_search"
            state["primary_tool"] = "rag_search"
            state["current_step"] = 0

        return state

    # Fixed Functions for agent_brain.py

    # ========== FIX #1: Tool Name Extraction ==========
    def _extract_tool_from_plan_step(self, step: str) -> str:
        """
        Extract tool name from plan step like 'Use comparator to compare X'

        IMPORTANT: Check in order of specificity (longest names first) to avoid
        substring matching issues (e.g., "web_search" contains "search" which
        would incorrectly match "rag_search" if checked first)
        """
        step_lower = step.lower()

        # ✅ Ordered by specificity - longer/more specific names first
        tools_list = [
            "educational_planner",  # Most specific
            "fact_verifier",
            "comparator",
            "web_search",  # Check before rag_search!
            "rag_search",  # Generic "search" - check last
        ]

        for tool in tools_list:
            if tool in step_lower:
                logger.info(f"EXTRACT: Found '{tool}' in step: '{step[:50]}...'")
                return tool

        logger.warning(f"EXTRACT: No tool found in step '{step[:50]}...', defaulting to rag_search")
        return "rag_search"  # default fallback

    # ========== FIX #2: Enhanced Decide Tool with Better Logging ==========
    def _decide_tool_node(self, state: AgentState) -> AgentState:
        logger.info("=" * 60)
        logger.info("DECIDE: Entering decision node")
        logger.info(
            f"DECIDE: current_step={state.get('current_step')}/{len(state.get('plan', []))}"
        )
        logger.info(f"DECIDE: force_next_tool={state.get('force_next_tool')}")
        logger.info(f"DECIDE: plan={state.get('plan')}")
        logger.info("=" * 60)

        # Handle forced tool (from quality check)
        if "force_next_tool" in state and state.get("force_next_tool") is not None:
            forced_tool = state.get("force_next_tool")
            logger.info(f"DECIDE: 🔒 FORCED TOOL: {forced_tool}")

            # Generate appropriate input for the forced tool
            if forced_tool == "web_search":
                tool_input = {"query": state.get("query", "")}
            elif forced_tool == "rag_search":
                tool_input = {
                    "query": state.get("query", ""),
                    "topic": state.get("topic", "benefits"),
                    "top_k": 6,
                }
            elif forced_tool == "educational_planner":
                tool_input = {
                    "content_type": _infer_content_type(state.get("query", "")),
                    "topic": state.get("topic", "benefits"),
                    "level": state.get("difficulty", "intermediate"),
                }

            elif forced_tool == "comparator":
                query = state.get("query", "")
                item_a, item_b = _extract_comparison_items(query)
                tool_input = {
                    "item_a": item_a,
                    "item_b": item_b,
                    "topic": state.get("topic", "benefits"),
                    "comparison_type": "general",
                }

            elif forced_tool == "fact_verifier":
                tool_input = {
                    "claim": state.get("query", ""),
                    "topic": state.get("topic", "benefits"),
                }

            state["current_tool"] = forced_tool
            state.setdefault("tool_calls", []).append(
                {
                    "tool": forced_tool,
                    "tool_input": tool_input,
                    "reasoning": "Forced by quality threshold check",
                }
            )
            state.setdefault("reasoning_trace", []).append(
                f"FORCED TOOL: Using {forced_tool} due to quality check"
            )
            del state["force_next_tool"]
            logger.info(
                f"DECIDE: ✅ Forced tool setup complete. Tool calls: {len(state.get('tool_calls', []))}"
            )
            return state

        # Check if plan is complete
        if state.get("current_step", 0) >= len(state.get("plan", [])):
            logger.info("DECIDE: ⚠️ current_step >= plan length; nothing to execute")
            state["needs_more_info"] = False
            return state

        # Get current plan step
        current_plan_step = state["plan"][state["current_step"]]
        logger.info(f"DECIDE: 📋 Current plan step [{state['current_step']}]: '{current_plan_step}'")

        # Extract suggested tool from plan
        suggested_tool = self._extract_tool_from_plan_step(current_plan_step)
        logger.info(f"DECIDE: 🔍 Extracted tool from plan: '{suggested_tool}'")

        # If suggested tool is NOT rag_search, use it directly (don't ask LLM)
        if suggested_tool != "rag_search":
            logger.info(f"DECIDE: 🎯 Using plan-suggested tool '{suggested_tool}' directly")

            # ✅ Generate appropriate input for each tool based on its signature
            if suggested_tool == "web_search":
                tool_input = {"query": state.get("query", "")}

            elif suggested_tool == "educational_planner":
                tool_input = {
                    "content_type": _infer_content_type(state.get("query", "")),
                    "topic": state.get("topic", "benefits"),
                    "level": state.get("difficulty", "intermediate"),
                }

            elif suggested_tool == "comparator":
                # Extract two items to compare from query
                query = state.get("query", "")
                item_a, item_b = _extract_comparison_items(query)
                tool_input = {
                    "item_a": item_a,
                    "item_b": item_b,
                    "topic": state.get("topic", "benefits"),
                    "comparison_type": "general",
                }

            elif suggested_tool == "fact_verifier":
                tool_input = {
                    "claim": state.get("query", ""),
                    "topic": state.get("topic", "benefits"),
                }

            else:
                # Fallback for any other tools
                tool_input = {"query": state.get("query", "")}

            logger.info(f"DECIDE: 📦 Prepared tool_input: {tool_input}")

            state["current_tool"] = suggested_tool
            state.setdefault("tool_calls", []).append(
                {
                    "tool": suggested_tool,
                    "tool_input": tool_input,
                    "reasoning": f"Plan step explicitly suggests {suggested_tool}",
                }
            )
            state.setdefault("reasoning_trace", []).append(
                f"DECISION: Using plan-suggested tool {suggested_tool}"
            )

            logger.info(
                f"DECIDE: ✅ Tool setup complete. Total tool_calls: {len(state['tool_calls'])}"
            )
            logger.info(f"DECIDE: current_tool set to: '{state['current_tool']}'")
            return state

        # Only reach here for rag_search vs web_search decisions
        logger.info("DECIDE: 🤔 Asking LLM to choose between rag_search and web_search")

        recent_results = self._get_recent_results(state)
        decision_prompt = f"""
    You are executing this step: "{current_plan_step}"

    CONTEXT:
    Query: {state.get('query','')}
    Previous results:
    {recent_results}

    Choose between rag_search (local documents) or web_search (internet).
    Return ONLY JSON:
    {{
    "tool": "rag_search|web_search",
    "tool_input": {{"query": "..."}},
    "reasoning": "short why"
    }}"""

        messages = [
            SystemMessage(content="You are a tool selection expert."),
            HumanMessage(content=decision_prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            decision = json.loads(response.content)
            tool = decision.get("tool", "rag_search")
            tool_input = decision.get("tool_input", {"query": state.get("query", "")})
            reasoning = decision.get("reasoning", "")

            logger.info(f"DECIDE: 🤖 LLM chose: {tool} | Reasoning: {reasoning}")

            state["current_tool"] = tool
            state.setdefault("tool_calls", []).append(
                {"tool": tool, "tool_input": tool_input, "reasoning": reasoning}
            )
            state.setdefault("reasoning_trace", []).append(f"DECISION: {reasoning}")

            logger.info(
                f"DECIDE: ✅ Tool setup complete. Total tool_calls: {len(state['tool_calls'])}"
            )

        except Exception as e:
            logger.error(f"DECIDE: ❌ LLM decision failed: {e}")
            state["current_tool"] = "rag_search"
            state.setdefault("tool_calls", []).append(
                {
                    "tool": "rag_search",
                    "tool_input": {"query": state.get("query", "")},
                    "reasoning": "fallback due to error",
                }
            )

        return state

    # ========== FIX #3: Enhanced Execute Tool with Validation ==========
    def _execute_tool_node(self, state: AgentState) -> AgentState:
        logger.info("=" * 60)
        logger.info("EXECUTE: Entering execution node")

        # ✅ Validate tool_calls exists
        if not state.get("tool_calls"):
            logger.error("EXECUTE: ❌ No tool_calls found in state! Cannot execute.")
            logger.error(f"EXECUTE: State keys: {list(state.keys())}")
            return state

        last_call = state["tool_calls"][-1]
        tool_name = last_call.get("tool", "rag_search")
        tool_input = last_call.get("tool_input", {})
        reasoning = last_call.get("reasoning", "")

        logger.info(f"EXECUTE: 🔧 Tool: {tool_name}")
        logger.info(f"EXECUTE: 📦 Input: {tool_input}")
        logger.info(f"EXECUTE: 💭 Reasoning: {reasoning}")

        state["current_tool"] = tool_name

        # Execute the tool
        if tool_name in self.tools:
            try:
                logger.info(f"EXECUTE: ▶️ Running {tool_name}.run(**{tool_input})")
                result = self.tools[tool_name].run(**tool_input)
                logger.info(f"EXECUTE: ✅ Tool completed successfully")
                logger.info(f"EXECUTE: 📊 Result type: {type(result)}")
                if isinstance(result, dict):
                    logger.info(f"EXECUTE: 📊 Result keys: {list(result.keys())}")
            except Exception as e:
                logger.error(f"EXECUTE: ❌ Tool execution failed: {e}")
                logger.exception("Full traceback:")
                result = {"error": str(e)}
        else:
            logger.error(f"EXECUTE: ❌ Tool '{tool_name}' not found in available tools")
            logger.error(f"EXECUTE: Available tools: {list(self.tools.keys())}")
            result = {"error": f"Tool '{tool_name}' not found"}

        # Store result
        state.setdefault("tool_results", {})[tool_name] = result
        logger.info(f"EXECUTE: 💾 Stored result for {tool_name}")

        # Increment counters
        # ✅ Only increment step if this wasn't a forced tool
        if reasoning != "Forced by quality threshold check":
            old_step = state.get("current_step", 0)
            state["current_step"] = old_step + 1
            logger.info(
                f"EXECUTE: 📈 Incremented current_step: {old_step} → {state['current_step']}"
            )
        else:
            logger.info(f"EXECUTE: ⏸️ NOT incrementing current_step (forced tool)")

        old_iter = state.get("iterations", 0)
        state["iterations"] = old_iter + 1
        logger.info(f"EXECUTE: 📈 Incremented iterations: {old_iter} → {state['iterations']}")
        logger.info("=" * 60)

        return state

    def _reflect_node(self, state: AgentState) -> AgentState:
        logger.info("REFLECT: Starting reflection (iterations=%d)", state.get("iterations", 0))
        tool_results = state.get("tool_results", {})
        last_tool = list(tool_results.keys())[-1] if tool_results else ""

        logger.info(
            f"REFLECT: last_tool='{last_tool}', tool_results keys={list(tool_results.keys())}"
        )

        if last_tool == "rag_search" and "rag_search" in tool_results:
            rag_result = tool_results["rag_search"]
            is_sufficient = rag_result.get("is_sufficient", True)
            confidence = rag_result.get("confidence", 0.7)

            web_search_used = "web_search" in tool_results
            iterations = state.get("iterations", 0)
            max_iterations = state.get("max_iterations", 5)
            logger.info(
                f"REFLECT: RAG check — is_sufficient={is_sufficient}, "
                f"web_search_used={web_search_used}, "
                f"iterations={iterations}/{max_iterations}"
            )

            if (
                not is_sufficient
                and "web_search" not in tool_results
                and state.get("iterations", 0) < state.get("max_iterations", 5)
            ):
                state["needs_more_info"] = True
                state["confidence_score"] = confidence
                state.setdefault("reasoning_trace", []).append(
                    "DECISION: RAG quality insufficient → will try web search"
                )
                state["force_next_tool"] = "web_search"
                logger.info("REFLECT: ✅ Forcing web_search")
                return state

            logger.info(f"REFLECT: Not forcing — is_sufficient={is_sufficient}")

        logger.info("REFLECT: Using standard reflection (not forcing tool)")
        reflection_prompt = f"""
You've executed {state.get('iterations',0)} step(s).
ORIGINAL QUERY: {state.get('query','')}

TOOLS USED: {list(tool_results.keys())}

CURRENT INFORMATION:
{json.dumps(tool_results, indent=2)}

Return ONLY JSON:
{{
  "sufficient_info": true | false,
  "confidence": 0.0-1.0,
  "gaps": ["what's missing"],
  "next_action": "finish" | "continue"
}}"""

        messages = [
            SystemMessage(content="You are a quality control expert."),
            HumanMessage(content=reflection_prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            reflection = json.loads(response.content)
            state["needs_more_info"] = not bool(reflection.get("sufficient_info", True))
            state["confidence_score"] = float(reflection.get("confidence", 0.7))
            state.setdefault("reasoning_trace", []).append(
                f"REFLECTION: Confidence={state['confidence_score']}"
            )
        except Exception:
            state["needs_more_info"] = state.get("iterations", 0) < 1
            state["confidence_score"] = 0.7

        # ✅ CRITICAL: Set to None instead of del (LangGraph state mutation fix)
        if "force_next_tool" in state:
            logger.info("REFLECT: Clearing force_next_tool to prevent infinite loop")
            state["force_next_tool"] = None  # ← Change: set to None instead of del

        return state

    def _finish_node(self, state: AgentState) -> AgentState:
        synthesis_prompt = f"""
You are an HR policy expert. Synthesize a clear answer.

QUERY: {state.get('query','')}
LEVEL: {state.get('difficulty','intermediate')}

DATA:
{json.dumps(state.get('tool_results', {}), indent=2)}

TRACE:
{chr(10).join(state.get('reasoning_trace', []))}

Guidelines:
- Direct answer first
- Use tool information
- Cite sources if present
- Match difficulty level
"""
        messages = [
            SystemMessage(content="You are an HR policy and employment expert for TechNova Inc."),
            HumanMessage(content=synthesis_prompt),
        ]
        try:
            response = self.llm.invoke(messages)
            state["final_answer"] = response.content
        except Exception as e:
            state["final_answer"] = f"(fallback) Unable to synthesize answer: {e}"

        state["sources_used"] = self._extract_sources(state.get("tool_results", {}))
        return state

    # ---------- EDGES ----------
    def _should_continue(self, state: AgentState) -> Literal["execute", "finish"]:
        current_step = state.get("current_step", 0)
        plan_length = len(state.get("plan", []))
        iterations = state.get("iterations", 0)
        max_iter = state.get("max_iterations", 5)

        logger.info(
            f"SHOULD_CONTINUE: step={current_step}/{plan_length}, iter={iterations}/{max_iter}"
        )

        if current_step >= plan_length:
            logger.info("SHOULD_CONTINUE: Finishing (plan complete)")
            return "finish"
        if iterations >= max_iter:
            logger.info("SHOULD_CONTINUE: Finishing (max iterations)")
            return "finish"

        logger.info("SHOULD_CONTINUE: Executing")
        return "execute"

    def _should_iterate(self, state: AgentState) -> Literal["continue", "finish"]:
        # Hard stop at max iterations
        if state.get("iterations", 0) >= state.get("max_iterations", 5):
            logger.info(
                f"ITERATE: Hit max iterations ({state['iterations']}/{state['max_iterations']}); finishing"
            )
            return "finish"

        # ✅ Check for both presence AND non-None value
        if state.get("force_next_tool") and state.get("force_next_tool") is not None:
            logger.info(f"ITERATE: force_next_tool='{state['force_next_tool']}'; continuing")
            return "continue"

        # 🎯 FIX: Check if the plan is unfinished. If current_step < plan_length, continue.
        current_step = state.get("current_step", 0)
        plan_length = len(state.get("plan", []))

        if current_step < plan_length:
            logger.info(
                f"ITERATE: Plan is not complete (step {current_step} < {plan_length}); continuing"
            )
            return "continue"

        # Original condition for needs_more_info (usually after RAG, before web_search)
        if state.get("needs_more_info", False) and state.get("iterations", 0) < state.get(
            "max_iterations", 5
        ):
            logger.info(f"ITERATE: needs_more_info=True; continuing")
            return "continue"

        logger.info("ITERATE: Finishing")
        return "finish"

    # ---------- HELPERS ----------
    def _format_tool_descriptions(self) -> str:
        lines = []
        for name, tool in self.tools.items():
            desc = getattr(tool, "description", name)
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)

    def _get_recent_results(self, state: AgentState) -> str:
        tr = state.get("tool_results", {})
        if not tr:
            return "No results yet"
        summary = []
        for tool, result in list(tr.items())[-3:]:
            s = str(result)
            summary.append(f"{tool}: {s[:200]}{'...' if len(s)>200 else ''}")
        return "\n".join(summary)

    def _extract_sources(self, tool_results: dict) -> List[str]:
        sources = []
        for _tool, result in tool_results.items():
            if isinstance(result, dict):
                if "sources" in result and isinstance(result["sources"], list):
                    sources.extend(result["sources"])
                if "top_k" in result and isinstance(result["top_k"], list):
                    sources.extend(result["top_k"])
        return list({str(s) for s in sources})

    def _extract_tool_from_plan_step(self, step: str) -> str:
        """Extract tool name from plan step like 'Use comparator to compare X'"""
        step_lower = step.lower()
        tools_list = [
            "rag_search",
            "web_search",
            "fact_verifier",
            "comparator",
            "educational_planner",
        ]
        for tool in tools_list:
            if tool in step_lower:
                return tool
        return "rag_search"  # default fallback

    # ---------- PUBLIC ----------
    def run(self, query: str, topic: str, difficulty: str = "intermediate") -> dict:
        init: AgentState = {
            "query": query,
            "topic": topic,
            "difficulty": difficulty,
            "plan": [],
            "current_step": 0,
            "messages": [],
            "tool_calls": [],
            "tool_results": {},
            "needs_more_info": True,
            "confidence_score": 0.0,
            "final_answer": "",
            "sources_used": [],
            "reasoning_trace": [],
            "iterations": 0,
            "max_iterations": 5,
        }
        final_state = self.graph.invoke(init)
        return {
            "answer": final_state.get("final_answer", ""),
            "sources": final_state.get("sources_used", []),
            "reasoning_trace": final_state.get("reasoning_trace", []),
            "confidence": final_state.get("confidence_score", 0.0),
            "tools_used": [c["tool"] for c in final_state.get("tool_calls", [])],
        }

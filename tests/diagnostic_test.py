#!/usr/bin/env python3
"""
Diagnostic script to test LangGraph tool execution
Run this to identify where the execution is failing
"""

import sys
import logging
from typing import Dict, Any

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_tool_extraction():
    """Test if tool names are being extracted correctly from plan steps"""
    print("\n" + "=" * 60)
    print("TEST 1: Tool Name Extraction")
    print("=" * 60)

    test_cases = [
        ("Use web_search to search for current events", "web_search"),
        ("Use educational_planner to create lesson plan", "educational_planner"),
        ("Use rag_search to find information", "rag_search"),
        ("Use fact_verifier to verify claims", "fact_verifier"),
        ("Use comparator to compare two concepts", "comparator"),
        ("Search for information about free speech", "rag_search"),  # ambiguous
    ]

    # Old buggy version
    def extract_tool_buggy(step: str) -> str:
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
        return "rag_search"

    # Fixed version
    def extract_tool_fixed(step: str) -> str:
        step_lower = step.lower()
        tools_list = [
            "educational_planner",
            "fact_verifier",
            "comparator",
            "web_search",
            "rag_search",
        ]
        for tool in tools_list:
            if tool in step_lower:
                return tool
        return "rag_search"

    all_passed = True
    for step, expected in test_cases:
        buggy_result = extract_tool_buggy(step)
        fixed_result = extract_tool_fixed(step)

        buggy_correct = "✅" if buggy_result == expected else "❌"
        fixed_correct = "✅" if fixed_result == expected else "❌"

        print(f"\nStep: '{step[:50]}...'")
        print(f"  Expected:      {expected}")
        print(f"  Buggy version: {buggy_result} {buggy_correct}")
        print(f"  Fixed version: {fixed_result} {fixed_correct}")

        if buggy_result != expected:
            all_passed = False
            print(f"  ⚠️  ISSUE FOUND: Buggy extraction returning wrong tool!")

    if all_passed:
        print("\n✅ All tests passed - tool extraction is working correctly")
    else:
        print("\n❌ ISSUES FOUND - tool extraction has bugs!")

    return all_passed


def test_state_flow():
    """Test if state is flowing correctly through nodes"""
    print("\n" + "=" * 60)
    print("TEST 2: State Flow Simulation")
    print("=" * 60)

    # Simulate state after planning
    state = {
        "query": "Create a lesson plan about freedom of speech",
        "topic": "freedom_of_expression",
        "difficulty": "intermediate",
        "plan": [
            "Use educational_planner to create lesson plan",
            "Use rag_search to find supporting materials",
        ],
        "current_step": 0,
        "tool_calls": [],
        "tool_results": {},
        "iterations": 0,
        "max_iterations": 5,
    }

    print(f"\nInitial state:")
    print(f"  Plan: {state['plan']}")
    print(f"  Current step: {state['current_step']}")
    print(f"  Tool calls: {len(state['tool_calls'])}")

    # Simulate decide_tool_node
    print(f"\n--- Simulating decide_tool_node ---")
    current_plan_step = state["plan"][state["current_step"]]
    print(f"Current plan step: '{current_plan_step}'")

    # Extract tool (using fixed version)
    def extract_tool(step: str) -> str:
        step_lower = step.lower()
        tools_list = [
            "educational_planner",
            "fact_verifier",
            "comparator",
            "web_search",
            "rag_search",
        ]
        for tool in tools_list:
            if tool in step_lower:
                return tool
        return "rag_search"

    suggested_tool = extract_tool(current_plan_step)
    print(f"Extracted tool: '{suggested_tool}'")

    # Check if it would use the tool directly
    if suggested_tool != "rag_search":
        print(f"✅ Would use tool directly (not rag_search)")

        # Simulate tool setup
        if suggested_tool == "educational_planner":
            tool_input = {
                "query": state["query"],
                "topic": state["topic"],
                "difficulty": state["difficulty"],
            }
        else:
            tool_input = {"query": state["query"]}

        state["current_tool"] = suggested_tool
        state["tool_calls"].append(
            {
                "tool": suggested_tool,
                "tool_input": tool_input,
                "reasoning": f"Plan step explicitly suggests {suggested_tool}",
            }
        )

        print(f"✅ Tool setup complete:")
        print(f"  current_tool: {state['current_tool']}")
        print(f"  tool_calls length: {len(state['tool_calls'])}")
        print(f"  Last call: {state['tool_calls'][-1]}")
    else:
        print(f"⚠️  Would ask LLM to decide (suggested_tool is rag_search)")

    # Simulate should_continue check
    print(f"\n--- Simulating _should_continue ---")
    current_step = state.get("current_step", 0)
    plan_length = len(state.get("plan", []))
    iterations = state.get("iterations", 0)
    max_iter = state.get("max_iterations", 5)

    print(f"Current step: {current_step}/{plan_length}")
    print(f"Iterations: {iterations}/{max_iter}")

    if current_step >= plan_length:
        decision = "finish"
        print(f"Decision: {decision} (plan complete)")
    elif iterations >= max_iter:
        decision = "finish"
        print(f"Decision: {decision} (max iterations)")
    else:
        decision = "execute"
        print(f"✅ Decision: {decision} (should execute tool)")

    # Simulate execute_tool_node
    if decision == "execute" and state["tool_calls"]:
        print(f"\n--- Simulating _execute_tool_node ---")
        last_call = state["tool_calls"][-1]
        tool_name = last_call.get("tool")
        tool_input = last_call.get("tool_input")

        print(f"Would execute: {tool_name}")
        print(f"With input: {tool_input}")
        print(f"✅ Tool would be executed")

        # Simulate incrementing
        state["current_step"] += 1
        state["iterations"] += 1

        print(f"After execution:")
        print(f"  current_step: {state['current_step']}")
        print(f"  iterations: {state['iterations']}")
    else:
        print(
            f"\n❌ Would NOT execute (decision={decision}, tool_calls={len(state['tool_calls'])})"
        )


def test_tool_inputs():
    """Test if tool inputs match expected signatures"""
    print("\n" + "=" * 60)
    print("TEST 3: Tool Input Parameter Check")
    print("=" * 60)

    print("\n⚠️  MANUAL CHECK REQUIRED:")
    print("\nVerify your tool signatures match these expected inputs:\n")

    tools_expected = {
        "rag_search": "run(query: str, topic: str, top_k: int)",
        "web_search": "run(query: str, max_results: int)",
        "educational_planner": "run(query: str, topic: str, difficulty: str)",
        "comparator": "run(query: str)",
        "fact_verifier": "run(query: str)",
    }

    for tool, signature in tools_expected.items():
        print(f"  {tool}: {signature}")

    print("\n💡 Action items:")
    print("  1. Check each tool's actual run() method signature")
    print("  2. Update tool_input dictionaries in _decide_tool_node if needed")
    print("  3. Make sure all parameters are spelled correctly")


def main():
    print("\n" + "=" * 70)
    print(" LANGGRAPH DIAGNOSTIC TESTS")
    print("=" * 70)

    # Run all tests
    test1_passed = test_tool_extraction()
    test_state_flow()
    test_tool_inputs()

    print("\n" + "=" * 70)
    print(" SUMMARY")
    print("=" * 70)

    if not test1_passed:
        print("\n❌ ISSUE FOUND: Tool extraction is buggy!")
        print("   This is likely causing web_search/educational_planner to not execute.")
        print("   Fix: Reorder tools_list in _extract_tool_from_plan_step()")
        print("   See fixed_functions.py for corrected code.")
    else:
        print("\n✅ Tool extraction looks good")
        print("   If tools still aren't executing, check:")
        print("   1. Tool input parameters (see TEST 3)")
        print("   2. Add logging from fixed_functions.py")
        print("   3. Run your actual tests with DEBUG logging enabled")


if __name__ == "__main__":
    main()

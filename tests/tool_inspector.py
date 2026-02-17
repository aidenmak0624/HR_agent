#!/usr/bin/env python3
"""
Tool Signature Inspector
Automatically checks your tool signatures and generates correct tool_input code
"""

import inspect
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("\n" + "=" * 70)
print(" TOOL SIGNATURE INSPECTOR")
print("=" * 70)

try:
    from src.agent.tools.rag_tool import RAGSearchTool
    from src.agent.tools.fact_checker import FactVerifierTool
    from src.agent.tools.comparator import ComparatorTool
    from src.agent.tools.planner import EducationalPlannerTool
    from src.agent.tools.web_search_tool import WebSearchTool

    tools = {
        "rag_search": RAGSearchTool(),
        "web_search": WebSearchTool(),
        "fact_verifier": FactVerifierTool(),
        "comparator": ComparatorTool(),
        "educational_planner": EducationalPlannerTool(),
    }

    print("\n✅ Successfully imported all tools!\n")

    # Inspect each tool
    for tool_name, tool_instance in tools.items():
        print("-" * 70)
        print(f"🔧 Tool: {tool_name}")
        print("-" * 70)

        # Get the run method
        if hasattr(tool_instance, "run"):
            run_method = getattr(tool_instance, "run")
            sig = inspect.signature(run_method)

            # Get parameters (excluding 'self')
            params = []
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                # Get parameter details
                param_type = (
                    param.annotation if param.annotation != inspect.Parameter.empty else "Any"
                )
                param_default = (
                    param.default if param.default != inspect.Parameter.empty else "REQUIRED"
                )

                params.append({"name": param_name, "type": param_type, "default": param_default})

            # Print signature
            print(f"Signature: run(", end="")
            param_strs = []
            for p in params:
                if p["default"] == "REQUIRED":
                    param_strs.append(f"{p['name']}: {p['type']}")
                else:
                    param_strs.append(f"{p['name']}: {p['type']} = {p['default']}")
            print(", ".join(param_strs) + ")")

            # Generate tool_input code
            print("\n📦 Correct tool_input for _decide_tool_node:")
            print(f'if suggested_tool == "{tool_name}":')
            print(f"    tool_input = {{")
            for p in params:
                if p["name"] == "query":
                    print(f'        "{p["name"]}": state.get("query", ""),')
                elif p["name"] == "topic":
                    print(f'        "{p["name"]}": state.get("topic", "benefits"),')
                elif p["name"] == "difficulty":
                    print(f'        "{p["name"]}": state.get("difficulty", "detailed"),')
                elif p["default"] != "REQUIRED":
                    print(f'        "{p["name"]}": {p["default"]},')
                else:
                    print(f'        "{p["name"]}": state.get("{p["name"]}", ""),')
            print(f"    }}")
            print()

        else:
            print("❌ No run() method found!")
        print()

    # Generate complete code block
    print("=" * 70)
    print(" COMPLETE CODE FOR _decide_tool_node")
    print("=" * 70)
    print(
        """
# Replace this section in your _decide_tool_node function:

if suggested_tool != "rag_search":
    logger.info(f"DECIDE: Using plan-suggested tool '{suggested_tool}' directly")
    
    # ✅ CORRECTED TOOL INPUTS:"""
    )

    for tool_name, tool_instance in tools.items():
        if tool_name == "rag_search":
            continue

        if hasattr(tool_instance, "run"):
            run_method = getattr(tool_instance, "run")
            sig = inspect.signature(run_method)

            params = []
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                params.append(
                    {
                        "name": param_name,
                        "default": param.default
                        if param.default != inspect.Parameter.empty
                        else "REQUIRED",
                    }
                )

            print(f'    if suggested_tool == "{tool_name}":')
            print(f"        tool_input = {{")
            for p in params:
                if p["name"] == "query":
                    print(f'            "{p["name"]}": state.get("query", ""),')
                elif p["name"] == "topic":
                    print(f'            "{p["name"]}": state.get("topic", "benefits"),')
                elif p["name"] == "difficulty":
                    print(f'            "{p["name"]}": state.get("difficulty", "detailed"),')
                elif p["default"] != "REQUIRED":
                    print(f'            "{p["name"]}": {p["default"]},')
                else:
                    print(f'            "{p["name"]}": state.get("{p["name"]}", ""),')
            print(f"        }}")

    print(
        """    else:
        tool_input = {"query": state.get("query", "")}
    
    state["current_tool"] = suggested_tool
    state.setdefault("tool_calls", []).append({
        "tool": suggested_tool,
        "tool_input": tool_input,
        "reasoning": f"Plan step explicitly suggests {suggested_tool}"
    })
    return state
"""
    )

    print("\n✅ Copy the code above and replace the corresponding section in your agent_brain.py!")

except ImportError as e:
    print(f"\n❌ Failed to import tools: {e}")
    print("\nMake sure you're running this from the project root:")
    print("  cd /path/to/HR_agent")
    print("  python /home/claude/tool_inspector.py")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()

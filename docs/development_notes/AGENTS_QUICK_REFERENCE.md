# HR Specialist Agents - Quick Reference

## Summary Table

| Agent | Type | File | Tools | Purpose |
|-------|------|------|-------|---------|
| **EmployeeInfoAgent** | `employee_info` | `employee_info_agent.py` | 3 | Profile lookup, directory search, org chart |
| **PolicyAgent** | `policy` | `policy_agent.py` | 3 | Policy search, compliance check, citations |
| **LeaveAgent** | `leave` | `leave_agent.py` | 3 | Balance check, calendar view, request status |

---

## EmployeeInfoAgent - Tools Reference

```
hris_lookup(search_query, search_type="auto")
├─ Looks up employee by ID, name, or email
├─ Auto-detects search type
└─ Returns: Employee data dict

org_search(search_query, search_type="department")
├─ Searches organizational chart
├─ Supports: department, manager search
└─ Returns: Org hierarchy with direct reports

profile_synthesizer(employee_data)
├─ Converts structured data to natural language
├─ Formats: Name, title, department, location, hire date
└─ Returns: Readable profile summary
```

---

## PolicyAgent - Tools Reference

```
rag_policy_search(query, collection="policies", top_k=5)
├─ Searches policies using RAG
├─ Returns relevant excerpts with scores
└─ Min score threshold: 0.3

compliance_check(scenario, policy_query=None)
├─ Verifies scenario against policies
├─ Returns: yes/no/unknown verdict
└─ Includes supporting citations

citation_generator(rag_results)
├─ Formats results as proper citations
├─ Style: Chicago Manual of Style
└─ Includes: Document, section, page
```

**Key Requirement:** All responses include disclaimer:
> "Note: This is AI-generated guidance. Please consult HR for official decisions."

---

## LeaveAgent - Tools Reference

```
balance_calculator(employee_id)
├─ Gets leave balance (total - used - pending)
├─ Breaks down by leave type
└─ Returns: Available days per type

calendar_check(start_date=None, end_date=None, include_team=False)
├─ Shows holidays and team out-of-office
├─ Date range: today to +90 days (default)
└─ Managers: can include team members

leave_status(employee_id, status_filter=None)
├─ Lists leave requests
├─ Filters: pending, approved, denied, cancelled
└─ Shows: dates, type, status, duration
```

**Phase 1 Limitations:**
- ✅ View balances & request status
- ✅ View team calendars (managers)
- ❌ Submit new requests (use HR portal)
- ❌ Approve/deny requests

---

## How Agents Are Structured

All agents follow the BaseAgent pattern:

```
1. __init__()
   └─ Initialize with connectors (HRIS, RAG, RBAC)

2. get_agent_type() → str
   └─ Returns: "employee_info" | "policy" | "leave"

3. get_system_prompt() → str
   └─ LLM context for this agent's role

4. get_tools() → Dict[str, callable]
   └─ Returns dict of tool_name → tool_function
   └─ Each tool has .description attribute

5. _plan_node(state) → BaseAgentState [OPTIONAL OVERRIDE]
   └─ Custom planning logic for agent's domain
   └─ Creates execution plan based on query type

6. _finish_node(state) → BaseAgentState [OPTIONAL OVERRIDE]
   └─ Final answer synthesis
   └─ PolicyAgent: adds disclaimer
   └─ LeaveAgent: adds submission guidance
```

---

## Tool Error Handling

All tools follow consistent error pattern:

```python
try:
    # Tool implementation
    return {
        "result_key": result_value,
        "source": "connector_name",
    }
except Exception as e:
    logger.error(f"TOOL_NAME failed: {e}")
    return {"error": f"Friendly error message: {str(e)}"}
```

---

## Data Scope & RBAC

### EmployeeInfoAgent
- **Employee:** Can see own profile only
- **Manager:** Can see direct reports
- **HR Admin:** Can see all profiles
- Implementation: Checks `user_context["role"]`

### PolicyAgent
- **Everyone:** Can search policies
- **No restrictions:** Policies are company-wide
- Implementation: Returns results to all roles

### LeaveAgent
- **Employee:** Can see own balance/requests
- **Manager:** Can see team balance/requests/calendar
- **HR Admin:** Can see all
- Implementation: Filters by `user_context` role

---

## LLM Integration

Each agent receives a system prompt in the agent's graph execution:

```
SystemMessage(content=agent.get_system_prompt())
```

The LLM then:
1. Receives tools list from `agent.get_tools()`
2. Decides which tool to call based on query
3. Agent executor calls the tool
4. Returns result to LLM
5. LLM repeats or synthesizes final answer

---

## Key Imports

```python
# All agents use:
from .base_agent import BaseAgent, BaseAgentState
import logging

# EmployeeInfoAgent additionally uses:
from ..connectors.hris_interface import HRISConnector
from ..core.rbac import RBACManager

# PolicyAgent additionally uses:
from ..core.rag_pipeline import RAGPipeline, RAGResult

# LeaveAgent additionally uses:
from ..connectors.hris_interface import HRISConnector
from datetime import datetime, timedelta
```

---

## Testing Checklist

- [ ] Agent initialization without errors
- [ ] Each tool accessible via `get_tools()`
- [ ] Each tool has description attribute
- [ ] Tools handle missing data gracefully
- [ ] Tools log operations
- [ ] Error returns include "error" key
- [ ] System prompt is non-empty
- [ ] Agent type matches filename
- [ ] Planning override (if any) creates valid plan
- [ ] Syntax validated with `ast.parse()`

---

## File Sizes & Locations

```
/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/agents/
├── employee_info_agent.py  (12 KB)
├── policy_agent.py          (13 KB)
├── leave_agent.py           (14 KB)
└── base_agent.py            (existing)
```


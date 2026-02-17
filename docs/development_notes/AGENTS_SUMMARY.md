# HR Multi-Agent Platform - Specialist Agents

Three specialist agents have been successfully created for the HR multi-agent platform. Each agent extends `BaseAgent` and implements the required interface with domain-specific tools, system prompts, and planning logic.

---

## 1. Employee Information Agent (AGENT-001)

**File:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/agents/employee_info_agent.py`

**Class:** `EmployeeInfoAgent(BaseAgent)`

**Agent Type:** `"employee_info"`

### Purpose
Handles employee profile lookups, directory searches, organizational chart navigation, and profile synthesis with RBAC-enforced data access.

### Available Tools

#### a) `hris_lookup`
- **Description:** Look up employee information by ID, name, or email
- **Parameters:**
  - `search_query` (str): Employee ID, name, or email
  - `search_type` (str): "id", "name", "email", or "auto" (auto-detects)
- **Returns:** Employee data dict or error message
- **Calls:** `HRISConnector.get_employee()` or `HRISConnector.search_employees()`

#### b) `org_search`
- **Description:** Search organizational chart by department or manager
- **Parameters:**
  - `search_query` (str): Department name or manager name
  - `search_type` (str): "department", "manager", or "auto"
- **Returns:** Organizational hierarchy and direct reports
- **Calls:** `HRISConnector.get_org_chart()` and `HRISConnector.search_employees()`

#### c) `profile_synthesizer`
- **Description:** Generate natural language profile summary from employee data
- **Parameters:**
  - `employee_data` (dict): Structured employee information
- **Returns:** Natural language profile summary with key details
- **Synthesizes:** Name, title, department, location, hire date, contact info

### System Prompt
> "You are an Employee Information specialist agent. You help users look up employee profiles, search the company directory, and navigate the org chart. Always respect data access permissions. Use the available tools to find employee information, then synthesize the results into a clear, professional response. If the user is not authorized to view certain information, politely explain the restriction."

### Planning Strategy (`_plan_node`)
Analyzes query to determine search strategy:
- **Team/Department queries:** Use `org_search`
- **Specific person lookups:** Use `hris_lookup` + `profile_synthesizer`
- **Profile requests:** Use `hris_lookup` + `profile_synthesizer`
- **Default:** `hris_lookup` → `profile_synthesizer`

### Security & RBAC
- Respects user role from `user_context`
- Filters results based on access permissions
- Enforces role-based visibility (employee sees self, manager sees team, admin sees all)

---

## 2. Policy and Compliance Agent (AGENT-002)

**File:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/agents/policy_agent.py`

**Class:** `PolicyAgent(BaseAgent)`

**Agent Type:** `"policy"`

### Purpose
Searches company policies, verifies compliance, and provides authoritative policy guidance with proper citations and AI-generated disclaimers.

### Available Tools

#### a) `rag_policy_search`
- **Description:** Search company policies using natural language query
- **Parameters:**
  - `query` (str): Policy search query
  - `collection` (str, optional): Collection name (default: "policies")
  - `top_k` (int): Number of results (default: 5)
- **Returns:** List of relevant policy excerpts with sources and relevance scores
- **Calls:** `RAGPipeline.search()`

#### b) `compliance_check`
- **Description:** Verify if a scenario complies with company policies
- **Parameters:**
  - `scenario` (str): Description of scenario to check
  - `policy_query` (str, optional): Specific policy to check against
- **Returns:** Compliance verdict (yes/no/unknown) with supporting citations
- **Logic:** Searches policies and analyzes compliance match

#### c) `citation_generator`
- **Description:** Format RAG results as proper citations
- **Parameters:**
  - `rag_results` (list): List of RAG result dicts
- **Returns:** Formatted citations with document, section, and page references
- **Format:** Chicago Manual of Style inline citations

### System Prompt
> "You are a Policy and Compliance specialist agent. You search company policies, verify compliance, and provide authoritative answers with citations. Always include proper citations from the policy documents you reference. Include the following disclaimer in all responses: 'Note: This is AI-generated guidance. Please consult HR for official decisions.' Be precise, reference specific policy sections, and explain how policies apply to scenarios."

### Planning Strategy (`_plan_node`)
Determines execution plan based on query type:
- **Compliance questions:** `compliance_check` → `rag_policy_search` → `citation_generator`
- **Policy searches:** `rag_policy_search` → `citation_generator`
- **Interpretations:** `rag_policy_search` → `citation_generator`
- **Default:** `rag_policy_search` → `citation_generator`

### Compliance Disclaimer
All responses include the disclaimer:
> "Note: This is AI-generated guidance. Please consult HR for official decisions."

Implemented in overridden `_finish_node()` to ensure consistency.

### Data Sources
- Uses `RAGPipeline` from `src/core/rag_pipeline.py`
- Accesses "policies" collection by default
- Configurable per-query collection selection
- Minimum relevance score: 0.3

---

## 3. Leave and Attendance Agent (AGENT-003)

**File:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/agents/leave_agent.py`

**Class:** `LeaveAgent(BaseAgent)`

**Agent Type:** `"leave"`

### Purpose
Handles leave balance checks, team calendar lookups, leave request status, and attendance-related queries with read-only operations in Phase 1.

### Available Tools

#### a) `balance_calculator`
- **Description:** Get employee leave balance (total - used - pending)
- **Parameters:**
  - `employee_id` (str): Employee ID
- **Returns:** Breakdown by leave type with total available balance
- **Calls:** `HRISConnector.get_leave_balance()`
- **Calculation:** available = total - used - pending

#### b) `calendar_check`
- **Description:** View team calendar, holidays, and out-of-office dates
- **Parameters:**
  - `start_date` (str, optional): ISO format date (default: today)
  - `end_date` (str, optional): ISO format date (default: +90 days)
  - `include_team` (bool): Include team members' out-of-office
  - `team_id` (str, optional): Specific team ID
- **Returns:** Calendar events including holidays and team leave
- **Features:** Shows upcoming holidays, team out-of-office (for managers)

#### c) `leave_status`
- **Description:** Check leave request status
- **Parameters:**
  - `employee_id` (str): Employee ID
  - `status_filter` (str, optional): Filter by status (pending, approved, denied, cancelled)
- **Returns:** List of leave requests with status and details
- **Calls:** `HRISConnector.get_leave_requests()`
- **Details:** Request ID, dates, status, duration, notes

### System Prompt
> "You are a Leave and Attendance specialist agent. You help employees check their leave balances, view team calendars, and check leave request statuses. Phase 1 is read-only: employees can view balances and request status, but must use the HR portal to submit new leave requests. Managers can view their team's leave and calendars. Always be clear about remaining balances and provide helpful guidance on leave policy and request procedures."

### Planning Strategy (`_plan_node`)
Determines action based on query type:
- **Balance inquiries:** `balance_calculator`
- **Calendar/holiday queries:** `calendar_check`
- **Request status:** `leave_status`
- **Leave booking:** `balance_calculator` + reminder about HR portal
- **Default:** `balance_calculator` + `leave_status`

### Phase 1 Limitations (Read-Only)
- ✅ View own/team leave balances
- ✅ Check request status
- ✅ View holidays and team calendars
- ❌ Submit new leave requests (must use HR portal)
- ❌ Approve/deny requests (manager portal only)

### Read-Only Note
All responses include submission guidance:
> "To submit a new leave request, please use the HR portal at [portal URL]. Phase 1 of the agent system is read-only for leave management."

Implemented in overridden `_finish_node()`.

### Data Scope
- **Employees:** See own balance and requests
- **Managers:** See team balances and requests
- **HR Admin:** See all balances and requests (via base RBAC)

---

## Implementation Details

### Common Features

All three agents implement:

1. **BaseAgent Interface**
   ```python
   class YourAgent(BaseAgent):
       def get_agent_type(self) -> str: ...
       def get_system_prompt(self) -> str: ...
       def get_tools(self) -> Dict[str, Any]: ...
   ```

2. **Tool Structure**
   - Each tool is a callable function
   - Each tool has a `.description` attribute for LLM prompting
   - Tools handle errors gracefully and return dict with "error" key on failure
   - Tools include logging for debugging

3. **Logging**
   - Using Python `logging` module
   - Log level: INFO
   - Log messages include operation name, parameters, and results
   - Error logging with exception details

4. **Type Hints**
   - Full type hints on all functions
   - Dict[str, Any] for flexible returns
   - Optional types for nullable parameters
   - Proper TypedDict usage for structured data

5. **Planning Override**
   - Each agent overrides `_plan_node()` for domain-specific planning
   - Analyzes query to determine execution strategy
   - Creates ordered list of tools to use
   - Logs planning decisions for debugging

6. **Error Handling**
   - Try-catch blocks in all tool functions
   - Graceful degradation (returns error dict, doesn't crash)
   - User-friendly error messages
   - Exception details in logs

### Imports
```python
from .base_agent import BaseAgent, BaseAgentState
from ..connectors.hris_interface import HRISConnector
from ..core.rag_pipeline import RAGPipeline
```

### State Management
- Uses `BaseAgentState` TypedDict for state passing
- Maintains execution trace in `state["reasoning_trace"]`
- Updates `state["plan"]` during planning phase
- Tracks tools used in `state["tool_calls"]`

---

## Integration Points

### HRIS Connector
- **Module:** `src/connectors/hris_interface.py`
- **Methods used:**
  - `get_employee(employee_id)` → Employee
  - `search_employees(filters)` → List[Employee]
  - `get_org_chart(department)` → List[OrgNode]
  - `get_leave_balance(employee_id)` → List[LeaveBalance]
  - `get_leave_requests(employee_id, status)` → List[LeaveRequest]

### RAG Pipeline
- **Module:** `src/core/rag_pipeline.py`
- **Methods used:**
  - `search(query, collection, top_k, min_score)` → List[RAGResult]
- **Collections:** "policies" (policy agent)

### RBAC Manager
- **Module:** `src/core/rbac.py`
- **Usage:** Access control enforcement in employee info agent
- **Checks:** User role, department visibility, permission validation

---

## Usage Example

```python
from src.agents.employee_info_agent import EmployeeInfoAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.leave_agent import LeaveAgent

# Initialize agents
emp_agent = EmployeeInfoAgent(hris_connector=hris)
policy_agent = PolicyAgent(rag_pipeline=rag)
leave_agent = LeaveAgent(hris_connector=hris)

# Run employee info agent
result = emp_agent.run(
    query="Who is the manager of John Smith?",
    user_context={
        "user_id": "emp_001",
        "role": "employee",
        "department": "Engineering"
    }
)

# Run policy agent
result = policy_agent.run(
    query="Can I work from home on Fridays?"
)

# Run leave agent
result = leave_agent.run(
    query="How many vacation days do I have left?"
)
```

---

## File Locations

- **Employee Info Agent:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/agents/employee_info_agent.py` (12 KB)
- **Policy Agent:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/agents/policy_agent.py` (13 KB)
- **Leave Agent:** `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/agents/leave_agent.py` (14 KB)

All files have been syntax-validated with `ast.parse()`.

---

## Next Steps

1. **Testing:** Create unit tests for each agent's tools
2. **Integration:** Connect agents to the LangGraph dispatcher
3. **RBAC Enforcement:** Integrate RBACManager for access control
4. **RAG Data:** Load HR policies into RAG collections
5. **Error Handling:** Add comprehensive error scenarios
6. **Performance:** Profile and optimize tool execution
7. **Monitoring:** Add metrics collection and alerting


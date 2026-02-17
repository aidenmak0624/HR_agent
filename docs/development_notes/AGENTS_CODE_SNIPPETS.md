# HR Specialist Agents - Code Snippets

## Employee Information Agent Highlights

### Implementation Pattern
```python
class EmployeeInfoAgent(BaseAgent):
    """Specialist agent for employee information lookups."""
    
    def __init__(self, hris_connector: Optional[HRISConnector] = None, 
                 rbac: Optional[RBACManager] = None):
        self.hris_connector = hris_connector
        self.rbac = rbac
        super().__init__()
    
    def get_agent_type(self) -> str:
        return "employee_info"
    
    def get_system_prompt(self) -> str:
        return "You are an Employee Information specialist agent..."
    
    def get_tools(self) -> Dict[str, Any]:
        return {
            "hris_lookup": hris_lookup_function,
            "org_search": org_search_function,
            "profile_synthesizer": profile_synthesizer_function,
        }
```

### HRIS Lookup Tool
```python
def hris_lookup(search_query: str, search_type: str = "auto") -> Dict[str, Any]:
    """Look up employee information."""
    try:
        if not self.hris_connector:
            return {"error": "HRIS connector not available"}
        
        logger.info(f"HRIS_LOOKUP: Searching by {search_type}: {search_query}")
        
        # Auto-detect search type
        if search_type == "auto":
            if "@" in search_query:
                search_type = "email"
            elif search_query.isdigit():
                search_type = "id"
            else:
                search_type = "name"
        
        # Perform search
        if search_type == "id":
            employee = self.hris_connector.get_employee(search_query)
            if employee:
                return {
                    "employee": employee.dict(),
                    "source": f"HRIS/{employee.hris_id}",
                }
        
        elif search_type in ["name", "email"]:
            filters = {search_type: search_query}
            employees = self.hris_connector.search_employees(filters)
            if employees:
                return {
                    "employees": [e.dict() for e in employees],
                    "count": len(employees),
                    "source": f"HRIS/search/{search_type}",
                }
        
        return {"error": f"No results found for {search_query}"}
        
    except Exception as e:
        logger.error(f"HRIS_LOOKUP failed: {e}")
        return {"error": f"Lookup failed: {str(e)}"}

hris_lookup.description = (
    "Look up employee information by ID, name, or email. "
    "Respects RBAC restrictions. Returns employee profile data."
)
```

### Domain-Specific Planning
```python
def _plan_node(self, state: BaseAgentState) -> BaseAgentState:
    """Create execution plan specific to employee information requests."""
    query = state.get("query", "").lower()
    plan = []
    
    logger.info(f"PLAN: Analyzing query: {query[:50]}")
    
    # Determine search strategy
    if any(word in query for word in ["team", "department", "org chart"]):
        plan.append("Use org_search to find organizational structure")
    elif any(word in query for word in ["who is", "find", "lookup"]):
        plan.append("Use hris_lookup to find employee")
        plan.append("Use profile_synthesizer to generate profile summary")
    else:
        plan.append("Use hris_lookup to search for employee")
        plan.append("Use profile_synthesizer if specific employee found")
    
    state["plan"] = plan
    state["reasoning_trace"].append(f"Created plan with {len(plan)} steps")
    logger.info(f"PLAN: {plan}")
    
    return state
```

---

## Policy Agent Highlights

### RAG-Based Policy Search
```python
def rag_policy_search(query: str, collection: Optional[str] = None, 
                     top_k: int = 5) -> Dict[str, Any]:
    """Search company policies using RAG."""
    try:
        if not self.rag_pipeline:
            return {"error": "RAG pipeline not available"}
        
        logger.info(f"RAG_SEARCH: Searching policies for: {query[:50]}")
        
        collection_name = collection or "policies"
        
        # Search RAG pipeline
        results = self.rag_pipeline.search(
            query=query,
            collection=collection_name,
            top_k=top_k,
            min_score=0.3
        )
        
        if not results:
            return {"error": f"No policies found matching: {query}"}
        
        # Format results for LLM
        formatted_results = []
        for result in results:
            formatted_results.append({
                "content": result.content,
                "source": result.source,
                "score": result.score,
                "metadata": result.metadata,
            })
        
        return {
            "results": formatted_results,
            "count": len(results),
            "sources": list({r["source"] for r in formatted_results}),
            "query": query,
        }
        
    except Exception as e:
        logger.error(f"RAG_SEARCH failed: {e}")
        return {"error": f"Policy search failed: {str(e)}"}

rag_policy_search.description = (
    "Search company policies using natural language query. "
    "Returns relevant policy excerpts with sources and relevance scores."
)
```

### Compliance Verification
```python
def compliance_check(scenario: str, 
                    policy_query: Optional[str] = None) -> Dict[str, Any]:
    """Verify if a scenario complies with company policies."""
    try:
        if not self.rag_pipeline:
            return {"error": "RAG pipeline not available"}
        
        logger.info(f"COMPLIANCE_CHECK: Checking scenario: {scenario[:50]}")
        
        search_query = policy_query or scenario
        
        # Search relevant policies
        results = self.rag_pipeline.search(
            query=search_query,
            collection="policies",
            top_k=5,
            min_score=0.3
        )
        
        if not results:
            return {
                "compliant": "unknown",
                "reason": "No relevant policies found",
                "recommendation": "Contact HR for compliance verification",
            }
        
        # Build compliance analysis
        compliance_analysis = {
            "scenario": scenario,
            "compliant": "yes",
            "matching_policies": len(results),
            "relevant_excerpts": [],
            "sources": [],
        }
        
        for result in results:
            compliance_analysis["relevant_excerpts"].append({
                "content": result.content[:200],
                "source": result.source,
            })
            if result.source not in compliance_analysis["sources"]:
                compliance_analysis["sources"].append(result.source)
        
        return compliance_analysis
        
    except Exception as e:
        logger.error(f"COMPLIANCE_CHECK failed: {e}")
        return {"error": f"Compliance check failed: {str(e)}"}

compliance_check.description = (
    "Verify if a scenario complies with company policies. "
    "Returns yes/no verdict with supporting citations."
)
```

### Disclaimer Enforcement
```python
def _finish_node(self, state: BaseAgentState) -> BaseAgentState:
    """Synthesize final answer with compliance disclaimer."""
    # Call parent finish node
    state = super()._finish_node(state)
    
    # Add disclaimer to final answer
    final_answer = state.get("final_answer", "")
    disclaimer = (
        "\n\n---\n"
        "Note: This is AI-generated guidance. Please consult HR for official decisions."
    )
    
    state["final_answer"] = final_answer + disclaimer
    logger.info("FINISH: Added compliance disclaimer to response")
    
    return state
```

---

## Leave Agent Highlights

### Leave Balance Calculation
```python
def balance_calculator(employee_id: str) -> Dict[str, Any]:
    """Calculate available leave balance."""
    try:
        if not self.hris_connector:
            return {"error": "HRIS connector not available"}
        
        logger.info(f"BALANCE_CALCULATOR: Getting balance for {employee_id}")
        
        # Get leave balances from HRIS
        leave_balances = self.hris_connector.get_leave_balance(employee_id)
        
        if not leave_balances:
            return {"error": f"No leave balance found for {employee_id}"}
        
        # Calculate summary
        total_balance = 0.0
        balance_summary = []
        
        for balance in leave_balances:
            leave_type = getattr(balance, 'leave_type', 'Unknown')
            total = getattr(balance, 'total_days', 0)
            used = getattr(balance, 'used_days', 0)
            pending = getattr(balance, 'pending_days', 0)
            available = total - used - pending
            
            total_balance += available
            
            balance_summary.append({
                "leave_type": leave_type,
                "total": total,
                "used": used,
                "pending": pending,
                "available": available,
            })
        
        return {
            "employee_id": employee_id,
            "total_available": total_balance,
            "balance_by_type": balance_summary,
            "as_of": datetime.now().isoformat(),
            "source": "HRIS",
        }
        
    except Exception as e:
        logger.error(f"BALANCE_CALCULATOR failed: {e}")
        return {"error": f"Balance calculation failed: {str(e)}"}

balance_calculator.description = (
    "Get employee leave balance. "
    "Calculates available = total - used - pending for each leave type."
)
```

### Team Calendar Check
```python
def calendar_check(start_date: Optional[str] = None,
                  end_date: Optional[str] = None,
                  include_team: bool = False,
                  team_id: Optional[str] = None) -> Dict[str, Any]:
    """Check team calendar and holidays."""
    try:
        if not self.hris_connector:
            return {"error": "HRIS connector not available"}
        
        logger.info(f"CALENDAR_CHECK: Checking dates {start_date} to {end_date}")
        
        # Parse dates or use defaults
        if not start_date:
            start = datetime.now()
        else:
            start = datetime.fromisoformat(start_date)
        
        if not end_date:
            end = start + timedelta(days=90)
        else:
            end = datetime.fromisoformat(end_date)
        
        # Build calendar events
        events = {
            "holidays": [],
            "team_out": [],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
        
        # Add common holidays
        common_holidays = [
            {"date": "2025-01-01", "name": "New Year's Day"},
            {"date": "2025-07-04", "name": "Independence Day"},
            {"date": "2025-12-25", "name": "Christmas"},
        ]
        
        for holiday in common_holidays:
            h_date = datetime.fromisoformat(holiday["date"])
            if start <= h_date <= end:
                events["holidays"].append(holiday)
        
        # If include_team, fetch team leave
        if include_team and team_id:
            logger.info(f"CALENDAR_CHECK: Including team {team_id} leave")
            # Real implementation would fetch team data
        
        return {
            "calendar_events": events,
            "date_range": f"{start.date()} to {end.date()}",
            "total_holidays": len(events["holidays"]),
            "team_included": include_team,
        }
        
    except Exception as e:
        logger.error(f"CALENDAR_CHECK failed: {e}")
        return {"error": f"Calendar check failed: {str(e)}"}

calendar_check.description = (
    "View team calendar, holidays, and out-of-office dates. "
    "Shows upcoming holidays and team members' leave (for managers)."
)
```

### Read-Only Note Enforcement
```python
def _finish_node(self, state: BaseAgentState) -> BaseAgentState:
    """Synthesize final answer with leave submission note."""
    # Call parent finish node
    state = super()._finish_node(state)
    
    # Add read-only note to final answer
    final_answer = state.get("final_answer", "")
    
    # Only add note if relevant
    if "submit" in final_answer.lower() or "request" in final_answer.lower():
        note = (
            "\n\n---\n"
            "To submit a new leave request, please use the HR portal. "
            "Phase 1 of the agent system is read-only for leave management."
        )
        state["final_answer"] = final_answer + note
        logger.info("FINISH: Added leave submission note to response")
    
    return state
```

---

## Common Error Handling Pattern

All tools follow this pattern:

```python
def tool_function(param: str) -> Dict[str, Any]:
    """Tool description."""
    try:
        # Validate preconditions
        if not self.connector:
            return {"error": "Connector not available"}
        
        # Log operation start
        logger.info(f"TOOL_NAME: Starting with param: {param}")
        
        # Execute tool logic
        result = self.connector.method(param)
        
        # Format result
        formatted = {
            "data": result,
            "source": "connector_name",
        }
        
        # Log success
        logger.info(f"TOOL_NAME: Success, returned {len(result)} items")
        
        return formatted
        
    except SpecificException as e:
        # Handle specific errors
        logger.error(f"TOOL_NAME: Specific error: {e}")
        return {"error": f"Specific error message: {str(e)}"}
    except Exception as e:
        # Handle generic errors
        logger.error(f"TOOL_NAME failed: {e}")
        return {"error": f"Tool failed: {str(e)}"}

# Add description for LLM prompting
tool_function.description = "Tool description for LLM"
```

---

## System Prompt Examples

### EmployeeInfoAgent
```
You are an Employee Information specialist agent. 
You help users look up employee profiles, search the company directory, 
and navigate the org chart. Always respect data access permissions. 
Use the available tools to find employee information, then synthesize 
the results into a clear, professional response. 
If the user is not authorized to view certain information, 
politely explain the restriction.
```

### PolicyAgent
```
You are a Policy and Compliance specialist agent. 
You search company policies, verify compliance, and provide 
authoritative answers with citations. 
Always include proper citations from the policy documents you reference. 
Include the following disclaimer in all responses: 
'Note: This is AI-generated guidance. Please consult HR for official decisions.' 
Be precise, reference specific policy sections, and explain 
how policies apply to scenarios.
```

### LeaveAgent
```
You are a Leave and Attendance specialist agent. 
You help employees check their leave balances, view team calendars, 
and check leave request statuses. 
Phase 1 is read-only: employees can view balances and request status, 
but must use the HR portal to submit new leave requests. 
Managers can view their team's leave and calendars. 
Always be clear about remaining balances and provide helpful guidance 
on leave policy and request procedures.
```

---

## Usage Examples

### Initializing Agents
```python
from src.agents.employee_info_agent import EmployeeInfoAgent
from src.agents.policy_agent import PolicyAgent
from src.agents.leave_agent import LeaveAgent
from src.connectors.hris_interface import HRISConnector
from src.core.rag_pipeline import RAGPipeline
from src.core.rbac import RBACManager

# Initialize connectors
hris = HRISConnector()
rag = RAGPipeline()
rbac = RBACManager()

# Create agents
emp_agent = EmployeeInfoAgent(hris_connector=hris, rbac=rbac)
policy_agent = PolicyAgent(rag_pipeline=rag)
leave_agent = LeaveAgent(hris_connector=hris)
```

### Running Agents
```python
# Query employee info
result = emp_agent.run(
    query="Who is the manager of John Smith?",
    user_context={
        "user_id": "emp_001",
        "role": "employee",
        "department": "Engineering"
    }
)
print(result["answer"])
print(f"Tools used: {result['tools_used']}")
print(f"Sources: {result['sources']}")

# Query policies
result = policy_agent.run(
    query="Can I work from home on Fridays?"
)
print(result["answer"])  # Includes disclaimer

# Query leave
result = leave_agent.run(
    query="How many vacation days do I have left?"
)
print(result["answer"])  # Includes submission note
```

---

## Testing Template

```python
import unittest
from unittest.mock import Mock, MagicMock
from src.agents.employee_info_agent import EmployeeInfoAgent

class TestEmployeeInfoAgent(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_hris = Mock()
        self.agent = EmployeeInfoAgent(hris_connector=self.mock_hris)
    
    def test_agent_type(self):
        """Test agent type identifier."""
        self.assertEqual(self.agent.get_agent_type(), "employee_info")
    
    def test_system_prompt(self):
        """Test system prompt is non-empty."""
        prompt = self.agent.get_system_prompt()
        self.assertIsNotNone(prompt)
        self.assertGreater(len(prompt), 0)
    
    def test_get_tools(self):
        """Test all tools are defined."""
        tools = self.agent.get_tools()
        expected_tools = ["hris_lookup", "org_search", "profile_synthesizer"]
        for tool in expected_tools:
            self.assertIn(tool, tools)
            self.assertTrue(hasattr(tools[tool], 'description'))
    
    def test_hris_lookup_with_email(self):
        """Test HRIS lookup with email address."""
        tools = self.agent.get_tools()
        
        # Mock HRIS response
        self.mock_hris.search_employees.return_value = [
            Mock(dict=lambda: {"id": "1", "first_name": "John"})
        ]
        
        result = tools["hris_lookup"]("john@company.com", "auto")
        
        self.assertIn("employees", result)
        self.assertEqual(result["count"], 1)
    
    def test_hris_lookup_error_handling(self):
        """Test error handling in HRIS lookup."""
        tools = self.agent.get_tools()
        
        # Mock HRIS error
        self.mock_hris.get_employee.side_effect = Exception("HRIS down")
        
        result = tools["hris_lookup"]("123", "id")
        
        self.assertIn("error", result)

if __name__ == '__main__':
    unittest.main()
```


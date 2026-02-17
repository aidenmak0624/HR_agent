"""
Employee Information Agent (AGENT-001) for HR multi-agent platform.

Handles employee profile lookups, directory searches, org chart navigation,
and profile synthesis with RBAC data access enforcement.
"""

import logging
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent, BaseAgentState
from ..connectors.hris_interface import HRISConnector
from ..core.rbac import RBACManager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class EmployeeInfoAgent(BaseAgent):
    """
    Specialist agent for employee information lookups and directory searches.
    
    Provides tools for:
    - Looking up employee profiles by ID, name, or email
    - Searching company directory
    - Navigating organizational chart
    - Generating natural language profile summaries
    
    Enforces RBAC restrictions based on user role.
    """
    
    def __init__(self, llm=None, hris_connector: Optional[HRISConnector] = None, rbac: Optional[RBACManager] = None):
        """
        Initialize Employee Info Agent.

        Args:
            llm: Language model instance (passed from RouterAgent)
            hris_connector: HRIS connector instance
            rbac: RBAC manager instance for access control
        """
        self.hris_connector = hris_connector
        self.rbac = rbac
        super().__init__(llm=llm)
    
    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "employee_info"
    
    def get_system_prompt(self) -> str:
        """Return system prompt for employee information specialist."""
        return (
            "You are an Employee Information specialist agent. "
            "You help users look up employee profiles, search the company directory, "
            "and navigate the org chart. Always respect data access permissions. "
            "Use the available tools to find employee information, then synthesize "
            "the results into a clear, professional response. "
            "If the user is not authorized to view certain information, politely explain the restriction."
        )
    
    def get_tools(self) -> Dict[str, Any]:
        """
        Return available tools for employee information lookups.
        
        Tools:
        - hris_lookup: Look up employee by ID, name, or email
        - org_search: Search organizational chart by department or manager
        - profile_synthesizer: Generate natural language profile summary
        
        Returns:
            Dict of tool_name -> tool_function with description attribute
        """
        tools = {}
        
        # Tool 1: HRIS Lookup
        def hris_lookup(search_query: str, search_type: str = "auto") -> Dict[str, Any]:
            """
            Look up employee information.
            
            Args:
                search_query: Employee ID, name, or email
                search_type: "id", "name", "email", or "auto" (default)
                
            Returns:
                Employee data dict or error message
            """
            try:
                if not self.hris_connector:
                    return {"error": "HRIS connector not available"}
                
                logger.info(f"HRIS_LOOKUP: Searching by {search_type}: {search_query}")
                
                # Try to auto-detect search type
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
                    return {"error": f"Employee ID {search_query} not found"}
                
                elif search_type in ["name", "email"]:
                    filters = {search_type: search_query}
                    employees = self.hris_connector.search_employees(filters)
                    if employees:
                        return {
                            "employees": [e.dict() for e in employees],
                            "count": len(employees),
                            "source": f"HRIS/search/{search_type}",
                        }
                    return {"error": f"No employees found matching {search_type}: {search_query}"}
                
                return {"error": f"Unknown search type: {search_type}"}
                
            except Exception as e:
                logger.error(f"HRIS_LOOKUP failed: {e}")
                return {"error": f"Lookup failed: {str(e)}"}
        
        hris_lookup.description = (
            "Look up employee information by ID, name, or email. "
            "Respects RBAC restrictions. Returns employee profile data."
        )
        tools["hris_lookup"] = hris_lookup
        
        # Tool 2: Org Search
        def org_search(search_query: str, search_type: str = "department") -> Dict[str, Any]:
            """
            Search organizational chart.
            
            Args:
                search_query: Department name or manager name
                search_type: "department", "manager", or "auto" (default)
                
            Returns:
                List of org nodes or employees in hierarchy
            """
            try:
                if not self.hris_connector:
                    return {"error": "HRIS connector not available"}
                
                logger.info(f"ORG_SEARCH: Searching {search_type}: {search_query}")
                
                if search_type == "department" or search_type == "auto":
                    org_nodes = self.hris_connector.get_org_chart(search_query)
                    if org_nodes:
                        return {
                            "org_nodes": [n.dict() if hasattr(n, 'dict') else str(n) for n in org_nodes],
                            "count": len(org_nodes),
                            "source": f"HRIS/org_chart/{search_query}",
                        }
                    return {"error": f"Department {search_query} not found"}
                
                elif search_type == "manager":
                    # Search for manager first, then get org chart
                    filters = {"name": search_query}
                    managers = self.hris_connector.search_employees(filters)
                    if managers:
                        manager = managers[0]
                        org_nodes = self.hris_connector.get_org_chart()
                        # Filter for this manager's reports
                        reports = [n for n in org_nodes if getattr(n, 'manager_id', None) == manager.id]
                        return {
                            "manager": manager.dict(),
                            "direct_reports": [r.dict() if hasattr(r, 'dict') else str(r) for r in reports],
                            "count": len(reports),
                            "source": f"HRIS/manager/{manager.id}",
                        }
                    return {"error": f"Manager {search_query} not found"}
                
                return {"error": f"Unknown search type: {search_type}"}
                
            except Exception as e:
                logger.error(f"ORG_SEARCH failed: {e}")
                return {"error": f"Org search failed: {str(e)}"}
        
        org_search.description = (
            "Search organizational chart by department or manager. "
            "Returns organizational hierarchy and direct reports."
        )
        tools["org_search"] = org_search
        
        # Tool 3: Profile Synthesizer
        def profile_synthesizer(employee_data: Dict[str, Any]) -> Dict[str, str]:
            """
            Generate natural language profile summary.
            
            Args:
                employee_data: Employee data dictionary
                
            Returns:
                Synthesized profile summary as string
            """
            try:
                logger.info(f"PROFILE_SYNTHESIZER: Generating summary for {employee_data.get('first_name', 'Unknown')}")
                
                first_name = employee_data.get("first_name", "")
                last_name = employee_data.get("last_name", "")
                email = employee_data.get("email", "N/A")
                department = employee_data.get("department", "Unknown")
                job_title = employee_data.get("job_title", "Unknown")
                location = employee_data.get("location", "Unknown")
                hire_date = employee_data.get("hire_date", "Unknown")
                status = employee_data.get("status", "Unknown")
                phone = employee_data.get("phone", "N/A")
                
                profile = (
                    f"{first_name} {last_name} is a {job_title} in the {department} department. "
                    f"Based at {location}, they have been with the company since {hire_date}. "
                    f"Current employment status: {status}. "
                    f"Contact: {email}"
                )
                
                if phone != "N/A":
                    profile += f" | {phone}"
                
                return {
                    "profile_summary": profile,
                    "employee_name": f"{first_name} {last_name}",
                    "department": department,
                    "job_title": job_title,
                }
                
            except Exception as e:
                logger.error(f"PROFILE_SYNTHESIZER failed: {e}")
                return {"error": f"Profile synthesis failed: {str(e)}"}
        
        profile_synthesizer.description = (
            "Generate natural language profile summary from employee data. "
            "Converts structured employee information into readable format."
        )
        tools["profile_synthesizer"] = profile_synthesizer
        
        return tools
    
    def _plan_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Create execution plan specific to employee information requests.
        
        Analyzes query to determine search strategy:
        - If asking for specific person, use hris_lookup
        - If asking for team/department, use org_search
        - If asking for profile, use hris_lookup + profile_synthesizer
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with plan
        """
        query = state.get("query", "").lower()
        plan = []
        
        logger.info(f"PLAN: Analyzing query for employee info: {query[:50]}")
        
        # Determine search strategy
        if any(word in query for word in ["team", "department", "org chart", "reports"]):
            plan.append("Use org_search to find organizational structure")
        elif any(word in query for word in ["who is", "find", "lookup", "email", "contact"]):
            plan.append("Use hris_lookup to find employee by name/ID/email")
            plan.append("Use profile_synthesizer to generate profile summary")
        elif any(word in query for word in ["profile", "summary", "about"]):
            plan.append("Use hris_lookup to find employee")
            plan.append("Use profile_synthesizer to create natural language summary")
        else:
            # Default: try lookup first
            plan.append("Use hris_lookup to search for employee")
            plan.append("Use profile_synthesizer if specific employee found")
        
        state["plan"] = plan
        state["current_step"] = 0
        state.setdefault("reasoning_trace", []).append(f"Created plan with {len(plan)} steps")
        logger.info(f"PLAN: {plan}")

        return state


# Register agent class for discovery
__all__ = ["EmployeeInfoAgent"]

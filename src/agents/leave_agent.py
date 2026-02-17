"""
Leave and Attendance Agent (AGENT-003) for HR multi-agent platform.

Handles leave balance checks, team calendar lookups, leave request status,
and attendance-related queries with read-only operations in Phase 1.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .base_agent import BaseAgent, BaseAgentState
from ..connectors.hris_interface import HRISConnector

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LeaveAgent(BaseAgent):
    """
    Specialist agent for leave and attendance management.

    Provides tools for:
    - Checking leave balances (own or team)
    - Viewing team calendars and holidays
    - Checking leave request status
    - Viewing upcoming time off

    Phase 1 is read-only; new requests must be submitted via HR portal.
    """

    def __init__(self, llm=None, hris_connector: Optional[HRISConnector] = None):
        """
        Initialize Leave Agent.

        Args:
            llm: Language model instance (passed from RouterAgent)
            hris_connector: HRIS connector instance
        """
        self.hris_connector = hris_connector
        super().__init__(llm=llm)

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "leave"

    def get_system_prompt(self) -> str:
        """Return system prompt for leave specialist."""
        return (
            "You are a Leave and Attendance specialist agent. "
            "You help employees check their leave balances, view team calendars, "
            "and check leave request statuses. "
            "Phase 1 is read-only: employees can view balances and request status, "
            "but must use the HR portal to submit new leave requests. "
            "Managers can view their team's leave and calendars. "
            "Always be clear about remaining balances and provide helpful guidance "
            "on leave policy and request procedures."
        )

    def get_tools(self) -> Dict[str, Any]:
        """
        Return available tools for leave and attendance management.

        Tools:
        - balance_calculator: Get leave balance (total - used - pending)
        - calendar_check: View team calendar, holidays, and out-of-office dates
        - leave_status: Check pending/recent leave request status

        Returns:
            Dict of tool_name -> tool_function with description attribute
        """
        tools = {}

        # Tool 1: Balance Calculator
        def balance_calculator(employee_id: str) -> Dict[str, Any]:
            """
            Calculate available leave balance.

            Args:
                employee_id: Employee ID

            Returns:
                Leave balance breakdown by type
            """
            try:
                if not self.hris_connector:
                    return {"error": "HRIS connector not available"}

                logger.info(f"BALANCE_CALCULATOR: Getting balance for {employee_id}")

                # Get leave balances from HRIS
                leave_balances = self.hris_connector.get_leave_balance(employee_id)

                if not leave_balances:
                    return {"error": f"No leave balance found for employee {employee_id}"}

                # Calculate summary
                total_balance = 0.0
                balance_summary = []

                for balance in leave_balances:
                    leave_type = getattr(balance, "leave_type", "Unknown")
                    total = getattr(balance, "total_days", 0)
                    used = getattr(balance, "used_days", 0)
                    pending = getattr(balance, "pending_days", 0)
                    available = total - used - pending

                    total_balance += available

                    balance_summary.append(
                        {
                            "leave_type": leave_type,
                            "total": total,
                            "used": used,
                            "pending": pending,
                            "available": available,
                        }
                    )

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
            "Calculates available = total - used - pending for each leave type. "
            "Employees see their own, managers see their team."
        )
        tools["balance_calculator"] = balance_calculator

        # Tool 2: Calendar Check
        def calendar_check(
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            include_team: bool = False,
            team_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            """
            Check team calendar and holidays.

            Args:
                start_date: Start date (ISO format, default today)
                end_date: End date (ISO format, default 90 days ahead)
                include_team: Include team members' out-of-office
                team_id: Specific team ID (optional)

            Returns:
                Calendar events including holidays and team leave
            """
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

                # Get holidays and team leave
                # Note: This is simplified; real implementation would call HRIS methods
                events = {
                    "holidays": [],
                    "team_out": [],
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                }

                # Mock holiday data
                # Real implementation would fetch from HRIS
                common_holidays = [
                    {"date": "2025-01-01", "name": "New Year's Day"},
                    {"date": "2025-07-04", "name": "Independence Day"},
                    {"date": "2025-12-25", "name": "Christmas"},
                ]

                for holiday in common_holidays:
                    h_date = datetime.fromisoformat(holiday["date"])
                    if start <= h_date <= end:
                        events["holidays"].append(holiday)

                # If include_team, would fetch team leave requests
                if include_team and team_id:
                    logger.info(f"CALENDAR_CHECK: Including team {team_id} leave")
                    # Real implementation would call get_leave_requests for team

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
            "Shows upcoming holidays and team members' leave (for managers). "
            "Returns events within specified date range."
        )
        tools["calendar_check"] = calendar_check

        # Tool 3: Leave Status
        def leave_status(employee_id: str, status_filter: Optional[str] = None) -> Dict[str, Any]:
            """
            Check leave request status.

            Args:
                employee_id: Employee ID
                status_filter: Filter by status (pending, approved, denied, all)

            Returns:
                List of leave requests with status
            """
            try:
                if not self.hris_connector:
                    return {"error": "HRIS connector not available"}

                logger.info(f"LEAVE_STATUS: Getting requests for {employee_id}")

                # Get leave requests
                requests = self.hris_connector.get_leave_requests(
                    employee_id=employee_id, status=status_filter
                )

                if not requests:
                    return {
                        "employee_id": employee_id,
                        "message": f"No {status_filter or 'leave'} requests found",
                        "count": 0,
                    }

                # Format request data
                formatted_requests = []

                for req in requests:
                    formatted_requests.append(
                        {
                            "request_id": getattr(req, "id", "Unknown"),
                            "leave_type": getattr(req, "leave_type", "Unknown"),
                            "start_date": getattr(req, "start_date", "Unknown"),
                            "end_date": getattr(req, "end_date", "Unknown"),
                            "status": getattr(req, "status", "Unknown"),
                            "duration_days": getattr(req, "duration_days", 0),
                            "notes": getattr(req, "notes", ""),
                        }
                    )

                return {
                    "employee_id": employee_id,
                    "requests": formatted_requests,
                    "count": len(formatted_requests),
                    "status_filter": status_filter or "all",
                    "source": "HRIS",
                }

            except Exception as e:
                logger.error(f"LEAVE_STATUS failed: {e}")
                return {"error": f"Leave status lookup failed: {str(e)}"}

        leave_status.description = (
            "Check leave request status (pending, approved, denied, cancelled). "
            "Shows request details including dates, type, and approval status. "
            "Employees see own requests, managers see team requests."
        )
        tools["leave_status"] = leave_status

        return tools

    def _plan_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Create execution plan specific to leave queries.

        Determines action based on query type:
        - Balance inquiry: balance_calculator
        - Calendar/holiday: calendar_check
        - Request status: leave_status

        Args:
            state: Current agent state

        Returns:
            Updated state with plan
        """
        query = state.get("query", "").lower()
        plan = []

        logger.info(f"PLAN: Analyzing leave query: {query[:50]}")

        # Determine query type
        if any(word in query for word in ["balance", "available", "how much", "remaining"]):
            plan.append("Use balance_calculator to get leave balance")
        elif any(word in query for word in ["calendar", "holidays", "team calendar", "out"]):
            plan.append("Use calendar_check to view calendar and holidays")
        elif any(
            word in query for word in ["request", "status", "approval", "pending", "submitted"]
        ):
            plan.append("Use leave_status to check request status")
        elif any(word in query for word in ["when can", "can i take", "book", "submit"]):
            plan.append("Use balance_calculator to check balance")
            plan.append("Remind user to submit via HR portal")
        else:
            # Default: check balance and status
            plan.append("Use balance_calculator to get balance")
            plan.append("Use leave_status to check recent requests")

        state["plan"] = plan
        state["current_step"] = 0
        state.setdefault("reasoning_trace", []).append(f"Created leave plan with {len(plan)} steps")
        logger.info(f"PLAN: {plan}")

        return state

    def _finish_node(self, state: BaseAgentState) -> BaseAgentState:
        """
        Synthesize final answer with leave submission note.

        Overrides base implementation to add read-only note to responses.

        Args:
            state: Current agent state

        Returns:
            Updated state with final answer including submission note
        """
        # Call parent finish node
        state = super()._finish_node(state)

        # Add read-only note to final answer
        final_answer = state.get("final_answer", "")

        # Only add note if it's not already there
        if "submit" in final_answer.lower() or "request" in final_answer.lower():
            note = (
                "\n\n---\n"
                "To submit a new leave request, please use the HR portal at [portal URL]. "
                "Phase 1 of the agent system is read-only for leave management."
            )
            state["final_answer"] = final_answer + note
            logger.info("FINISH: Added leave submission note to response")

        return state


# Register agent class for discovery
__all__ = ["LeaveAgent"]

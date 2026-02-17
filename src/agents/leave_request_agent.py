"""
WRITE-002: Leave Request Submission Agent
Leave Request Submission (Write Mode) Agent for HR multi-agent platform.

Extends BaseAgent to handle leave request workflows including submission,
approval, cancellation, and leave balance management with RBAC enforcement.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from src.agents.base_agent import BaseAgent, BaseAgentState, UserContext
from src.core.rbac import check_permission, get_data_scope, DataScope
from src.core.workflow_engine import WorkflowEngine, WorkflowTemplate, ApprovalMode

logger = logging.getLogger(__name__)


class LeaveType(str, Enum):
    """Leave request type categories."""

    VACATION = "vacation"
    SICK = "sick"
    PERSONAL = "personal"
    PARENTAL = "parental"
    BEREAVEMENT = "bereavement"
    JURY_DUTY = "jury_duty"
    MILITARY = "military"
    UNPAID = "unpaid"


class LeaveRequestStatus(str, Enum):
    """Leave request lifecycle status."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class LeaveBalance:
    """Employee leave balance tracking."""

    employee_id: str
    leave_type: LeaveType
    total_available: float  # Days available
    used: float  # Days used
    pending: float  # Days pending approval
    remaining: float = field(init=False)

    def __post_init__(self) -> None:
        """Calculate remaining balance."""
        self.remaining = self.total_available - self.used - self.pending


@dataclass
class LeaveRequest:
    """Leave request submission with validation."""

    request_id: str = field(default_factory=lambda: str(uuid4()))
    employee_id: str = ""
    leave_type: LeaveType = LeaveType.VACATION
    start_date: datetime = field(default_factory=datetime.utcnow)
    end_date: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    status: LeaveRequestStatus = LeaveRequestStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    days_requested: float = field(init=False)
    manager_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Calculate days and validate."""
        self.days_requested = self._calculate_business_days()
        self._validate()

    def _calculate_business_days(self) -> float:
        """Calculate business days between dates (excluding weekends)."""
        if self.start_date > self.end_date:
            return 0.0

        current = self.start_date
        business_days = 0

        while current <= self.end_date:
            # 0=Monday, 5=Saturday, 6=Sunday
            if current.weekday() < 5:
                business_days += 1
            current += timedelta(days=1)

        return float(business_days)

    def _validate(self) -> None:
        """Validate leave request constraints."""
        if not self.employee_id:
            raise ValueError("Employee ID is required")

        if self.start_date > self.end_date:
            raise ValueError("Start date must be before or equal to end date")

        if self.days_requested <= 0:
            raise ValueError("Request must span at least one business day")

        if self.days_requested > 365:
            raise ValueError("Cannot request more than 365 days")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "employee_id": self.employee_id,
            "leave_type": self.leave_type.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "reason": self.reason,
            "status": self.status.value,
            "days_requested": self.days_requested,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
        }


class LeaveRequestAgent(BaseAgent):
    """
    Leave Request Submission Agent for HR platform.

    Handles:
    - Leave request submission and validation
    - Leave balance checking and deduction
    - Manager approval workflow
    - Team calendar conflict detection
    - Leave cancellation
    - Leave history retrieval

    Tools:
    - submit_leave_request: Submit new leave request
    - check_leave_balance: Get available leave balance
    - get_team_calendar: Check team availability
    - cancel_leave: Cancel approved leave request
    - approve_leave_request: Manager approval
    - get_leave_history: Retrieve past requests
    """

    def __init__(self, llm: Any = None, workflow_engine: Optional[WorkflowEngine] = None):
        """
        Initialize Leave Request Agent.

        Args:
            llm: Language model instance
            workflow_engine: Workflow engine for approval workflows
        """
        self.llm = llm
        self.workflow_engine = workflow_engine or WorkflowEngine()
        self.leave_requests: Dict[str, LeaveRequest] = {}
        self.leave_balances: Dict[str, Dict[LeaveType, LeaveBalance]] = {}
        self.team_calendar: Dict[str, List[LeaveRequest]] = {}
        self.graph = self._build_graph()
        self._initialize_approval_workflow()

    def _initialize_approval_workflow(self) -> None:
        """Initialize leave approval workflow template."""
        template = WorkflowTemplate(
            name="Leave Request Approval",
            entity_type="leave_request",
            steps_config=[
                {
                    "approver_role": "manager",
                    "escalate_after_hours": 48,
                    "next_level_role": "hr_generalist",
                }
            ],
            approval_mode=ApprovalMode.SEQUENTIAL,
        )
        self.leave_approval_template_id = self.workflow_engine.register_template(template)

    def get_tools(self) -> Dict[str, Any]:
        """Return available tools for this agent."""
        return {
            "submit_leave_request": self._tool_submit_leave_request,
            "check_leave_balance": self._tool_check_leave_balance,
            "get_team_calendar": self._tool_get_team_calendar,
            "cancel_leave": self._tool_cancel_leave,
            "approve_leave_request": self._tool_approve_leave_request,
            "get_leave_history": self._tool_get_leave_history,
        }

    def get_system_prompt(self) -> str:
        """Get system prompt for leave request agent."""
        return """You are an HR Leave Request Agent. Your responsibilities:
1. Help employees submit leave requests
2. Validate leave balance and dates
3. Check for calendar conflicts
4. Support manager approval workflows
5. Handle leave cancellations
6. Provide leave history

Always:
- Validate dates and business days
- Check leave balance before submission
- Detect team calendar conflicts
- Enforce RBAC policies
- Maintain audit trail of all changes
- Provide clear feedback on request status"""

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "leave_request"

    # ==================== Tool Implementations ====================

    def _tool_submit_leave_request(self, query: str) -> Dict[str, Any]:
        """
        Submit a new leave request.

        Args:
            query: Query string with request details

        Returns:
            Dict with request_id, status, and any validation errors
        """
        logger.info(f"TOOL: submit_leave_request: {query[:100]}...")

        try:
            # Parse request details from query
            import json
            import re

            # Extract JSON-like content from query
            match = re.search(r"\{[^{}]*\}", query)
            if not match:
                return {
                    "success": False,
                    "error": "Invalid request format. Expected JSON with: employee_id, leave_type, start_date, end_date, reason",
                }

            request_data = json.loads(match.group(0))

            # Parse dates
            start_date = datetime.fromisoformat(request_data.get("start_date", ""))
            end_date = datetime.fromisoformat(request_data.get("end_date", ""))

            # Create leave request
            leave_req = LeaveRequest(
                employee_id=request_data.get("employee_id", ""),
                leave_type=LeaveType(request_data.get("leave_type", "vacation")),
                start_date=start_date,
                end_date=end_date,
                reason=request_data.get("reason", ""),
                manager_id=request_data.get("manager_id"),
            )

            # Check leave balance
            balance_info = self._check_balance_internal(
                leave_req.employee_id, leave_req.leave_type, leave_req.days_requested
            )

            if not balance_info["sufficient"]:
                return {
                    "success": False,
                    "error": f"Insufficient leave balance. Available: {balance_info['remaining']} days, Requested: {leave_req.days_requested}",
                }

            # Check for conflicts
            conflicts = self._check_conflicts_internal(leave_req)
            if conflicts:
                return {
                    "success": False,
                    "error": f"Calendar conflicts detected: {conflicts}",
                    "conflicts": conflicts,
                }

            # Store request
            leave_req.status = LeaveRequestStatus.SUBMITTED
            leave_req.submitted_at = datetime.utcnow()
            self.leave_requests[leave_req.request_id] = leave_req

            # Create approval workflow
            workflow_id = self.workflow_engine.create_workflow(
                template_id=self.leave_approval_template_id,
                entity_type="leave_request",
                entity_id=leave_req.request_id,
                created_by=leave_req.employee_id,
            )

            self.workflow_engine.submit_for_approval(workflow_id)
            leave_req.status = LeaveRequestStatus.PENDING_APPROVAL
            leave_req.metadata["workflow_id"] = workflow_id

            # Update balance with pending days
            self._update_pending_balance(
                leave_req.employee_id,
                leave_req.leave_type,
                leave_req.days_requested,
            )

            logger.info(f"Leave request submitted: {leave_req.request_id}")

            return {
                "success": True,
                "request_id": leave_req.request_id,
                "status": leave_req.status.value,
                "days_requested": leave_req.days_requested,
                "workflow_id": workflow_id,
            }

        except Exception as e:
            logger.error(f"TOOL: submit_leave_request failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _tool_check_leave_balance(self, query: str) -> Dict[str, Any]:
        """
        Check leave balance for employee.

        Args:
            query: Query with employee_id and optional leave_type

        Returns:
            Dict with balance information
        """
        logger.info(f"TOOL: check_leave_balance: {query[:100]}...")

        try:
            import re
            import json

            match = re.search(r"\{[^{}]*\}", query)
            if not match:
                return {"success": False, "error": "Invalid format. Expected JSON with employee_id"}

            data = json.loads(match.group(0))
            employee_id = data.get("employee_id", "")

            if not employee_id:
                return {"success": False, "error": "employee_id required"}

            # Get or initialize balances
            if employee_id not in self.leave_balances:
                self._initialize_balances(employee_id)

            balances = self.leave_balances[employee_id]

            result = {
                "success": True,
                "employee_id": employee_id,
                "balances": {
                    leave_type.value: {
                        "total_available": balance.total_available,
                        "used": balance.used,
                        "pending": balance.pending,
                        "remaining": balance.remaining,
                    }
                    for leave_type, balance in balances.items()
                },
            }

            return result

        except Exception as e:
            logger.error(f"TOOL: check_leave_balance failed: {e}")
            return {"success": False, "error": str(e)}

    def _tool_get_team_calendar(self, query: str) -> Dict[str, Any]:
        """
        Get team calendar with leave requests.

        Args:
            query: Query with manager_id and optional date range

        Returns:
            Dict with team member leave schedules
        """
        logger.info(f"TOOL: get_team_calendar: {query[:100]}...")

        try:
            import re
            import json

            match = re.search(r"\{[^{}]*\}", query)
            if not match:
                return {"success": False, "error": "Invalid format"}

            data = json.loads(match.group(0))
            manager_id = data.get("manager_id", "")

            calendar_data = []

            # Return team calendar
            for req in self.leave_requests.values():
                if req.status in [LeaveRequestStatus.APPROVED, LeaveRequestStatus.PENDING_APPROVAL]:
                    calendar_data.append(
                        {
                            "employee_id": req.employee_id,
                            "leave_type": req.leave_type.value,
                            "start_date": req.start_date.isoformat(),
                            "end_date": req.end_date.isoformat(),
                            "status": req.status.value,
                        }
                    )

            return {
                "success": True,
                "manager_id": manager_id,
                "calendar": calendar_data,
                "total_on_leave": len(calendar_data),
            }

        except Exception as e:
            logger.error(f"TOOL: get_team_calendar failed: {e}")
            return {"success": False, "error": str(e)}

    def _tool_cancel_leave(self, query: str) -> Dict[str, Any]:
        """
        Cancel an approved or pending leave request.

        Args:
            query: Query with request_id and reason

        Returns:
            Dict with cancellation status
        """
        logger.info(f"TOOL: cancel_leave: {query[:100]}...")

        try:
            import re
            import json

            match = re.search(r"\{[^{}]*\}", query)
            if not match:
                return {"success": False, "error": "Invalid format"}

            data = json.loads(match.group(0))
            request_id = data.get("request_id", "")

            if request_id not in self.leave_requests:
                return {"success": False, "error": f"Request not found: {request_id}"}

            leave_req = self.leave_requests[request_id]

            if leave_req.status == LeaveRequestStatus.CANCELLED:
                return {"success": False, "error": "Request already cancelled"}

            # Revert pending balance
            self._update_pending_balance(
                leave_req.employee_id,
                leave_req.leave_type,
                -leave_req.days_requested,
            )

            leave_req.status = LeaveRequestStatus.CANCELLED
            leave_req.metadata["cancelled_at"] = datetime.utcnow().isoformat()
            leave_req.metadata["cancellation_reason"] = data.get("reason", "")

            logger.info(f"Leave request cancelled: {request_id}")

            return {
                "success": True,
                "request_id": request_id,
                "status": leave_req.status.value,
            }

        except Exception as e:
            logger.error(f"TOOL: cancel_leave failed: {e}")
            return {"success": False, "error": str(e)}

    def _tool_approve_leave_request(self, query: str) -> Dict[str, Any]:
        """
        Approve a leave request (manager/HR only).

        Args:
            query: Query with request_id and approver info

        Returns:
            Dict with approval status
        """
        logger.info(f"TOOL: approve_leave_request: {query[:100]}...")

        try:
            import re
            import json

            match = re.search(r"\{[^{}]*\}", query)
            if not match:
                return {"success": False, "error": "Invalid format"}

            data = json.loads(match.group(0))
            request_id = data.get("request_id", "")
            approver_id = data.get("approver_id", "")
            approver_role = data.get("approver_role", "manager")

            if request_id not in self.leave_requests:
                return {"success": False, "error": f"Request not found: {request_id}"}

            # RBAC check
            if not check_permission(approver_role.lower(), "leave", "approve"):
                return {"success": False, "error": f"Role {approver_role} cannot approve leave"}

            leave_req = self.leave_requests[request_id]

            if leave_req.status != LeaveRequestStatus.PENDING_APPROVAL:
                return {
                    "success": False,
                    "error": f"Cannot approve request in {leave_req.status.value} status",
                }

            # Update workflow
            workflow_id = leave_req.metadata.get("workflow_id")
            if workflow_id:
                success, msg = self.workflow_engine.approve_step(
                    workflow_id,
                    approver_id,
                    approver_role,
                    data.get("comments", ""),
                )

            # Mark as approved
            leave_req.status = LeaveRequestStatus.APPROVED
            leave_req.approved_at = datetime.utcnow()
            leave_req.approved_by = approver_id

            # Update used balance
            self._update_used_balance(
                leave_req.employee_id,
                leave_req.leave_type,
                leave_req.days_requested,
            )

            logger.info(f"Leave request approved: {request_id}")

            return {
                "success": True,
                "request_id": request_id,
                "status": leave_req.status.value,
                "approved_by": approver_id,
            }

        except Exception as e:
            logger.error(f"TOOL: approve_leave_request failed: {e}")
            return {"success": False, "error": str(e)}

    def _tool_get_leave_history(self, query: str) -> Dict[str, Any]:
        """
        Get leave history for employee.

        Args:
            query: Query with employee_id and optional date range

        Returns:
            Dict with historical leave requests
        """
        logger.info(f"TOOL: get_leave_history: {query[:100]}...")

        try:
            import re
            import json

            match = re.search(r"\{[^{}]*\}", query)
            if not match:
                return {"success": False, "error": "Invalid format"}

            data = json.loads(match.group(0))
            employee_id = data.get("employee_id", "")

            if not employee_id:
                return {"success": False, "error": "employee_id required"}

            history = [
                req.to_dict()
                for req in self.leave_requests.values()
                if req.employee_id == employee_id
            ]

            return {
                "success": True,
                "employee_id": employee_id,
                "history": history,
                "total_requests": len(history),
            }

        except Exception as e:
            logger.error(f"TOOL: get_leave_history failed: {e}")
            return {"success": False, "error": str(e)}

    # ==================== Internal Helpers ====================

    def _initialize_balances(self, employee_id: str) -> None:
        """Initialize leave balances for employee."""
        default_balances = {
            LeaveType.VACATION: 20.0,
            LeaveType.SICK: 10.0,
            LeaveType.PERSONAL: 5.0,
            LeaveType.PARENTAL: 90.0,
            LeaveType.BEREAVEMENT: 5.0,
            LeaveType.JURY_DUTY: 0.0,
            LeaveType.MILITARY: 0.0,
            LeaveType.UNPAID: float("inf"),
        }

        self.leave_balances[employee_id] = {
            leave_type: LeaveBalance(
                employee_id=employee_id,
                leave_type=leave_type,
                total_available=balance,
                used=0.0,
                pending=0.0,
            )
            for leave_type, balance in default_balances.items()
        }

    def _check_balance_internal(
        self,
        employee_id: str,
        leave_type: LeaveType,
        days_requested: float,
    ) -> Dict[str, Any]:
        """Check if employee has sufficient leave balance."""
        if employee_id not in self.leave_balances:
            self._initialize_balances(employee_id)

        balance = self.leave_balances[employee_id][leave_type]
        sufficient = balance.remaining >= days_requested

        return {
            "sufficient": sufficient,
            "remaining": balance.remaining,
            "requested": days_requested,
        }

    def _check_conflicts_internal(self, leave_req: LeaveRequest) -> List[str]:
        """Check for calendar conflicts with other approvals."""
        conflicts = []

        for other_req in self.leave_requests.values():
            if (
                other_req.employee_id == leave_req.employee_id
                and other_req.status
                in [LeaveRequestStatus.APPROVED, LeaveRequestStatus.PENDING_APPROVAL]
                and other_req.request_id != leave_req.request_id
            ):
                # Check date overlap
                if not (
                    leave_req.end_date < other_req.start_date
                    or leave_req.start_date > other_req.end_date
                ):
                    conflicts.append(f"Overlaps with {other_req.request_id}")

        return conflicts

    def _update_pending_balance(
        self,
        employee_id: str,
        leave_type: LeaveType,
        days: float,
    ) -> None:
        """Update pending balance."""
        if employee_id not in self.leave_balances:
            self._initialize_balances(employee_id)

        balance = self.leave_balances[employee_id][leave_type]
        balance.pending += days
        balance.remaining = balance.total_available - balance.used - balance.pending

    def _update_used_balance(
        self,
        employee_id: str,
        leave_type: LeaveType,
        days: float,
    ) -> None:
        """Update used balance."""
        if employee_id not in self.leave_balances:
            self._initialize_balances(employee_id)

        balance = self.leave_balances[employee_id][leave_type]
        balance.pending -= days
        balance.used += days
        balance.remaining = balance.total_available - balance.used - balance.pending

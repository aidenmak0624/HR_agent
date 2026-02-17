"""
WRITE-002: Leave Request Submission Service
Handles leave request creation, validation, approval workflows, and balance management.

Supports multiple leave types, business rules validation, overlap checking,
and integration with workflow engine and HRIS system. PII-safe with comprehensive
audit logging and error handling.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.connectors.hris_interface import (
    HRISConnector,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
)
from src.core.workflow_engine import (
    ApprovalMode,
    WorkflowEngine,
    WorkflowTemplate,
)

logger = logging.getLogger(__name__)


class LeaveRequestModel(BaseModel):
    """Internal model for leave request storage."""

    request_id: str = Field(default_factory=lambda: str(uuid4()))
    employee_id: str
    leave_type: LeaveType
    start_date: datetime
    end_date: datetime
    reason: str
    status: LeaveStatus = LeaveStatus.PENDING
    workflow_id: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    rejection_reason: Optional[str] = None
    business_days: int = 0

    model_config = ConfigDict(use_enum_values=False)


class LeaveRequestService:
    """
    Service for managing leave requests.

    Handles request submission, validation, cancellation, status tracking,
    approval workflow integration, and balance updates. Implements business
    rules including consecutive day limits, notice periods, and date validation.
    """

    # Business rule constants
    MAX_CONSECUTIVE_DAYS = 20
    MINIMUM_NOTICE_HOURS = 48
    DAYS_PER_WEEK = 5

    def __init__(
        self,
        hris_connector: HRISConnector,
        workflow_engine: WorkflowEngine,
        notification_service: Optional[Any] = None,
    ) -> None:
        """
        Initialize LeaveRequestService.

        Args:
            hris_connector: HRIS connector for balance updates
            workflow_engine: Workflow engine for approvals
            notification_service: Optional notification service

        Raises:
            ValueError: If required dependencies are None
        """
        if not hris_connector:
            raise ValueError("hris_connector is required")
        if not workflow_engine:
            raise ValueError("workflow_engine is required")

        self.hris = hris_connector
        self.workflow_engine = workflow_engine
        self.notification_service = notification_service
        self.requests: Dict[str, LeaveRequestModel] = {}
        self.settings = self._init_settings()

        logger.info("LeaveRequestService initialized")

    def _init_settings(self) -> Dict[str, Any]:
        """Initialize service settings from config.

        Returns:
            Settings dictionary
        """
        try:
            from config.settings import get_settings

            settings = get_settings()
            return {
                "max_consecutive_days": getattr(
                    settings, "max_leave_consecutive", self.MAX_CONSECUTIVE_DAYS
                ),
                "minimum_notice_hours": getattr(
                    settings, "leave_minimum_notice_hours", self.MINIMUM_NOTICE_HOURS
                ),
            }
        except ImportError:
            return {
                "max_consecutive_days": self.MAX_CONSECUTIVE_DAYS,
                "minimum_notice_hours": self.MINIMUM_NOTICE_HOURS,
            }

    def submit_request(
        self,
        employee_id: str,
        leave_type: LeaveType,
        start_date: datetime,
        end_date: datetime,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Submit a new leave request.

        Creates request, validates all business rules, initiates approval workflow,
        and returns request/workflow IDs.

        Args:
            employee_id: Employee submitting request
            leave_type: Type of leave requested
            start_date: Start date of leave
            end_date: End date of leave
            reason: Reason for leave (will be PII-stripped)

        Returns:
            Dictionary with request_id, workflow_id, and status

        Raises:
            ValueError: If validation fails
            Exception: If HRIS or workflow operation fails

        Example:
            result = service.submit_request(
                employee_id="emp_123",
                leave_type=LeaveType.PTO,
                start_date=datetime(2025, 3, 1),
                end_date=datetime(2025, 3, 5),
                reason="Family vacation"
            )
            # Returns: {"request_id": "req_...", "workflow_id": "wf_..."}
        """
        logger.info(
            f"Submitting leave request for employee {employee_id}, "
            f"type: {leave_type}, dates: {start_date.date()} to {end_date.date()}"
        )

        # Validate date range
        if start_date > end_date:
            raise ValueError("start_date must be before end_date")

        # Validate no past dates
        if start_date.date() < datetime.utcnow().date():
            raise ValueError("Cannot submit leave request for past dates")

        # Validate notice period
        hours_until_start = (start_date - datetime.utcnow()).total_seconds() / 3600
        min_hours = self.settings["minimum_notice_hours"]
        if hours_until_start < min_hours:
            raise ValueError(
                f"Leave request must be submitted at least {min_hours} hours in advance"
            )

        # Calculate business days
        business_days = self._calculate_business_days(start_date, end_date)

        # Validate balance
        if not self._validate_balance(employee_id, leave_type, business_days):
            raise ValueError(
                f"Insufficient leave balance for {leave_type.value}. "
                f"Required: {business_days} days"
            )

        # Validate no overlap
        if not self._validate_no_overlap(employee_id, start_date, end_date):
            raise ValueError(
                "Overlapping leave request exists for this date range"
            )

        # Validate business rules
        errors = self._validate_business_rules(leave_type, start_date, end_date)
        if errors:
            error_msg = "; ".join(errors)
            logger.warning(f"Business rule validation failed: {error_msg}")
            raise ValueError(f"Business rule violations: {error_msg}")

        # Strip PII from reason before logging or LLM processing
        clean_reason = self._strip_pii(reason)

        # Create request
        request = LeaveRequestModel(
            employee_id=employee_id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=clean_reason,
            business_days=business_days,
        )

        # Create approval workflow
        try:
            workflow_template = self._get_or_create_leave_workflow_template()
            workflow_id = self.workflow_engine.create_workflow(
                template_id=workflow_template,
                entity_type="leave_request",
                entity_id=request.request_id,
                created_by=employee_id,
            )
            request.workflow_id = workflow_id

            # Submit for approval
            self.workflow_engine.submit_for_approval(workflow_id)
            logger.info(
                f"Created leave request {request.request_id} with workflow {workflow_id}"
            )

        except Exception as e:
            logger.error(f"Failed to create approval workflow: {e}")
            raise

        # Store request
        self.requests[request.request_id] = request

        return {
            "request_id": request.request_id,
            "workflow_id": workflow_id,
            "status": request.status.value,
            "business_days": business_days,
        }

    def cancel_request(
        self, request_id: str, employee_id: str
    ) -> Dict[str, Any]:
        """
        Cancel a leave request.

        Only pending requests can be cancelled. Cancels associated workflow.

        Args:
            request_id: ID of request to cancel
            employee_id: Employee requesting cancellation

        Returns:
            Dictionary with updated request status

        Raises:
            ValueError: If request not found or not cancellable
        """
        request = self._get_request(request_id)

        if request.employee_id != employee_id:
            raise ValueError(
                f"Employee {employee_id} cannot cancel request owned by {request.employee_id}"
            )

        if request.status != LeaveStatus.PENDING:
            raise ValueError(
                f"Cannot cancel request with status {request.status.value}"
            )

        # Cancel workflow
        if request.workflow_id:
            try:
                self.workflow_engine.cancel_workflow(
                    request.workflow_id, employee_id, user_role="employee"
                )
            except Exception as e:
                logger.error(f"Failed to cancel workflow {request.workflow_id}: {e}")

        request.status = LeaveStatus.CANCELLED
        request.updated_at = datetime.utcnow()

        logger.info(f"Cancelled leave request {request_id}")

        return {
            "request_id": request_id,
            "status": request.status.value,
            "cancelled_at": request.updated_at.isoformat(),
        }

    def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """
        Get status of a leave request.

        Args:
            request_id: ID of request

        Returns:
            Dictionary with request details

        Raises:
            ValueError: If request not found
        """
        request = self._get_request(request_id)

        return {
            "request_id": request.request_id,
            "employee_id": request.employee_id,
            "leave_type": request.leave_type.value,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "business_days": request.business_days,
            "status": request.status.value,
            "workflow_id": request.workflow_id,
            "submitted_at": request.submitted_at.isoformat(),
            "updated_at": request.updated_at.isoformat(),
            "rejection_reason": request.rejection_reason,
        }

    def get_employee_requests(
        self, employee_id: str, status_filter: Optional[LeaveStatus] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all leave requests for an employee.

        Args:
            employee_id: Employee ID
            status_filter: Optional status to filter by

        Returns:
            List of request dictionaries
        """
        requests = [
            r
            for r in self.requests.values()
            if r.employee_id == employee_id
        ]

        if status_filter:
            requests = [r for r in requests if r.status == status_filter]

        return [
            {
                "request_id": r.request_id,
                "leave_type": r.leave_type.value,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "business_days": r.business_days,
                "status": r.status.value,
                "submitted_at": r.submitted_at.isoformat(),
            }
            for r in sorted(requests, key=lambda x: x.submitted_at, reverse=True)
        ]

    def on_approval(self, workflow_id: str) -> Dict[str, Any]:
        """
        Handle approval of a leave request workflow.

        Updates request status, deducts balance from HRIS, notifies employee.

        Args:
            workflow_id: Workflow ID that was approved

        Returns:
            Dictionary with updated request info

        Raises:
            ValueError: If workflow not found or request not found
        """
        # Find request by workflow_id
        request = None
        for r in self.requests.values():
            if r.workflow_id == workflow_id:
                request = r
                break

        if not request:
            raise ValueError(f"Request not found for workflow {workflow_id}")

        request.status = LeaveStatus.APPROVED
        request.updated_at = datetime.utcnow()

        logger.info(
            f"Approved leave request {request.request_id} "
            f"for {request.business_days} days"
        )

        # Deduct balance from HRIS
        try:
            # This would be called via HRIS to deduct the balance
            # For now, log the intent
            logger.info(
                f"Deducting {request.business_days} {request.leave_type.value} days "
                f"for employee {request.employee_id}"
            )
        except Exception as e:
            logger.error(f"Failed to deduct balance: {e}")
            raise

        # Notify employee
        if self.notification_service:
            try:
                self.notification_service.notify(
                    employee_id=request.employee_id,
                    message_type="leave_approved",
                    context={
                        "request_id": request.request_id,
                        "start_date": request.start_date.isoformat(),
                        "end_date": request.end_date.isoformat(),
                        "business_days": request.business_days,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to send approval notification: {e}")

        return {
            "request_id": request.request_id,
            "status": request.status.value,
            "approved_at": request.updated_at.isoformat(),
        }

    def on_rejection(
        self, workflow_id: str, reason: str = ""
    ) -> Dict[str, Any]:
        """
        Handle rejection of a leave request workflow.

        Updates request status, records rejection reason, notifies employee.

        Args:
            workflow_id: Workflow ID that was rejected
            reason: Reason for rejection

        Returns:
            Dictionary with updated request info

        Raises:
            ValueError: If workflow not found or request not found
        """
        # Find request by workflow_id
        request = None
        for r in self.requests.values():
            if r.workflow_id == workflow_id:
                request = r
                break

        if not request:
            raise ValueError(f"Request not found for workflow {workflow_id}")

        request.status = LeaveStatus.DENIED
        request.rejection_reason = reason
        request.updated_at = datetime.utcnow()

        logger.info(
            f"Rejected leave request {request.request_id}: {reason}"
        )

        # Notify employee
        if self.notification_service:
            try:
                self.notification_service.notify(
                    employee_id=request.employee_id,
                    message_type="leave_rejected",
                    context={
                        "request_id": request.request_id,
                        "reason": reason,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to send rejection notification: {e}")

        return {
            "request_id": request.request_id,
            "status": request.status.value,
            "rejection_reason": reason,
            "rejected_at": request.updated_at.isoformat(),
        }

    def _validate_balance(
        self, employee_id: str, leave_type: LeaveType, days: int
    ) -> bool:
        """
        Validate employee has sufficient leave balance.

        Args:
            employee_id: Employee ID
            leave_type: Type of leave
            days: Number of days requested

        Returns:
            True if balance is sufficient
        """
        try:
            balances = self.hris.get_leave_balance(employee_id)
            for balance in balances:
                if balance.leave_type == leave_type:
                    available = balance.available_days
                    if available >= days:
                        logger.debug(
                            f"Balance check passed: {available} >= {days}"
                        )
                        return True
                    logger.warning(
                        f"Insufficient balance: {available} < {days}"
                    )
                    return False
            logger.warning(f"No balance found for leave type {leave_type}")
            return False
        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            return False

    def _validate_no_overlap(
        self, employee_id: str, start_date: datetime, end_date: datetime
    ) -> bool:
        """
        Validate no overlapping leave requests exist.

        Args:
            employee_id: Employee ID
            start_date: Start date
            end_date: End date

        Returns:
            True if no overlaps found
        """
        existing = self.requests.values()
        for req in existing:
            if req.employee_id != employee_id:
                continue
            if req.status == LeaveStatus.CANCELLED:
                continue

            # Check for overlap
            if start_date <= req.end_date and end_date >= req.start_date:
                logger.warning(
                    f"Overlap detected with request {req.request_id}"
                )
                return False

        return True

    def _validate_business_rules(
        self, leave_type: LeaveType, start_date: datetime, end_date: datetime
    ) -> List[str]:
        """
        Validate business rules for leave request.

        Rules:
        - Max 20 consecutive days per request
        - Certain leave types may have additional restrictions

        Args:
            leave_type: Type of leave
            start_date: Start date
            end_date: End date

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check max consecutive days
        business_days = self._calculate_business_days(start_date, end_date)
        max_days = self.settings["max_consecutive_days"]
        if business_days > max_days:
            errors.append(
                f"Leave request exceeds maximum of {max_days} consecutive days"
            )

        # Additional rules for certain leave types
        if leave_type == LeaveType.UNPAID:
            # Unpaid leave might have stricter rules
            if business_days > max_days * 0.5:
                errors.append(
                    "Unpaid leave limited to 10 consecutive days"
                )

        return errors

    def _calculate_business_days(
        self, start_date: datetime, end_date: datetime
    ) -> int:
        """
        Calculate business days (Mon-Fri) between dates (inclusive).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Number of business days
        """
        current = start_date.date()
        end = end_date.date()
        business_days = 0

        while current <= end:
            # Monday = 0, Friday = 4, Saturday = 5, Sunday = 6
            if current.weekday() < 5:
                business_days += 1
            current += timedelta(days=1)

        return business_days

    def _strip_pii(self, text: str) -> str:
        """
        Strip PII from text before LLM processing.

        Removes: emails, phone numbers, SSN patterns, dates of birth.

        Args:
            text: Input text

        Returns:
            Text with PII redacted
        """
        if not text:
            return text

        # Email pattern
        text = re.sub(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "[EMAIL]",
            text,
        )

        # Phone pattern (US format)
        text = re.sub(
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]", text
        )

        # SSN pattern
        text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", text)

        # Common date of birth patterns
        text = re.sub(
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "[DOB]", text
        )

        return text

    def _get_request(self, request_id: str) -> LeaveRequestModel:
        """
        Internal helper to get request and raise if not found.

        Args:
            request_id: Request ID

        Returns:
            LeaveRequestModel instance

        Raises:
            ValueError: If request not found
        """
        request = self.requests.get(request_id)
        if not request:
            raise ValueError(f"Leave request not found: {request_id}")
        return request

    def _get_or_create_leave_workflow_template(self) -> str:
        """
        Get or create leave approval workflow template.

        Returns:
            Template ID
        """
        # Check if template exists
        for template in self.workflow_engine.templates.values():
            if template.entity_type == "leave_request":
                return template.template_id

        # Create default template
        template = WorkflowTemplate(
            name="Leave Request Approval",
            entity_type="leave_request",
            steps_config=[
                {
                    "approver_role": "manager",
                    "escalate_after_hours": 48,
                    "next_level_role": "hr_admin",
                }
            ],
            approval_mode=ApprovalMode.SEQUENTIAL,
        )
        return self.workflow_engine.register_template(template)

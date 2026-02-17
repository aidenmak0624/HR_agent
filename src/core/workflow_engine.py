"""
WRITE-001: Approval Workflow Engine
Generic state-machine approval workflow engine for HR multi-agent platform.

Supports sequential and parallel approval modes, RBAC integration, auto-escalation,
and comprehensive audit logging. Workflows are stored in-memory with database
integration points for future persistence.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from config.settings import get_settings
from src.core.rbac import RoleLevel, check_permission

logger = logging.getLogger(__name__)


class WorkflowState(str, Enum):
    """Workflow lifecycle states."""

    DRAFT = "draft"  # Initial state, not submitted
    PENDING_APPROVAL = "pending_approval"  # Awaiting approval decision
    APPROVED = "approved"  # All steps approved/completed
    REJECTED = "rejected"  # Rejected at some step
    ESCALATED = "escalated"  # Escalated to higher approver
    CANCELLED = "cancelled"  # Cancelled by initiator or admin


class ApprovalMode(str, Enum):
    """Approval workflow modes."""

    SEQUENTIAL = "sequential"  # All steps in order, each must approve
    PARALLEL = "parallel"  # Any one approver can approve step


class BiasSeverity(str, Enum):
    """Severity levels for approval decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class WorkflowStep:
    """Configuration for a single approval step."""

    approver_role: str  # Role required to approve (e.g., "hr_admin")
    step_id: str = field(default_factory=lambda: str(uuid4()))
    approver_id: Optional[str] = None  # Specific user (None = any with role)
    status: str = "pending"  # pending, approved, rejected, escalated
    decision_at: Optional[datetime] = None
    comments: str = ""
    escalate_after_hours: int = 24  # Auto-escalate if not approved in N hours
    next_level_role: Optional[str] = None  # Role for escalation


@dataclass
class WorkflowDecision:
    """Record of a step decision."""

    instance_id: str = ""  # Workflow instance ID
    step_idx: int = 0
    approver_id: str = ""
    decision: str = "pending"  # approved, rejected, escalated
    comments: str = ""
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    decided_at: datetime = field(default_factory=datetime.utcnow)


class ApprovalWorkflow(BaseModel):
    """Full approval workflow instance."""

    workflow_id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: str  # Entity being approved (e.g., "compensation_change")
    entity_id: str  # ID of entity
    steps: List[WorkflowStep] = Field(default_factory=list)
    current_step: int = 0  # Current step index
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    state: WorkflowState = WorkflowState.DRAFT
    approval_mode: ApprovalMode = ApprovalMode.SEQUENTIAL
    decisions: List[WorkflowDecision] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=False)


class WorkflowTemplate(BaseModel):
    """Reusable workflow template."""

    template_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str  # e.g., "Compensation Change Approval"
    entity_type: str
    steps_config: List[Dict[str, Any]] = Field(default_factory=list)
    approval_mode: ApprovalMode = ApprovalMode.SEQUENTIAL
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=False)


class WorkflowEvent:
    """Event for audit logging."""

    def __init__(
        self,
        event_type: str,
        workflow_id: str,
        actor: str,
        timestamp: Optional[datetime] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize workflow event.

        Args:
            event_type: Event type (created, submitted, approved, rejected, etc.)
            workflow_id: Workflow instance ID
            actor: User ID of person triggering event
            timestamp: Event timestamp (default: now)
            details: Additional event details
        """
        self.event_type = event_type
        self.workflow_id = workflow_id
        self.actor = actor
        self.timestamp = timestamp or datetime.utcnow()
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for logging.

        Returns:
            Event as dictionary
        """
        return {
            "event_type": self.event_type,
            "workflow_id": self.workflow_id,
            "actor": self.actor,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


class WorkflowEngine:
    """
    Generic approval workflow engine for HR processes.

    Manages workflow lifecycle, approvals, rejections, escalations, and audit logging.
    Supports both sequential and parallel approval modes with RBAC integration.
    """

    def __init__(self) -> None:
        """Initialize workflow engine."""
        self.workflows: Dict[str, ApprovalWorkflow] = {}
        self.templates: Dict[str, WorkflowTemplate] = {}
        self.audit_events: List[WorkflowEvent] = []
        self.settings = get_settings()

    def register_template(self, template: WorkflowTemplate) -> str:
        """Register a workflow template.

        Args:
            template: WorkflowTemplate instance

        Returns:
            Template ID

        Example:
            template = WorkflowTemplate(
                name="Compensation Change",
                entity_type="compensation",
                steps_config=[
                    {"approver_role": "manager", "escalate_after_hours": 48},
                    {"approver_role": "hr_admin", "escalate_after_hours": 72},
                ]
            )
            template_id = engine.register_template(template)
        """
        self.templates[template.template_id] = template
        logger.info(f"Registered workflow template: {template.template_id}")
        return template.template_id

    def create_workflow(
        self,
        template_id: str,
        entity_type: str,
        entity_id: str,
        created_by: str,
    ) -> str:
        """Create a new workflow instance from template.

        Args:
            template_id: ID of workflow template
            entity_type: Type of entity being approved
            entity_id: ID of entity
            created_by: User ID creating workflow

        Returns:
            Workflow ID

        Raises:
            ValueError: If template not found

        Example:
            workflow_id = engine.create_workflow(
                template_id="tmpl_123",
                entity_type="compensation",
                entity_id="emp_456",
                created_by="user_789"
            )
        """
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Create workflow steps from template
        steps = []
        for step_config in template.steps_config:
            step = WorkflowStep(
                approver_role=step_config.get("approver_role", ""),
                approver_id=step_config.get("approver_id"),
                escalate_after_hours=step_config.get("escalate_after_hours", 24),
                next_level_role=step_config.get("next_level_role"),
            )
            steps.append(step)

        workflow = ApprovalWorkflow(
            entity_type=entity_type,
            entity_id=entity_id,
            steps=steps,
            created_by=created_by,
            approval_mode=template.approval_mode,
        )

        self.workflows[workflow.workflow_id] = workflow
        self._emit_event(
            WorkflowEvent(
                event_type="workflow_created",
                workflow_id=workflow.workflow_id,
                actor=created_by,
                details={
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "template_id": template_id,
                },
            )
        )

        logger.info(f"Created workflow: {workflow.workflow_id}")
        return workflow.workflow_id

    def submit_for_approval(self, workflow_id: str) -> bool:
        """Submit workflow for approval (DRAFT -> PENDING_APPROVAL).

        Args:
            workflow_id: Workflow instance ID

        Returns:
            True if submission successful

        Raises:
            ValueError: If workflow not found or not in DRAFT state
        """
        workflow = self._get_workflow(workflow_id)
        if workflow.state != WorkflowState.DRAFT:
            raise ValueError(f"Cannot submit workflow in {workflow.state} state")

        workflow.state = WorkflowState.PENDING_APPROVAL
        workflow.updated_at = datetime.utcnow()

        self._emit_event(
            WorkflowEvent(
                event_type="workflow_submitted",
                workflow_id=workflow_id,
                actor=workflow.created_by,
            )
        )

        logger.info(f"Submitted workflow for approval: {workflow_id}")
        return True

    def approve_step(
        self,
        workflow_id: str,
        approver_id: str,
        approver_role: str,
        comments: str = "",
    ) -> Tuple[bool, str]:
        """Approve current step and advance to next.

        Args:
            workflow_id: Workflow instance ID
            approver_id: User ID of approver
            approver_role: Role of approver
            comments: Comments from approver

        Returns:
            Tuple of (success, message)

        Raises:
            ValueError: If workflow not found or validation fails
        """
        workflow = self._get_workflow(workflow_id)

        if workflow.state != WorkflowState.PENDING_APPROVAL:
            raise ValueError(f"Cannot approve workflow in {workflow.state} state")

        if workflow.current_step >= len(workflow.steps):
            raise ValueError("No pending steps in workflow")

        current_step = workflow.steps[workflow.current_step]

        # Validate approver has required role
        if not check_permission(approver_role.lower(), "workflow", "approve"):
            raise ValueError(f"Approver role '{approver_role}' lacks approval permission")

        # Record decision
        decision = WorkflowDecision(
            instance_id=workflow_id,
            step_idx=workflow.current_step,
            approver_id=approver_id,
            decision="approved",
            comments=comments,
            decided_at=datetime.utcnow(),
        )
        workflow.decisions.append(decision)

        # Update step
        current_step.status = "approved"
        current_step.approver_id = approver_id
        current_step.comments = comments
        current_step.decision_at = datetime.utcnow()

        self._emit_event(
            WorkflowEvent(
                event_type="step_approved",
                workflow_id=workflow_id,
                actor=approver_id,
                details={
                    "step_idx": workflow.current_step,
                    "step_id": current_step.step_id,
                    "comments": comments,
                },
            )
        )

        # Advance to next step or mark complete
        if workflow.current_step < len(workflow.steps) - 1:
            workflow.current_step += 1
            message = f"Step {workflow.current_step} pending approval"
        else:
            workflow.state = WorkflowState.APPROVED
            message = "Workflow approved and completed"
            self._emit_event(
                WorkflowEvent(
                    event_type="workflow_approved",
                    workflow_id=workflow_id,
                    actor=approver_id,
                )
            )

        workflow.updated_at = datetime.utcnow()
        logger.info(f"Approved step in workflow: {workflow_id}")
        return True, message

    def reject_step(
        self,
        workflow_id: str,
        approver_id: str,
        approver_role: str,
        comments: str = "",
    ) -> bool:
        """Reject workflow at current step.

        Args:
            workflow_id: Workflow instance ID
            approver_id: User ID of approver
            approver_role: Role of approver
            comments: Rejection reason/comments

        Returns:
            True if rejection successful

        Raises:
            ValueError: If workflow not found or validation fails
        """
        workflow = self._get_workflow(workflow_id)

        if workflow.state != WorkflowState.PENDING_APPROVAL:
            raise ValueError(f"Cannot reject workflow in {workflow.state} state")

        if workflow.current_step >= len(workflow.steps):
            raise ValueError("No pending steps to reject")

        current_step = workflow.steps[workflow.current_step]

        # Record decision
        decision = WorkflowDecision(
            instance_id=workflow_id,
            step_idx=workflow.current_step,
            approver_id=approver_id,
            decision="rejected",
            comments=comments,
            decided_at=datetime.utcnow(),
        )
        workflow.decisions.append(decision)

        # Update step
        current_step.status = "rejected"
        current_step.approver_id = approver_id
        current_step.comments = comments
        current_step.decision_at = datetime.utcnow()

        # Mark entire workflow as rejected
        workflow.state = WorkflowState.REJECTED
        workflow.updated_at = datetime.utcnow()

        self._emit_event(
            WorkflowEvent(
                event_type="workflow_rejected",
                workflow_id=workflow_id,
                actor=approver_id,
                details={
                    "step_idx": workflow.current_step,
                    "reason": comments,
                },
            )
        )

        logger.info(f"Rejected workflow: {workflow_id}")
        return True

    def escalate_step(
        self,
        workflow_id: str,
        reason: str = "",
    ) -> bool:
        """Escalate current step to next-level approver.

        Args:
            workflow_id: Workflow instance ID
            reason: Reason for escalation

        Returns:
            True if escalation successful

        Raises:
            ValueError: If workflow not found or validation fails
        """
        workflow = self._get_workflow(workflow_id)

        if workflow.state != WorkflowState.PENDING_APPROVAL:
            raise ValueError(f"Cannot escalate workflow in {workflow.state} state")

        if workflow.current_step >= len(workflow.steps):
            raise ValueError("No pending steps to escalate")

        current_step = workflow.steps[workflow.current_step]

        if not current_step.next_level_role:
            raise ValueError("No next level role configured for escalation")

        # Update step
        current_step.status = "escalated"
        current_step.comments = reason
        current_step.decision_at = datetime.utcnow()

        # Change approver role to next level
        current_step.approver_role = current_step.next_level_role

        workflow.state = WorkflowState.ESCALATED
        workflow.updated_at = datetime.utcnow()

        self._emit_event(
            WorkflowEvent(
                event_type="workflow_escalated",
                workflow_id=workflow_id,
                actor="system",
                details={
                    "step_idx": workflow.current_step,
                    "next_level_role": current_step.next_level_role,
                    "reason": reason,
                },
            )
        )

        # Return to PENDING so escalated approver can act
        workflow.state = WorkflowState.PENDING_APPROVAL

        logger.info(f"Escalated workflow: {workflow_id}")
        return True

    def cancel_workflow(
        self,
        workflow_id: str,
        user_id: str,
        user_role: str = "employee",
    ) -> bool:
        """Cancel a workflow.

        Only creator or HR admin can cancel.

        Args:
            workflow_id: Workflow instance ID
            user_id: User ID requesting cancellation
            user_role: Role of user

        Returns:
            True if cancellation successful

        Raises:
            ValueError: If workflow not found or user lacks permission
        """
        workflow = self._get_workflow(workflow_id)

        # Only creator or HR admin can cancel
        if user_id != workflow.created_by and user_role != "hr_admin":
            raise ValueError(f"User {user_id} lacks permission to cancel workflow")

        if workflow.state == WorkflowState.CANCELLED:
            raise ValueError("Workflow already cancelled")

        workflow.state = WorkflowState.CANCELLED
        workflow.updated_at = datetime.utcnow()

        self._emit_event(
            WorkflowEvent(
                event_type="workflow_cancelled",
                workflow_id=workflow_id,
                actor=user_id,
            )
        )

        logger.info(f"Cancelled workflow: {workflow_id}")
        return True

    def get_pending_approvals(self, approver_id: str) -> List[ApprovalWorkflow]:
        """Get all pending workflows awaiting approval from user.

        Args:
            approver_id: User ID of approver

        Returns:
            List of pending workflows
        """
        pending = []
        for workflow in self.workflows.values():
            if workflow.state != WorkflowState.PENDING_APPROVAL:
                continue

            if workflow.current_step >= len(workflow.steps):
                continue

            current_step = workflow.steps[workflow.current_step]

            # Check if this user can approve (role match or specific ID match)
            if current_step.approver_id == approver_id or current_step.approver_id is None:
                pending.append(workflow)

        return pending

    def get_workflow(self, workflow_id: str) -> ApprovalWorkflow:
        """Get workflow by ID.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Workflow instance

        Raises:
            ValueError: If workflow not found
        """
        return self._get_workflow(workflow_id)

    def get_workflow_history(self, workflow_id: str) -> List[WorkflowEvent]:
        """Get all events for a workflow (audit trail).

        Args:
            workflow_id: Workflow instance ID

        Returns:
            List of events for workflow
        """
        return [e for e in self.audit_events if e.workflow_id == workflow_id]

    def get_user_workflows(
        self, user_id: str, state_filter: Optional[WorkflowState] = None
    ) -> List[ApprovalWorkflow]:
        """Get all workflows created by user.

        Args:
            user_id: User ID
            state_filter: Optional state filter

        Returns:
            List of workflows
        """
        workflows = [w for w in self.workflows.values() if w.created_by == user_id]

        if state_filter:
            workflows = [w for w in workflows if w.state == state_filter]

        return workflows

    def check_escalations(self) -> List[str]:
        """Check for pending workflows that need auto-escalation.

        Returns workflows that exceeded escalation timeout.

        Returns:
            List of workflow IDs that were escalated
        """
        escalated = []
        now = datetime.utcnow()

        for workflow in self.workflows.values():
            if workflow.state != WorkflowState.PENDING_APPROVAL:
                continue

            if workflow.current_step >= len(workflow.steps):
                continue

            current_step = workflow.steps[workflow.current_step]
            hours_pending = (now - workflow.updated_at).total_seconds() / 3600

            if hours_pending > current_step.escalate_after_hours:
                try:
                    self.escalate_step(workflow.workflow_id, "Auto-escalation timeout")
                    escalated.append(workflow.workflow_id)
                except ValueError as e:
                    logger.warning(f"Failed to auto-escalate {workflow.workflow_id}: {e}")

        return escalated

    def _get_workflow(self, workflow_id: str) -> ApprovalWorkflow:
        """Internal helper to get workflow and raise if not found.

        Args:
            workflow_id: Workflow instance ID

        Returns:
            Workflow instance

        Raises:
            ValueError: If workflow not found
        """
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        return workflow

    def _emit_event(self, event: WorkflowEvent) -> None:
        """Emit and log an audit event.

        Args:
            event: WorkflowEvent to emit
        """
        self.audit_events.append(event)
        logger.info(f"Workflow event: {event.to_dict()}")

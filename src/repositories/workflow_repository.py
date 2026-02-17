"""Workflow repository for approval workflow persistence."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin
from src.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class WorkflowModel(Base, TimestampMixin):
    """
    SQLAlchemy model for workflow instances.

    Represents approval workflow instances with full state management,
    approval steps, and decision tracking.

    Attributes:
        id: Primary key
        workflow_type: Type of workflow (e.g., 'compensation_change')
        creator_id: User ID who created the workflow
        state: Current workflow state
        mode: Approval mode (sequential/parallel)
        data_json: Complex workflow metadata as JSON
        steps_json: Workflow steps configuration as JSON
        created_at: Creation timestamp
        updated_at: Last update timestamp
        steps: Relationship to WorkflowStepModel
    """

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(100), nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    mode: Mapped[str] = mapped_column(String(50), default="sequential", nullable=False)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    steps_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    steps: Mapped[List["WorkflowStepModel"]] = relationship(
        "WorkflowStepModel",
        back_populates="workflow",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<WorkflowModel(id={self.id}, type={self.workflow_type}, state={self.state})>"


class WorkflowStepModel(Base, TimestampMixin):
    """
    SQLAlchemy model for individual workflow approval steps.

    Represents a single approval step within a workflow with decision tracking.

    Attributes:
        id: Primary key
        workflow_id: Foreign key to WorkflowModel
        step_order: Position in workflow sequence
        approver_role: Role required to approve (e.g., 'hr_admin')
        status: Current step status (pending/approved/rejected/escalated)
        decided_by: User ID who made the decision (if any)
        decision: Decision made (approved/rejected/escalated)
        decided_at: When decision was made
        workflow: Relationship to WorkflowModel
    """

    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_role: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="steps")

    def __repr__(self) -> str:
        return f"<WorkflowStepModel(id={self.id}, workflow_id={self.workflow_id}, status={self.status})>"


class WorkflowRepository(BaseRepository[WorkflowModel]):
    """
    Repository for workflow persistence and retrieval.

    Provides specialized methods for workflow operations including state
    transitions, step management, and approver queries.
    """

    def __init__(self) -> None:
        """Initialize workflow repository."""
        super().__init__(WorkflowModel)

    def get_workflow(self, workflow_id: int) -> Optional[WorkflowModel]:
        """
        Get workflow by ID with all steps.

        Args:
            workflow_id: Workflow ID

        Returns:
            WorkflowModel instance with populated steps or None
        """
        return self.get(workflow_id)

    def create_workflow(
        self,
        workflow_type: str,
        creator_id: int,
        state: str = "draft",
        mode: str = "sequential",
        data: Optional[Dict[str, Any]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[WorkflowModel]:
        """
        Create new workflow instance.

        Args:
            workflow_type: Type of workflow
            creator_id: Employee ID of creator
            state: Initial state (default: draft)
            mode: Approval mode (default: sequential)
            data: Additional metadata
            steps: List of step configurations

        Returns:
            Created WorkflowModel or None on error
        """
        try:
            workflow_data = {
                "workflow_type": workflow_type,
                "creator_id": creator_id,
                "state": state,
                "mode": mode,
                "data_json": data or {},
                "steps_json": steps or [],
            }
            workflow = self.create(workflow_data)
            if workflow:
                logger.info(f"Created workflow: id={workflow.id}, type={workflow_type}")
            return workflow
        except Exception as e:
            logger.error(f"Error creating workflow: {str(e)}")
            return None

    def update_state(self, workflow_id: int, new_state: str) -> Optional[WorkflowModel]:
        """
        Update workflow state.

        Args:
            workflow_id: Workflow ID
            new_state: New state value

        Returns:
            Updated WorkflowModel or None on error
        """
        return self.update(workflow_id, {"state": new_state})

    def add_step(
        self,
        workflow_id: int,
        step_order: int,
        approver_role: str,
    ) -> Optional[WorkflowStepModel]:
        """
        Add approval step to workflow.

        Args:
            workflow_id: Workflow ID
            step_order: Step position in sequence
            approver_role: Required approver role

        Returns:
            Created WorkflowStepModel or None on error
        """
        try:
            from src.repositories.workflow_repository import WorkflowStepRepository
            repo = WorkflowStepRepository()
            return repo.create({
                "workflow_id": workflow_id,
                "step_order": step_order,
                "approver_role": approver_role,
                "status": "pending",
            })
        except Exception as e:
            logger.error(f"Error adding step to workflow {workflow_id}: {str(e)}")
            return None

    def get_pending_for_approver(self, approver_role: str, limit: int = 50) -> List[WorkflowModel]:
        """
        Get pending workflows awaiting approval by role.

        Args:
            approver_role: Role of approver
            limit: Maximum results

        Returns:
            List of pending WorkflowModel instances
        """
        try:
            with self._get_session() as session:
                stmt = (
                    select(WorkflowModel)
                    .where(WorkflowModel.state == "pending_approval")
                    .limit(limit)
                )
                workflows = session.execute(stmt).scalars().all()

                # Filter by approver role in steps
                result = []
                for workflow in workflows:
                    for step in workflow.steps:
                        if step.status == "pending" and step.approver_role == approver_role:
                            result.append(workflow)
                            break

                return result
        except Exception as e:
            logger.error(f"Error getting pending workflows for {approver_role}: {str(e)}")
            return []

    def get_by_creator(self, creator_id: int, limit: int = 50) -> List[WorkflowModel]:
        """
        Get all workflows created by user.

        Args:
            creator_id: Employee ID of creator
            limit: Maximum results

        Returns:
            List of WorkflowModel instances
        """
        return self.list({"creator_id": creator_id}, limit=limit)

    def get_by_state(self, state: str, limit: int = 50) -> List[WorkflowModel]:
        """
        Get workflows in specific state.

        Args:
            state: Workflow state
            limit: Maximum results

        Returns:
            List of WorkflowModel instances
        """
        return self.list({"state": state}, limit=limit)

    def approve_step(
        self,
        workflow_id: int,
        step_id: int,
        approver_id: int,
        decision: str = "approved",
    ) -> Optional[WorkflowStepModel]:
        """
        Record approval decision on step.

        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            approver_id: Employee ID of approver
            decision: Decision value (approved/rejected/escalated)

        Returns:
            Updated WorkflowStepModel or None on error
        """
        try:
            from src.repositories.workflow_repository import WorkflowStepRepository
            repo = WorkflowStepRepository()
            return repo.update(
                step_id,
                {
                    "status": decision,
                    "decided_by": approver_id,
                    "decision": decision,
                    "decided_at": datetime.utcnow(),
                },
            )
        except Exception as e:
            logger.error(f"Error approving step {step_id}: {str(e)}")
            return None


class WorkflowStepRepository(BaseRepository[WorkflowStepModel]):
    """
    Repository for workflow step persistence.

    Handles individual step operations within workflows.
    """

    def __init__(self) -> None:
        """Initialize workflow step repository."""
        super().__init__(WorkflowStepModel)

    def get_steps_for_workflow(self, workflow_id: int) -> List[WorkflowStepModel]:
        """
        Get all steps for a workflow in order.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of WorkflowStepModel instances sorted by step_order
        """
        try:
            with self._get_session() as session:
                stmt = (
                    select(WorkflowStepModel)
                    .where(WorkflowStepModel.workflow_id == workflow_id)
                    .order_by(WorkflowStepModel.step_order)
                )
                return session.execute(stmt).scalars().all()
        except Exception as e:
            logger.error(f"Error getting steps for workflow {workflow_id}: {str(e)}")
            return []

    def get_pending_steps(self, workflow_id: int) -> List[WorkflowStepModel]:
        """
        Get pending steps for workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            List of pending WorkflowStepModel instances
        """
        return self.list(
            {"workflow_id": workflow_id, "status": "pending"}
        )

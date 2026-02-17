"""Tests for Approval Workflow Engine (WRITE-001)."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.core.workflow_engine import (
    WorkflowEngine,
    ApprovalWorkflow,
    WorkflowTemplate,
    WorkflowStep,
    WorkflowState,
    ApprovalMode,
    WorkflowEvent,
)


class TestWorkflowCreation:
    """Tests for workflow creation."""

    def test_create_workflow_returns_workflow_id(self):
        """create_workflow returns a valid workflow ID."""
        engine = WorkflowEngine()

        # Register template first
        template = WorkflowTemplate(
            name="Compensation Change",
            entity_type="compensation",
            steps_config=[
                {"approver_role": "manager", "escalate_after_hours": 48},
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        assert workflow_id is not None
        assert isinstance(workflow_id, str)
        assert len(workflow_id) > 0

    def test_create_workflow_default_state_is_draft(self):
        """create_workflow sets default state to DRAFT."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Compensation Change",
            entity_type="compensation",
            steps_config=[
                {"approver_role": "manager"},
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        workflow = engine.get_workflow(workflow_id)
        assert workflow.state == WorkflowState.DRAFT

    def test_create_workflow_with_multiple_steps(self):
        """create_workflow creates workflow with multiple steps."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Multi-step Approval",
            entity_type="compensation",
            steps_config=[
                {"approver_role": "manager", "escalate_after_hours": 24},
                {"approver_role": "hr_admin", "escalate_after_hours": 48},
                {"approver_role": "director", "escalate_after_hours": 72},
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        workflow = engine.get_workflow(workflow_id)
        assert len(workflow.steps) == 3
        assert workflow.current_step == 0

    def test_create_workflow_invalid_template_raises(self):
        """create_workflow with invalid template raises ValueError."""
        engine = WorkflowEngine()

        with pytest.raises(ValueError, match="Template not found"):
            engine.create_workflow(
                template_id="invalid_template",
                entity_type="compensation",
                entity_id="emp_001",
                created_by="user_001"
            )


class TestWorkflowSubmission:
    """Tests for workflow submission."""

    def test_submit_workflow_changes_state_to_pending_approval(self):
        """submit_for_approval changes state from DRAFT to PENDING_APPROVAL."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        result = engine.submit_for_approval(workflow_id)

        assert result is True
        workflow = engine.get_workflow(workflow_id)
        assert workflow.state == WorkflowState.PENDING_APPROVAL

    def test_submit_workflow_updates_timestamp(self):
        """submit_for_approval updates workflow updated_at timestamp."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        workflow_before = engine.get_workflow(workflow_id)
        original_timestamp = workflow_before.updated_at

        engine.submit_for_approval(workflow_id)

        workflow_after = engine.get_workflow(workflow_id)
        assert workflow_after.updated_at > original_timestamp

    def test_submit_non_draft_workflow_raises(self):
        """submit_for_approval on non-DRAFT workflow raises ValueError."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        # Submit once
        engine.submit_for_approval(workflow_id)

        # Try to submit again
        with pytest.raises(ValueError, match="Cannot submit workflow"):
            engine.submit_for_approval(workflow_id)


class TestWorkflowApproval:
    """Tests for workflow approval."""

    @patch('src.core.workflow_engine.check_permission')
    def test_approve_step_changes_step_status(self, mock_check_permission):
        """approve_step changes step status to approved."""
        mock_check_permission.return_value = True
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        success, message = engine.approve_step(
            workflow_id=workflow_id,
            approver_id="user_002",
            approver_role="manager",
            comments="Approved"
        )

        assert success is True
        workflow = engine.get_workflow(workflow_id)
        assert workflow.steps[0].status == "approved"

    @patch('src.core.workflow_engine.check_permission')
    def test_approve_last_step_completes_workflow(self, mock_check_permission):
        """approve_step on last step changes state to APPROVED."""
        mock_check_permission.return_value = True
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        engine.approve_step(
            workflow_id=workflow_id,
            approver_id="user_002",
            approver_role="manager",
            comments="Approved"
        )

        workflow = engine.get_workflow(workflow_id)
        assert workflow.state == WorkflowState.APPROVED

    @patch('src.core.workflow_engine.check_permission')
    def test_approve_middle_step_advances_workflow(self, mock_check_permission):
        """approve_step in middle advances to next step."""
        mock_check_permission.return_value = True
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[
                {"approver_role": "manager"},
                {"approver_role": "hr_admin"}
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        engine.approve_step(
            workflow_id=workflow_id,
            approver_id="user_002",
            approver_role="manager"
        )

        workflow = engine.get_workflow(workflow_id)
        assert workflow.state == WorkflowState.PENDING_APPROVAL
        assert workflow.current_step == 1

    @patch('src.core.workflow_engine.check_permission')
    def test_approve_records_decision(self, mock_check_permission):
        """approve_step records decision in workflow."""
        mock_check_permission.return_value = True
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        engine.approve_step(
            workflow_id=workflow_id,
            approver_id="user_002",
            approver_role="manager",
            comments="Looks good"
        )

        workflow = engine.get_workflow(workflow_id)
        assert len(workflow.decisions) == 1
        assert workflow.decisions[0].approver_id == "user_002"
        assert workflow.decisions[0].decision == "approved"
        assert workflow.decisions[0].comments == "Looks good"

    @patch('src.core.workflow_engine.check_permission')
    def test_approve_invalid_role_raises(self, mock_check_permission):
        """approve_step with invalid role raises ValueError."""
        mock_check_permission.return_value = False
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        with pytest.raises(ValueError, match="lacks approval permission"):
            engine.approve_step(
                workflow_id=workflow_id,
                approver_id="user_002",
                approver_role="invalid_role"
            )


class TestWorkflowRejection:
    """Tests for workflow rejection."""

    def test_reject_step_changes_state_to_rejected(self):
        """reject_step changes workflow state to REJECTED."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        result = engine.reject_step(
            workflow_id=workflow_id,
            approver_id="user_002",
            approver_role="manager",
            comments="Not approved"
        )

        assert result is True
        workflow = engine.get_workflow(workflow_id)
        assert workflow.state == WorkflowState.REJECTED

    def test_reject_records_decision(self):
        """reject_step records rejection decision."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        engine.reject_step(
            workflow_id=workflow_id,
            approver_id="user_002",
            approver_role="manager",
            comments="Insufficient justification"
        )

        workflow = engine.get_workflow(workflow_id)
        assert len(workflow.decisions) == 1
        assert workflow.decisions[0].decision == "rejected"
        assert workflow.decisions[0].comments == "Insufficient justification"

    def test_reject_updates_step_status(self):
        """reject_step updates step status."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        engine.reject_step(
            workflow_id=workflow_id,
            approver_id="user_002",
            approver_role="manager"
        )

        workflow = engine.get_workflow(workflow_id)
        assert workflow.steps[0].status == "rejected"


class TestWorkflowEscalation:
    """Tests for workflow escalation."""

    def test_escalate_step_changes_state_to_escalated(self):
        """escalate_step changes workflow state."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[
                {
                    "approver_role": "manager",
                    "next_level_role": "director"
                }
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        result = engine.escalate_step(
            workflow_id=workflow_id,
            reason="Timeout escalation"
        )

        assert result is True
        workflow = engine.get_workflow(workflow_id)
        assert workflow.state == WorkflowState.PENDING_APPROVAL

    def test_escalate_updates_step_status(self):
        """escalate_step updates step status to escalated."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[
                {
                    "approver_role": "manager",
                    "next_level_role": "director"
                }
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        engine.escalate_step(
            workflow_id=workflow_id,
            reason="No response within 24 hours"
        )

        workflow = engine.get_workflow(workflow_id)
        assert workflow.steps[0].status == "escalated"
        assert workflow.steps[0].approver_role == "director"

    def test_escalate_without_next_level_raises(self):
        """escalate_step without next_level_role raises ValueError."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[
                {
                    "approver_role": "manager",
                    "next_level_role": None
                }
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        with pytest.raises(ValueError, match="No next level role"):
            engine.escalate_step(workflow_id=workflow_id)


class TestWorkflowCancellation:
    """Tests for workflow cancellation."""

    def test_cancel_workflow_changes_state_to_cancelled(self):
        """cancel_workflow changes state to CANCELLED."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        result = engine.cancel_workflow(
            workflow_id=workflow_id,
            user_id="user_001",
            user_role="employee"
        )

        assert result is True
        workflow = engine.get_workflow(workflow_id)
        assert workflow.state == WorkflowState.CANCELLED

    def test_cancel_by_creator_succeeds(self):
        """cancel_workflow by creator succeeds."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        result = engine.cancel_workflow(
            workflow_id=workflow_id,
            user_id="user_001",
            user_role="employee"
        )

        assert result is True

    def test_cancel_by_hr_admin_succeeds(self):
        """cancel_workflow by HR admin succeeds."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        result = engine.cancel_workflow(
            workflow_id=workflow_id,
            user_id="admin_user",
            user_role="hr_admin"
        )

        assert result is True

    def test_cancel_by_unauthorized_raises(self):
        """cancel_workflow by unauthorized user raises ValueError."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        with pytest.raises(ValueError, match="lacks permission"):
            engine.cancel_workflow(
                workflow_id=workflow_id,
                user_id="user_002",
                user_role="employee"
            )

    def test_cancel_already_cancelled_raises(self):
        """cancel_workflow when already cancelled raises ValueError."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.cancel_workflow(
            workflow_id=workflow_id,
            user_id="user_001"
        )

        with pytest.raises(ValueError, match="already cancelled"):
            engine.cancel_workflow(
                workflow_id=workflow_id,
                user_id="user_001"
            )


class TestGetPendingWorkflows:
    """Tests for pending workflow retrieval."""

    @patch('src.core.workflow_engine.check_permission')
    def test_get_pending_approvals_filters_by_approver(self, mock_check_permission):
        """get_pending_approvals returns workflows for specific approver."""
        mock_check_permission.return_value = True
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        # Create two workflows
        workflow_id_1 = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        workflow_id_2 = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_002",
            created_by="user_002"
        )

        engine.submit_for_approval(workflow_id_1)
        engine.submit_for_approval(workflow_id_2)

        # Approve first workflow
        engine.approve_step(
            workflow_id=workflow_id_1,
            approver_id="user_003",
            approver_role="manager"
        )

        # Get pending for a generic approver (no specific ID assigned)
        pending = engine.get_pending_approvals("user_003")

        assert len(pending) >= 1

    def test_get_pending_approvals_excludes_non_pending(self):
        """get_pending_approvals excludes non-PENDING workflows."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        # Don't submit - stays in DRAFT
        pending = engine.get_pending_approvals("user_002")

        assert len(pending) == 0


class TestApprovalModes:
    """Tests for SEQUENTIAL vs PARALLEL approval modes."""

    def test_sequential_mode_advances_linearly(self):
        """SEQUENTIAL mode requires approvals in order."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[
                {"approver_role": "manager"},
                {"approver_role": "hr_admin"}
            ],
            approval_mode=ApprovalMode.SEQUENTIAL
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        workflow = engine.get_workflow(workflow_id)
        assert workflow.approval_mode == ApprovalMode.SEQUENTIAL

    def test_parallel_mode_is_set(self):
        """PARALLEL mode can be set in template."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}],
            approval_mode=ApprovalMode.PARALLEL
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        workflow = engine.get_workflow(workflow_id)
        assert workflow.approval_mode == ApprovalMode.PARALLEL


class TestAutoEscalation:
    """Tests for auto-escalation timeout logic."""

    def test_check_escalations_identifies_expired_workflows(self):
        """check_escalations identifies workflows past escalation timeout."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[
                {
                    "approver_role": "manager",
                    "escalate_after_hours": 1,
                    "next_level_role": "director"
                }
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        # Manually set updated_at to past escalation timeout
        workflow = engine.get_workflow(workflow_id)
        workflow.updated_at = datetime.utcnow() - timedelta(hours=2)

        escalated = engine.check_escalations()

        assert len(escalated) >= 1
        assert workflow_id in escalated

    def test_check_escalations_skips_completed_workflows(self):
        """check_escalations does not escalate completed workflows."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[
                {
                    "approver_role": "manager",
                    "escalate_after_hours": 1,
                    "next_level_role": "director"
                }
            ]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        # Manually mark as completed
        workflow = engine.get_workflow(workflow_id)
        workflow.state = WorkflowState.APPROVED

        escalated = engine.check_escalations()

        assert workflow_id not in escalated


class TestWorkflowHistory:
    """Tests for workflow audit trail and history."""

    def test_get_workflow_history_returns_events(self):
        """get_workflow_history returns audit trail events."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        engine.submit_for_approval(workflow_id)

        history = engine.get_workflow_history(workflow_id)

        assert len(history) >= 2
        assert history[0].event_type == "workflow_created"
        assert history[1].event_type == "workflow_submitted"

    def test_workflow_event_to_dict(self):
        """WorkflowEvent.to_dict returns event data."""
        event = WorkflowEvent(
            event_type="test_event",
            workflow_id="wf_001",
            actor="user_001",
            details={"key": "value"}
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == "test_event"
        assert event_dict["workflow_id"] == "wf_001"
        assert event_dict["actor"] == "user_001"
        assert event_dict["details"] == {"key": "value"}


class TestGetUserWorkflows:
    """Tests for retrieving workflows by user."""

    def test_get_user_workflows_filters_by_creator(self):
        """get_user_workflows returns only workflows created by user."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        # Create workflows by different users
        workflow_id_1 = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        workflow_id_2 = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_002",
            created_by="user_002"
        )

        # Get workflows for user_001
        user_workflows = engine.get_user_workflows("user_001")

        assert len(user_workflows) == 1
        assert user_workflows[0].workflow_id == workflow_id_1

    def test_get_user_workflows_with_state_filter(self):
        """get_user_workflows filters by state when provided."""
        engine = WorkflowEngine()

        template = WorkflowTemplate(
            name="Test",
            entity_type="compensation",
            steps_config=[{"approver_role": "manager"}]
        )
        template_id = engine.register_template(template)

        workflow_id_1 = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_001",
            created_by="user_001"
        )

        workflow_id_2 = engine.create_workflow(
            template_id=template_id,
            entity_type="compensation",
            entity_id="emp_002",
            created_by="user_001"
        )

        # Submit only first workflow
        engine.submit_for_approval(workflow_id_1)

        # Get DRAFT workflows
        draft_workflows = engine.get_user_workflows(
            "user_001",
            state_filter=WorkflowState.DRAFT
        )

        assert len(draft_workflows) == 1
        assert draft_workflows[0].workflow_id == workflow_id_2

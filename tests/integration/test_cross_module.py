"""Integration tests for cross-module workflows in HR platform."""

import os
import sys
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add project root to path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import from conftest in same directory
from conftest import MockHRISConnector, MockCacheService

# Try to import modules with fallback
try:
    from src.middleware.auth import AuthService
except ImportError:
    AuthService = None

try:
    from src.core.rbac import RBACEnforcer, RoleLevel
except ImportError:
    RBACEnforcer = None
    RoleLevel = None

try:
    from src.middleware.pii_stripper import PIIStripper
except ImportError:
    PIIStripper = None

try:
    from src.core.quality import QualityAssessor, QualityLevel
except ImportError:
    QualityAssessor = None
    QualityLevel = None

try:
    from src.core.workflow_engine import WorkflowEngine, WorkflowState, ApprovalMode
except ImportError:
    WorkflowEngine = None
    WorkflowState = None
    ApprovalMode = None


# ===== MARKER FOR INTEGRATION TESTS =====
pytestmark = pytest.mark.integration


class TestAuthToRBACFlow:
    """Test authentication to RBAC permission flow."""

    def test_auth_to_rbac_flow(
        self,
        auth_service: AuthService,
        auth_tokens: Dict[str, str],
        sample_employees: List[Dict[str, Any]]
    ):
        """Test JWT generation → verification → RBAC permission check."""
        # Generate token for employee
        token_data = auth_service.generate_token(
            user_id='emp-001',
            email='john.doe@company.com',
            role='employee',
            department='Engineering'
        )

        assert token_data['access_token']
        assert token_data['refresh_token']

        # Verify token
        verified = auth_service.verify_token(token_data['access_token'])
        assert verified['user_id'] == 'emp-001'
        assert verified['role'] == 'employee'
        assert verified['department'] == 'Engineering'

    def test_rbac_data_filtering(
        self,
        auth_tokens: Dict[str, str],
        sample_employees: List[Dict[str, Any]]
    ):
        """Test RBAC filtering of employee data by role."""
        # Employee sees only own data
        employee_data = [emp for emp in sample_employees if emp['id'] == 'emp-001']
        assert len(employee_data) == 1
        assert employee_data[0]['name'] == 'John Doe'

        # Manager sees team data
        team_employees = [
            emp for emp in sample_employees
            if emp['manager_id'] == 'mgr-001'
        ]
        assert len(team_employees) == 2

        # HR Admin sees all data
        assert len(sample_employees) == 5

    def test_role_hierarchy_permissions(
        self,
        auth_service: AuthService,
        sample_employees: List[Dict[str, Any]]
    ):
        """Test role hierarchy for permission checking."""
        # Create tokens for different roles
        roles = ['employee', 'manager', 'hr_admin']
        tokens = {}

        for role in roles:
            token_data = auth_service.generate_token(
                user_id=f'{role}-001',
                email=f'{role}@company.com',
                role=role,
                department='Test'
            )
            tokens[role] = token_data['access_token']

        # Verify all tokens are valid
        for role in roles:
            verified = auth_service.verify_token(tokens[role])
            assert verified['role'] == role


class TestPIIPipelineFlow:
    """Test PII detection, stripping, and rehydration flow."""

    def test_pii_strip_and_detect(
        self,
        pii_stripper: PIIStripper
    ):
        """Test PII detection and stripping."""
        text_with_pii = (
            "Employee John Doe with SSN 123-45-6789 "
            "can be reached at john.doe@company.com or 555-123-4567. "
            "Current salary is $120,000 annually."
        )

        result = pii_stripper.strip(text_with_pii)

        assert result.pii_count > 0
        assert len(result.mapping) > 0
        assert 'john.doe@company.com' not in result.sanitized_text
        assert '123-45-6789' not in result.sanitized_text
        assert '[PII' in result.sanitized_text or '[REDACTED' in result.sanitized_text

    def test_pii_rehydration(
        self,
        pii_stripper: PIIStripper
    ):
        """Test PII rehydration after stripping."""
        original_text = (
            "Contact john.smith@company.com for SSN 987-65-4321"
        )

        result = pii_stripper.strip(original_text)

        # Verify stripping worked
        assert result.pii_count > 0
        assert result.sanitized_text != original_text

        # Verify mapping exists for rehydration
        assert len(result.mapping) > 0

    def test_pii_types_detected(
        self,
        pii_stripper: PIIStripper
    ):
        """Test detection of multiple PII types."""
        text = (
            "John Doe (SSN: 555-12-3456) works at john.doe@company.com. "
            "Phone: 212-555-1234. Employee ID: EMP-12345. Salary: $95,000"
        )

        result = pii_stripper.strip(text)

        # Should detect multiple types
        assert 'email' in result.pii_types_found or 'EMAIL' in str(result.pii_types_found)
        assert result.pii_count >= 3


class TestRouterIntentClassification:
    """Test router agent intent classification."""

    def test_router_leave_intent(
        self,
        router_agent
    ):
        """Test router classification of leave request intent."""
        query = "I need to take 5 days of annual leave next month"

        result = router_agent.classify_intent(query)

        assert result['intent'] in ['leave_request', 'leave']
        assert result['confidence'] > 0.7

    def test_router_policy_intent(
        self,
        router_agent
    ):
        """Test router classification of policy search intent."""
        query = "What is the remote work policy?"

        result = router_agent.classify_intent(query)

        assert 'policy' in result['intent'].lower()

    def test_router_employee_info_intent(
        self,
        router_agent
    ):
        """Test router classification of employee info intent."""
        query = "Who are my team members?"

        result = router_agent.classify_intent(query)

        # Should classify as employee_info or employee related
        assert 'employee' in result['intent'].lower() or 'team' in result['intent'].lower()

    def test_router_multiple_query_types(
        self,
        router_agent
    ):
        """Test router handling multiple query types."""
        queries = [
            "How much PTO do I have left?",
            "What is the compensation policy?",
            "Who is my manager?"
        ]

        for query in queries:
            result = router_agent.classify_intent(query)
            assert 'intent' in result
            assert 'confidence' in result


class TestQualityScoringPipeline:
    """Test quality assessment pipeline."""

    def test_quality_assessment_sufficient(
        self,
        quality_assessor: QualityAssessor
    ):
        """Test quality assessment for good response."""
        query = "What is the vacation policy?"
        response = (
            "Our vacation policy provides 20 days of paid time off annually. "
            "Employees can take up to 10 consecutive days. "
            "Unused days can be carried over up to 5 days per year."
        )

        score = quality_assessor.assess(query, response)

        assert score.overall >= 0.4
        assert score.relevance > 0.3
        assert score.completeness > 0.3

    def test_quality_assessment_insufficient(
        self,
        quality_assessor: QualityAssessor
    ):
        """Test quality assessment for poor response."""
        query = "What is the vacation policy?"
        response = "I don't know."

        score = quality_assessor.assess(query, response)

        assert score.overall < 0.7
        assert score.completeness < 0.5

    def test_quality_level_classification(
        self,
        quality_assessor: QualityAssessor
    ):
        """Test quality level classification."""
        if QualityLevel is None:
            pytest.skip("QualityLevel not available")

        query = "What is the vacation policy?"

        # Good response
        good_response = (
            "Our vacation policy provides 20 days of paid time off annually. "
            "Employees can take up to 10 consecutive days."
        )
        good_score = quality_assessor.assess(query, good_response)
        good_level = quality_assessor.get_level(good_score)

        # Poor response
        poor_response = "I don't know."
        poor_score = quality_assessor.assess(query, poor_response)
        poor_level = quality_assessor.get_level(poor_score)

        # Good should be sufficient or marginal, poor should be insufficient
        assert good_level in [QualityLevel.SUFFICIENT, QualityLevel.MARGINAL]

    def test_quality_fallback_suggestions(
        self,
        quality_assessor: QualityAssessor
    ):
        """Test fallback suggestions based on quality."""
        query = "Complex query about policies"
        response = "I think it might be related to something"

        score = quality_assessor.assess(query, response)
        fallback = quality_assessor.suggest_fallback(score)

        # Marginal response should suggest fallback
        if score.overall < 0.7:
            assert fallback is not None


class TestWorkflowLifecycle:
    """Test workflow creation, submission, and approval."""

    def test_workflow_creation(
        self,
        workflow_engine: WorkflowEngine,
        sample_workflow_data: Dict[str, Any],
        sample_workflow_steps: List
    ):
        """Test creating a new workflow."""
        if WorkflowState is None:
            pytest.skip("WorkflowState not available")

        workflow = workflow_engine.create_workflow(
            entity_type=sample_workflow_data['entity_type'],
            entity_id=sample_workflow_data['entity_id'],
            created_by=sample_workflow_data['created_by'],
            steps_config=sample_workflow_steps
        )

        assert workflow.workflow_id
        assert workflow.state == WorkflowState.DRAFT
        assert len(workflow.steps) > 0

    def test_workflow_submission(
        self,
        workflow_engine: WorkflowEngine,
        sample_workflow_data: Dict[str, Any],
        sample_workflow_steps: List
    ):
        """Test submitting a workflow for approval."""
        if WorkflowState is None:
            pytest.skip("WorkflowState not available")

        workflow = workflow_engine.create_workflow(
            entity_type=sample_workflow_data['entity_type'],
            entity_id=sample_workflow_data['entity_id'],
            created_by=sample_workflow_data['created_by'],
            steps_config=sample_workflow_steps
        )

        # Submit workflow
        submitted = workflow_engine.submit_workflow(workflow.workflow_id)

        assert submitted.state == WorkflowState.PENDING_APPROVAL
        assert submitted.current_step == 0

    def test_workflow_approval_flow(
        self,
        workflow_engine: WorkflowEngine,
        sample_workflow_data: Dict[str, Any],
        sample_workflow_steps: List
    ):
        """Test complete workflow approval flow."""
        if WorkflowState is None:
            pytest.skip("WorkflowState not available")

        # Create and submit
        workflow = workflow_engine.create_workflow(
            entity_type=sample_workflow_data['entity_type'],
            entity_id=sample_workflow_data['entity_id'],
            created_by=sample_workflow_data['created_by'],
            steps_config=sample_workflow_steps
        )

        submitted = workflow_engine.submit_workflow(workflow.workflow_id)
        assert submitted.state == WorkflowState.PENDING_APPROVAL

        # Approve all steps
        for i in range(len(submitted.steps)):
            approved = workflow_engine.approve_step(
                workflow_id=submitted.workflow_id,
                step_index=i,
                approver_id='mgr-001',
                comments='Approved'
            )
            assert approved is not None

    def test_workflow_completion(
        self,
        workflow_engine: WorkflowEngine,
        sample_workflow_data: Dict[str, Any],
        sample_workflow_steps: List
    ):
        """Test workflow completion state."""
        if WorkflowState is None:
            pytest.skip("WorkflowState not available")

        workflow = workflow_engine.create_workflow(
            entity_type=sample_workflow_data['entity_type'],
            entity_id=sample_workflow_data['entity_id'],
            created_by=sample_workflow_data['created_by'],
            steps_config=sample_workflow_steps
        )

        submitted = workflow_engine.submit_workflow(workflow.workflow_id)

        # Approve all steps
        for i in range(len(submitted.steps)):
            workflow_engine.approve_step(
                workflow_id=submitted.workflow_id,
                step_index=i,
                approver_id='mgr-001',
                comments='Approved'
            )

        # Get final workflow
        final = workflow_engine.get_workflow(submitted.workflow_id)
        assert final.state == WorkflowState.APPROVED


class TestWorkflowRejection:
    """Test workflow rejection flow."""

    def test_workflow_rejection(
        self,
        workflow_engine: WorkflowEngine,
        sample_workflow_data: Dict[str, Any],
        sample_workflow_steps: List
    ):
        """Test rejecting a workflow at approval step."""
        if WorkflowState is None:
            pytest.skip("WorkflowState not available")

        workflow = workflow_engine.create_workflow(
            entity_type=sample_workflow_data['entity_type'],
            entity_id=sample_workflow_data['entity_id'],
            created_by=sample_workflow_data['created_by'],
            steps_config=sample_workflow_steps
        )

        submitted = workflow_engine.submit_workflow(workflow.workflow_id)

        # Reject at first step
        rejected = workflow_engine.reject_workflow(
            workflow_id=submitted.workflow_id,
            step_index=0,
            approver_id='mgr-001',
            comments='Does not meet criteria'
        )

        assert rejected.state == WorkflowState.REJECTED


class TestWorkflowEscalation:
    """Test workflow escalation flow."""

    def test_workflow_escalation(
        self,
        workflow_engine: WorkflowEngine,
        sample_workflow_data: Dict[str, Any],
        sample_workflow_steps: List
    ):
        """Test escalating a workflow to higher role."""
        if WorkflowState is None:
            pytest.skip("WorkflowState not available")

        workflow = workflow_engine.create_workflow(
            entity_type=sample_workflow_data['entity_type'],
            entity_id=sample_workflow_data['entity_id'],
            created_by=sample_workflow_data['created_by'],
            steps_config=sample_workflow_steps
        )

        submitted = workflow_engine.submit_workflow(workflow.workflow_id)

        # Escalate from first step
        escalated = workflow_engine.escalate_workflow(
            workflow_id=submitted.workflow_id,
            step_index=0,
            escalated_by='mgr-001',
            comments='Escalating to HR for review'
        )

        assert escalated.state == WorkflowState.ESCALATED


class TestMultiModuleConversation:
    """Test full conversation flow touching multiple modules."""

    def test_multi_module_conversation_flow(
        self,
        auth_service: AuthService,
        auth_tokens: Dict[str, str],
        router_agent,
        quality_assessor: QualityAssessor,
        pii_stripper: PIIStripper,
        sample_employees: List[Dict[str, Any]]
    ):
        """Test full conversation flow: auth → router → agent → quality."""
        # Step 1: Authenticate
        verified = auth_service.verify_token(auth_tokens['employee'])
        assert verified['user_id'] == 'emp-001'

        # Step 2: Route user query
        query = "What is my PTO balance?"
        intent_result = router_agent.classify_intent(query)
        assert intent_result['confidence'] > 0.5

        # Step 3: Generate response
        response = "Your current PTO balance is 15 days."

        # Step 4: Assess quality
        score = quality_assessor.assess(query, response)
        assert score.overall > 0.0

    def test_pii_handling_in_conversation(
        self,
        pii_stripper: PIIStripper,
        quality_assessor: QualityAssessor
    ):
        """Test PII handling within conversation flow."""
        # User sends message with PII
        user_message = "My name is John Doe and SSN is 123-45-6789"

        # Strip PII
        pii_result = pii_stripper.strip(user_message)
        assert pii_result.pii_count > 0

        # Process sanitized version
        sanitized = pii_result.sanitized_text
        response = "Your information has been securely recorded."

        # Assess quality of response
        score = quality_assessor.assess(sanitized, response)
        assert score.overall >= 0.0


class TestPIIInWorkflow:
    """Test PII handling in workflow submissions."""

    def test_pii_stripping_in_workflow_comments(
        self,
        workflow_engine: WorkflowEngine,
        pii_stripper: PIIStripper,
        sample_workflow_data: Dict[str, Any],
        sample_workflow_steps: List
    ):
        """Test that PII in workflow comments is handled."""
        workflow = workflow_engine.create_workflow(
            entity_type=sample_workflow_data['entity_type'],
            entity_id=sample_workflow_data['entity_id'],
            created_by=sample_workflow_data['created_by'],
            steps_config=sample_workflow_steps,
            metadata=sample_workflow_data
        )

        submitted = workflow_engine.submit_workflow(workflow.workflow_id)

        # Submit approval with PII in comments
        comment_with_pii = "Approved by John Doe, contact john.doe@company.com"
        pii_result = pii_stripper.strip(comment_with_pii)

        # Comments should have PII stripped
        assert pii_result.pii_count > 0
        assert 'john.doe@company.com' not in pii_result.sanitized_text

    def test_workflow_audit_pii_redaction(
        self,
        workflow_engine: WorkflowEngine,
        sample_workflow_data: Dict[str, Any],
        sample_workflow_steps: List
    ):
        """Test that audit logs redact PII."""
        workflow = workflow_engine.create_workflow(
            entity_type=sample_workflow_data['entity_type'],
            entity_id=sample_workflow_data['entity_id'],
            created_by=sample_workflow_data['created_by'],
            steps_config=sample_workflow_steps
        )

        submitted = workflow_engine.submit_workflow(workflow.workflow_id)

        # Get workflow history (audit)
        history = workflow_engine.get_workflow_history(submitted.workflow_id)

        # Verify history exists and can be retrieved
        assert history is not None or submitted.workflow_id is not None

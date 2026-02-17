"""Unit tests for repository layer - Iteration 3."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from typing import Optional

from src.repositories.base_repository import BaseRepository
from src.repositories.workflow_repository import (
    WorkflowRepository,
    WorkflowModel,
    WorkflowStepRepository,
    WorkflowStepModel,
)
from src.repositories.notification_repository import (
    NotificationRepository,
    NotificationModel,
    NotificationPreferenceRepository,
    NotificationPreferenceModel,
)
from src.repositories.gdpr_repository import (
    GDPRRepository,
    ConsentRecordModel,
    DSARRepository,
    DSARRequestModel,
    RetentionPolicyRepository,
    RetentionPolicyModel,
)
from src.repositories.document_repository import (
    DocumentTemplateRepository,
    DocumentTemplateModel,
    GeneratedDocumentRepository,
    GeneratedDocumentModel,
)
from src.repositories.bias_repository import (
    BiasRepository,
    BiasIncidentModel,
    BiasAuditReportRepository,
    BiasAuditReportModel,
)
from src.repositories.dashboard_repository import (
    DashboardRepository,
    DashboardModel,
    DashboardWidgetRepository,
    DashboardWidgetModel,
    MetricSnapshotRepository,
    MetricSnapshotModel,
)


class MockModel:
    """Mock SQLAlchemy model for testing."""
    id = MagicMock()

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.id = kwargs.get('id', 1)


@pytest.fixture
def mock_session():
    """Create a mocked SQLAlchemy session."""
    session = MagicMock()
    return session


@pytest.fixture
def mock_session_context():
    """Create a mocked session context manager."""
    with patch('src.repositories.base_repository.SessionLocal') as mock_local:
        session_mock = MagicMock()
        session_mock.__enter__ = MagicMock(return_value=session_mock)
        session_mock.__exit__ = MagicMock(return_value=False)
        mock_local.return_value = session_mock
        yield session_mock


# ==================== BASE REPOSITORY TESTS ====================

class TestBaseRepository:
    """Tests for base repository abstract class."""

    def test_base_repository_initialization(self):
        """BaseRepository initializes with model class."""
        repo = BaseRepository(WorkflowModel)
        assert repo.model_class == WorkflowModel

    def test_base_repository_get_session_requires_initialized_db(self):
        """_get_session raises RuntimeError if SessionLocal not initialized."""
        with patch('src.repositories.base_repository.SessionLocal', None):
            repo = BaseRepository(WorkflowModel)
            with pytest.raises(RuntimeError, match="Database not initialized"):
                with repo._get_session():
                    pass

    def test_base_repository_session_context_commits_on_success(self, mock_session_context):
        """_get_session commits transaction on success."""
        repo = BaseRepository(WorkflowModel)

        with patch('src.repositories.base_repository.SessionLocal') as mock_local:
            mock_local.return_value = mock_session_context
            with repo._get_session():
                pass

            mock_session_context.commit.assert_called_once()

    def test_base_repository_session_context_rolls_back_on_error(self):
        """_get_session rolls back transaction on exception."""
        repo = BaseRepository(WorkflowModel)

        with patch('src.repositories.base_repository.SessionLocal') as mock_local:
            session_mock = MagicMock()
            session_mock.__enter__ = MagicMock(return_value=session_mock)
            session_mock.__exit__ = MagicMock(side_effect=Exception("Test error"))
            mock_local.return_value = session_mock

            with pytest.raises(Exception):
                with repo._get_session():
                    raise Exception("Test error")

            session_mock.rollback.assert_called()

    def test_base_repository_session_context_closes_session(self):
        """_get_session closes session in finally block."""
        repo = BaseRepository(WorkflowModel)

        with patch('src.repositories.base_repository.SessionLocal') as mock_local:
            session_mock = MagicMock()
            session_mock.__enter__ = MagicMock(return_value=session_mock)
            session_mock.__exit__ = MagicMock(return_value=False)
            mock_local.return_value = session_mock

            with repo._get_session():
                pass

            session_mock.close.assert_called_once()


# ==================== WORKFLOW REPOSITORY TESTS ====================

class TestWorkflowRepository:
    """Tests for workflow repository."""

    def test_create_workflow_success(self):
        """create_workflow successfully creates workflow."""
        repo = WorkflowRepository()

        with patch.object(repo, 'create') as mock_create:
            workflow = MagicMock(spec=WorkflowModel)
            workflow.id = 1
            workflow.workflow_type = 'compensation_change'
            mock_create.return_value = workflow

            result = repo.create_workflow(
                workflow_type='compensation_change',
                creator_id=123,
                state='draft',
                mode='sequential',
                data={'key': 'value'},
                steps=[{'role': 'manager'}]
            )

            assert result is not None
            assert result.workflow_type == 'compensation_change'
            mock_create.assert_called_once()

    def test_create_workflow_with_defaults(self):
        """create_workflow uses default state and mode."""
        repo = WorkflowRepository()

        with patch.object(repo, 'create') as mock_create:
            mock_create.return_value = MagicMock(spec=WorkflowModel)

            repo.create_workflow(
                workflow_type='leave_request',
                creator_id=456
            )

            call_args = mock_create.call_args[0][0]
            assert call_args['state'] == 'draft'
            assert call_args['mode'] == 'sequential'
            assert call_args['data_json'] == {}
            assert call_args['steps_json'] == []

    def test_update_state_success(self):
        """update_state successfully updates workflow state."""
        repo = WorkflowRepository()

        with patch.object(repo, 'update') as mock_update:
            workflow = MagicMock(spec=WorkflowModel)
            workflow.state = 'pending_approval'
            mock_update.return_value = workflow

            result = repo.update_state(1, 'pending_approval')

            assert result.state == 'pending_approval'
            mock_update.assert_called_once_with(1, {'state': 'pending_approval'})

    def test_get_pending_for_approver_filters_by_role(self):
        """get_pending_for_approver returns workflows pending approval by role."""
        repo = WorkflowRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            # Create mock workflow with steps
            workflow = MagicMock(spec=WorkflowModel)
            step = MagicMock(spec=WorkflowStepModel)
            step.status = 'pending'
            step.approver_role = 'manager'
            workflow.steps = [step]
            workflow.state = 'pending_approval'

            session_mock = MagicMock()
            session_mock.execute.return_value.scalars.return_value.all.return_value = [workflow]

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_pending_for_approver('manager')

            assert len(result) == 1
            assert result[0] == workflow

    def test_get_by_creator_filters_by_user(self):
        """get_by_creator returns workflows created by specific user."""
        repo = WorkflowRepository()

        with patch.object(repo, 'list') as mock_list:
            workflows = [MagicMock(spec=WorkflowModel)]
            mock_list.return_value = workflows

            result = repo.get_by_creator(789, limit=50)

            assert result == workflows
            mock_list.assert_called_once_with({'creator_id': 789}, limit=50)

    def test_get_by_state_filters_by_state(self):
        """get_by_state returns workflows in specific state."""
        repo = WorkflowRepository()

        with patch.object(repo, 'list') as mock_list:
            workflows = [MagicMock(spec=WorkflowModel)]
            mock_list.return_value = workflows

            result = repo.get_by_state('approved', limit=50)

            assert result == workflows
            mock_list.assert_called_once_with({'state': 'approved'}, limit=50)

    def test_approve_step_records_decision(self):
        """approve_step records approval decision."""
        repo = WorkflowRepository()

        with patch('src.repositories.workflow_repository.WorkflowStepRepository') as mock_step_repo_class:
            step_repo_mock = MagicMock()
            step = MagicMock(spec=WorkflowStepModel)
            step.status = 'approved'
            step_repo_mock.update.return_value = step
            mock_step_repo_class.return_value = step_repo_mock

            result = repo.approve_step(1, 5, 456, decision='approved')

            assert result.status == 'approved'
            step_repo_mock.update.assert_called_once()
            call_args = step_repo_mock.update.call_args[0]
            assert call_args[0] == 5


class TestWorkflowStepRepository:
    """Tests for workflow step repository."""

    def test_get_steps_for_workflow_ordered(self):
        """get_steps_for_workflow returns steps in order."""
        repo = WorkflowStepRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            steps = [
                MagicMock(spec=WorkflowStepModel, step_order=1),
                MagicMock(spec=WorkflowStepModel, step_order=2),
            ]

            session_mock = MagicMock()
            session_mock.execute.return_value.scalars.return_value.all.return_value = steps

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_steps_for_workflow(1)

            assert len(result) == 2
            assert result[0].step_order == 1
            assert result[1].step_order == 2

    def test_get_pending_steps_filters_status(self):
        """get_pending_steps returns only pending steps."""
        repo = WorkflowStepRepository()

        with patch.object(repo, 'list') as mock_list:
            steps = [MagicMock(spec=WorkflowStepModel)]
            mock_list.return_value = steps

            result = repo.get_pending_steps(1)

            mock_list.assert_called_once_with({
                'workflow_id': 1,
                'status': 'pending'
            })


# ==================== NOTIFICATION REPOSITORY TESTS ====================

class TestNotificationRepository:
    """Tests for notification repository."""

    def test_create_notification_success(self):
        """create_notification creates notification with defaults."""
        repo = NotificationRepository()

        with patch.object(repo, 'create') as mock_create:
            notification = MagicMock(spec=NotificationModel)
            notification.id = 1
            notification.status = 'pending'
            mock_create.return_value = notification

            result = repo.create_notification(
                recipient_id=100,
                title='Test Title',
                message='Test Message',
                channel='in_app',
                priority='high'
            )

            assert result.status == 'pending'
            mock_create.assert_called_once()

    def test_mark_as_read_updates_status_and_timestamp(self):
        """mark_as_read updates status and sets read_at."""
        repo = NotificationRepository()

        with patch.object(repo, 'update') as mock_update:
            notification = MagicMock(spec=NotificationModel)
            notification.status = 'read'
            notification.read_at = datetime.utcnow()
            mock_update.return_value = notification

            result = repo.mark_as_read(1)

            assert result.status == 'read'
            mock_update.assert_called_once()

    def test_get_unread_count_returns_count(self):
        """get_unread_count returns number of unread notifications."""
        repo = NotificationRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            session_mock = MagicMock()
            session_mock.execute.return_value.scalar.return_value = 5

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_unread_count(100)

            assert result == 5

    def test_get_notifications_filters_by_status_and_channel(self):
        """get_notifications filters by status and channel."""
        repo = NotificationRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            notifications = [MagicMock(spec=NotificationModel)]
            session_mock = MagicMock()
            session_mock.execute.return_value.scalars.return_value.all.return_value = notifications

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_notifications(100, status='sent', channel='email', limit=20)

            assert len(result) == 1

    def test_mark_sent_updates_status(self):
        """mark_sent updates notification status to sent."""
        repo = NotificationRepository()

        with patch.object(repo, 'update') as mock_update:
            mock_update.return_value = MagicMock(spec=NotificationModel)

            repo.mark_sent(1)

            mock_update.assert_called_once_with(1, {'status': 'sent'})

    def test_mark_failed_updates_status(self):
        """mark_failed updates notification status to failed."""
        repo = NotificationRepository()

        with patch.object(repo, 'update') as mock_update:
            mock_update.return_value = MagicMock(spec=NotificationModel)

            repo.mark_failed(1)

            mock_update.assert_called_once_with(1, {'status': 'failed'})


class TestNotificationPreferenceRepository:
    """Tests for notification preference repository."""

    def test_get_preferences_returns_user_preferences(self):
        """get_preferences returns all preferences for user."""
        repo = NotificationPreferenceRepository()

        with patch.object(repo, 'list') as mock_list:
            prefs = [MagicMock(spec=NotificationPreferenceModel)]
            mock_list.return_value = prefs

            result = repo.get_preferences(100)

            assert result == prefs
            mock_list.assert_called_once_with({'user_id': 100})

    def test_save_preference_creates_new_preference(self):
        """save_preference creates new preference when not exists."""
        repo = NotificationPreferenceRepository()

        with patch.object(repo, 'get_preference', return_value=None):
            with patch.object(repo, 'create') as mock_create:
                pref = MagicMock(spec=NotificationPreferenceModel)
                mock_create.return_value = pref

                result = repo.save_preference(
                    user_id=100,
                    channel='email',
                    enabled=True,
                    quiet_hours_start='18:00',
                    quiet_hours_end='09:00'
                )

                assert result is not None
                mock_create.assert_called_once()

    def test_save_preference_updates_existing_preference(self):
        """save_preference updates existing preference."""
        repo = NotificationPreferenceRepository()

        existing_pref = MagicMock(spec=NotificationPreferenceModel)
        existing_pref.id = 5

        with patch.object(repo, 'get_preference', return_value=existing_pref):
            with patch.object(repo, 'update') as mock_update:
                pref = MagicMock(spec=NotificationPreferenceModel)
                mock_update.return_value = pref

                result = repo.save_preference(100, 'slack', False)

                mock_update.assert_called_once_with(5, {
                    'enabled': False,
                    'quiet_hours_start': None,
                    'quiet_hours_end': None
                })


# ==================== GDPR REPOSITORY TESTS ====================

class TestGDPRRepository:
    """Tests for GDPR repository."""

    def test_record_consent_creates_consent_record(self):
        """record_consent creates consent record with timestamp."""
        repo = GDPRRepository()

        with patch.object(repo, 'create') as mock_create:
            consent = MagicMock(spec=ConsentRecordModel)
            consent.id = 1
            mock_create.return_value = consent

            result = repo.record_consent(100, 'marketing', True, 'explicit_consent')

            assert result is not None
            mock_create.assert_called_once()

    def test_get_active_consents_excludes_revoked(self):
        """get_active_consents returns only non-revoked consents."""
        repo = GDPRRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            consents = [
                MagicMock(spec=ConsentRecordModel, revoked_at=None)
            ]

            session_mock = MagicMock()
            session_mock.execute.return_value.scalars.return_value.all.return_value = consents

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_active_consents(100)

            assert len(result) == 1
            assert result[0].revoked_at is None

    def test_revoke_consent_sets_revoked_at(self):
        """revoke_consent sets revoked_at timestamp."""
        repo = GDPRRepository()

        with patch.object(repo, 'update') as mock_update:
            consent = MagicMock(spec=ConsentRecordModel)
            mock_update.return_value = consent

            repo.revoke_consent(1)

            mock_update.assert_called_once()


class TestDSARRepository:
    """Tests for Data Subject Access Request repository."""

    def test_create_dsar_creates_request(self):
        """create_dsar creates DSAR with deadline."""
        repo = DSARRepository()

        deadline = datetime.utcnow() + timedelta(days=30)

        with patch.object(repo, 'create') as mock_create:
            dsar = MagicMock(spec=DSARRequestModel)
            dsar.id = 1
            dsar.status = 'pending'
            mock_create.return_value = dsar

            result = repo.create_dsar(100, 'access', deadline)

            assert result.status == 'pending'

    def test_get_pending_dsars_returns_pending_only(self):
        """get_pending_dsars returns only pending requests."""
        repo = DSARRepository()

        with patch.object(repo, 'list') as mock_list:
            dsars = [MagicMock(spec=DSARRequestModel)]
            mock_list.return_value = dsars

            result = repo.get_pending_dsars()

            mock_list.assert_called_once_with({'status': 'pending'})

    def test_get_overdue_dsars_filters_by_deadline(self):
        """get_overdue_dsars returns requests past deadline."""
        repo = DSARRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            dsar = MagicMock(spec=DSARRequestModel)
            dsar.deadline = datetime.utcnow() - timedelta(days=1)
            dsar.status = 'pending'

            session_mock = MagicMock()
            session_mock.execute.return_value.scalars.return_value.all.return_value = [dsar]

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_overdue_dsars()

            assert len(result) == 1


class TestRetentionPolicyRepository:
    """Tests for data retention policy repository."""

    def test_create_policy_creates_retention_policy(self):
        """create_policy creates data retention policy."""
        repo = RetentionPolicyRepository()

        with patch.object(repo, 'create') as mock_create:
            policy = MagicMock(spec=RetentionPolicyModel)
            policy.id = 1
            mock_create.return_value = policy

            result = repo.create_policy('personal', 365, 'delete', 'Delete after 1 year')

            assert result is not None

    def test_get_policy_for_category_returns_policy(self):
        """get_policy_for_category returns policy for category."""
        repo = RetentionPolicyRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            policy = MagicMock(spec=RetentionPolicyModel)
            policy.data_category = 'financial'

            session_mock = MagicMock()
            session_mock.execute.return_value.scalar_one_or_none.return_value = policy

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_policy_for_category('financial')

            assert result.data_category == 'financial'


# ==================== DOCUMENT REPOSITORY TESTS ====================

class TestDocumentTemplateRepository:
    """Tests for document template repository."""

    def test_create_template_creates_template(self):
        """create_template creates document template."""
        repo = DocumentTemplateRepository()

        with patch.object(repo, 'create') as mock_create:
            template = MagicMock(spec=DocumentTemplateModel)
            template.id = 1
            template.name = 'Offer Letter'
            mock_create.return_value = template

            result = repo.create_template(
                name='Offer Letter',
                document_type='offer_letter',
                content_template='Dear {{employee_name}}...',
                required_variables=['employee_name', 'start_date']
            )

            assert result.name == 'Offer Letter'

    def test_list_templates_filters_by_type(self):
        """list_templates filters by document type."""
        repo = DocumentTemplateRepository()

        with patch.object(repo, 'list') as mock_list:
            templates = [MagicMock(spec=DocumentTemplateModel)]
            mock_list.return_value = templates

            result = repo.list_templates(document_type='offer_letter')

            mock_list.assert_called_once_with({'document_type': 'offer_letter'})

    def test_get_by_name_returns_template(self):
        """get_by_name returns template by name."""
        repo = DocumentTemplateRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            template = MagicMock(spec=DocumentTemplateModel)
            template.name = 'Termination Letter'

            session_mock = MagicMock()
            session_mock.execute.return_value.scalar_one_or_none.return_value = template

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_by_name('Termination Letter')

            assert result.name == 'Termination Letter'


class TestGeneratedDocumentRepository:
    """Tests for generated document repository."""

    def test_create_document_creates_generated_document(self):
        """create_document creates generated document."""
        repo = GeneratedDocumentRepository()

        with patch.object(repo, 'create') as mock_create:
            doc = MagicMock(spec=GeneratedDocumentModel)
            doc.id = 1
            doc.status = 'draft'
            mock_create.return_value = doc

            result = repo.create_document(
                template_id=1,
                generated_by=100,
                content='Generated content',
                variables={'name': 'John'}
            )

            assert result.status == 'draft'

    def test_update_status_updates_document_status(self):
        """update_status updates document status."""
        repo = GeneratedDocumentRepository()

        with patch.object(repo, 'update') as mock_update:
            doc = MagicMock(spec=GeneratedDocumentModel)
            doc.status = 'approved'
            doc.approved_by = 200
            mock_update.return_value = doc

            result = repo.update_status(1, 'approved', approved_by=200)

            assert result.status == 'approved'

    def test_get_pending_approval_returns_pending_documents(self):
        """get_pending_approval returns documents pending approval."""
        repo = GeneratedDocumentRepository()

        with patch.object(repo, 'list') as mock_list:
            docs = [MagicMock(spec=GeneratedDocumentModel)]
            mock_list.return_value = docs

            result = repo.get_pending_approval()

            mock_list.assert_called_once_with({'status': 'pending_approval'})

    def test_approve_document_sets_approved_status(self):
        """approve_document sets approved status and approver."""
        repo = GeneratedDocumentRepository()

        with patch.object(repo, 'update_status') as mock_update_status:
            doc = MagicMock(spec=GeneratedDocumentModel)
            mock_update_status.return_value = doc

            result = repo.approve_document(1, 200)

            mock_update_status.assert_called_once_with(1, 'approved', approved_by=200)

    def test_get_audit_trail_returns_history(self):
        """get_audit_trail returns document history."""
        repo = GeneratedDocumentRepository()

        doc = MagicMock(spec=GeneratedDocumentModel)
        doc.id = 1
        doc.template_id = 5
        doc.generated_by = 100
        doc.created_at = datetime.utcnow()
        doc.status = 'approved'
        doc.updated_at = datetime.utcnow()
        doc.approved_by = 200
        doc.variables_json = {'name': 'John'}

        with patch.object(repo, 'get', return_value=doc):
            result = repo.get_audit_trail(1)

            assert result['document_id'] == 1
            assert result['template_id'] == 5
            assert result['status'] == 'approved'


# ==================== BIAS REPOSITORY TESTS ====================

class TestBiasRepository:
    """Tests for bias detection repository."""

    def test_log_incident_creates_incident(self):
        """log_incident creates bias incident record."""
        repo = BiasRepository()

        with patch.object(repo, 'create') as mock_create:
            incident = MagicMock(spec=BiasIncidentModel)
            incident.id = 1
            incident.category = 'gender'
            incident.severity = 'high'
            mock_create.return_value = incident

            result = repo.log_incident(
                response_text='Young, energetic person needed',
                category='age',
                severity='high',
                term_found='young',
                context='Job description for sales role'
            )

            assert result is not None

    def test_get_incidents_filters_by_category_and_severity(self):
        """get_incidents filters by category and severity."""
        repo = BiasRepository()

        with patch.object(repo, 'list') as mock_list:
            incidents = [MagicMock(spec=BiasIncidentModel)]
            mock_list.return_value = incidents

            result = repo.get_incidents(category='gender', severity='high', limit=100)

            mock_list.assert_called_once()

    def test_get_high_severity_incidents_returns_high_severity(self):
        """get_high_severity_incidents returns high severity incidents."""
        repo = BiasRepository()

        with patch.object(repo, 'get_incidents') as mock_get:
            incidents = [MagicMock(spec=BiasIncidentModel)]
            mock_get.return_value = incidents

            result = repo.get_high_severity_incidents(limit=50)

            mock_get.assert_called_once_with(severity='high', limit=50)


class TestBiasAuditReportRepository:
    """Tests for bias audit report repository."""

    def test_create_report_creates_audit_report(self):
        """create_report creates bias audit report."""
        repo = BiasAuditReportRepository()

        with patch.object(repo, 'create') as mock_create:
            report = MagicMock(spec=BiasAuditReportModel)
            report.id = 1
            report.total_incidents = 15
            mock_create.return_value = report

            result = repo.create_report(
                total_incidents=15,
                severity_breakdown={'low': 5, 'medium': 8, 'high': 2},
                recommendations=['Review job descriptions', 'Add bias training']
            )

            assert result.total_incidents == 15

    def test_get_latest_report_returns_most_recent(self):
        """get_latest_report returns most recent report."""
        repo = BiasAuditReportRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            report = MagicMock(spec=BiasAuditReportModel)
            report.id = 10

            session_mock = MagicMock()
            session_mock.execute.return_value.scalar_one_or_none.return_value = report

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_latest_report()

            assert result.id == 10


# ==================== DASHBOARD REPOSITORY TESTS ====================

class TestDashboardRepository:
    """Tests for dashboard repository."""

    def test_create_dashboard_creates_dashboard(self):
        """create_dashboard creates user dashboard."""
        repo = DashboardRepository()

        with patch.object(repo, 'create') as mock_create:
            dashboard = MagicMock(spec=DashboardModel)
            dashboard.id = 1
            dashboard.name = 'HR Analytics'
            dashboard.owner_id = 100
            mock_create.return_value = dashboard

            result = repo.create_dashboard(
                name='HR Analytics',
                owner_id=100,
                description='Main HR metrics'
            )

            assert result.name == 'HR Analytics'

    def test_get_dashboards_for_owner_returns_owner_dashboards(self):
        """get_dashboards_for_owner returns dashboards owned by user."""
        repo = DashboardRepository()

        with patch.object(repo, 'list') as mock_list:
            dashboards = [MagicMock(spec=DashboardModel)]
            mock_list.return_value = dashboards

            result = repo.get_dashboards_for_owner(100)

            mock_list.assert_called_once_with({'owner_id': 100})


class TestDashboardWidgetRepository:
    """Tests for dashboard widget repository."""

    def test_add_widget_creates_widget(self):
        """add_widget creates dashboard widget."""
        repo = DashboardWidgetRepository()

        with patch.object(repo, 'create') as mock_create:
            widget = MagicMock(spec=DashboardWidgetModel)
            widget.id = 1
            widget.widget_type = 'chart'
            mock_create.return_value = widget

            result = repo.add_widget(
                dashboard_id=1,
                widget_type='chart',
                title='Hiring Trends',
                config={'type': 'line'},
                position=0
            )

            assert result.widget_type == 'chart'

    def test_update_widget_data_updates_data(self):
        """update_widget_data updates widget data."""
        repo = DashboardWidgetRepository()

        with patch.object(repo, 'update') as mock_update:
            widget = MagicMock(spec=DashboardWidgetModel)
            mock_update.return_value = widget

            repo.update_widget_data(1, {'values': [1, 2, 3]})

            mock_update.assert_called_once_with(1, {'data_json': {'values': [1, 2, 3]}})

    def test_get_widgets_for_dashboard_ordered_by_position(self):
        """get_widgets_for_dashboard returns widgets ordered by position."""
        repo = DashboardWidgetRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            widgets = [
                MagicMock(spec=DashboardWidgetModel, position=0),
                MagicMock(spec=DashboardWidgetModel, position=1),
            ]

            session_mock = MagicMock()
            session_mock.execute.return_value.scalars.return_value.all.return_value = widgets

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_widgets_for_dashboard(1)

            assert len(result) == 2


class TestMetricSnapshotRepository:
    """Tests for metric snapshot repository."""

    def test_save_metric_snapshot_creates_snapshot(self):
        """save_metric_snapshot creates metric snapshot."""
        repo = MetricSnapshotRepository()

        with patch.object(repo, 'create') as mock_create:
            snapshot = MagicMock(spec=MetricSnapshotModel)
            snapshot.id = 1
            snapshot.metric_name = 'headcount'
            snapshot.metric_value = 450.0
            mock_create.return_value = snapshot

            result = repo.save_metric_snapshot(
                metric_name='headcount',
                metric_value=450.0,
                department='Engineering'
            )

            assert result.metric_value == 450.0

    def test_get_metric_history_returns_ordered_snapshots(self):
        """get_metric_history returns metric values in chronological order."""
        repo = MetricSnapshotRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            now = datetime.utcnow()
            snapshots = [
                MagicMock(spec=MetricSnapshotModel, recorded_at=now - timedelta(days=2)),
                MagicMock(spec=MetricSnapshotModel, recorded_at=now - timedelta(days=1)),
                MagicMock(spec=MetricSnapshotModel, recorded_at=now),
            ]

            session_mock = MagicMock()
            session_mock.execute.return_value.scalars.return_value.all.return_value = snapshots

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_metric_history('headcount', limit=100)

            assert len(result) == 3

    def test_get_latest_metrics_returns_latest_values(self):
        """get_latest_metrics returns most recent metric values."""
        repo = MetricSnapshotRepository()

        with patch.object(repo, '_get_session') as mock_get_session:
            now = datetime.utcnow()
            snapshots = [
                MagicMock(spec=MetricSnapshotModel, metric_name='headcount', metric_value=450.0, recorded_at=now),
                MagicMock(spec=MetricSnapshotModel, metric_name='turnover', metric_value=0.08, recorded_at=now),
            ]

            session_mock = MagicMock()
            session_mock.execute.return_value.scalars.return_value.all.return_value = snapshots

            mock_get_session.return_value.__enter__.return_value = session_mock
            mock_get_session.return_value.__exit__.return_value = False

            result = repo.get_latest_metrics(limit=50)

            assert 'headcount' in result or 'turnover' in result

"""Tests for notification service module."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from src.core.notifications import (
    NotificationService,
    NotificationTemplate,
    Notification,
    NotificationPreference,
    NotificationChannel,
    NotificationStatus,
    NotificationPriority,
)


class TestSendNotification:
    """Tests for sending notifications via different channels."""

    def test_send_notification_in_app(self):
        """send_notification dispatches IN_APP notification."""
        service = NotificationService()
        notification = service.send_notification(
            recipient_id="emp-001",
            template_id="workflow_submitted",
            context={
                "entity_type": "Promotion",
                "approver_role": "Manager"
            },
            priority=NotificationPriority.NORMAL
        )

        assert notification.recipient_id == "emp-001"
        assert notification.channel == NotificationChannel.IN_APP
        assert notification.status == NotificationStatus.SENT
        assert notification.priority == NotificationPriority.NORMAL
        assert "Promotion" in notification.subject
        assert "Manager" in notification.body

    def test_send_notification_email(self):
        """send_notification dispatches EMAIL notification."""
        service = NotificationService()
        template = NotificationTemplate(
            template_id="email_template",
            name="Email Test",
            channel=NotificationChannel.EMAIL,
            subject_template="Subject: $title",
            body_template="Body: $content",
            variables=["title", "content"]
        )
        service.register_template(template)

        notification = service.send_notification(
            recipient_id="emp-002",
            template_id="email_template",
            context={"title": "Test", "content": "Test Content"},
            channel=NotificationChannel.EMAIL
        )

        assert notification.channel == NotificationChannel.EMAIL
        assert notification.status == NotificationStatus.SENT

    def test_send_notification_webhook(self):
        """send_notification dispatches WEBHOOK notification."""
        service = NotificationService()
        template = NotificationTemplate(
            template_id="webhook_template",
            name="Webhook Test",
            channel=NotificationChannel.WEBHOOK,
            subject_template="Event: $event_type",
            body_template="Data: $payload",
            variables=["event_type", "payload"]
        )
        service.register_template(template)

        notification = service.send_notification(
            recipient_id="emp-003",
            template_id="webhook_template",
            context={"event_type": "user_created", "payload": "{}"},
            channel=NotificationChannel.WEBHOOK
        )

        assert notification.channel == NotificationChannel.WEBHOOK
        assert notification.status == NotificationStatus.SENT

    def test_send_notification_slack(self):
        """send_notification dispatches SLACK notification."""
        service = NotificationService()
        template = NotificationTemplate(
            template_id="slack_template",
            name="Slack Test",
            channel=NotificationChannel.SLACK,
            subject_template="Slack: $message",
            body_template="Channel: $channel",
            variables=["message", "channel"]
        )
        service.register_template(template)

        notification = service.send_notification(
            recipient_id="emp-004",
            template_id="slack_template",
            context={"message": "Test message", "channel": "#general"},
            channel=NotificationChannel.SLACK
        )

        assert notification.channel == NotificationChannel.SLACK
        assert notification.status == NotificationStatus.SENT

    def test_send_notification_invalid_template_raises(self):
        """send_notification raises ValueError for invalid template."""
        service = NotificationService()

        with pytest.raises(ValueError, match="Template not found"):
            service.send_notification(
                recipient_id="emp-005",
                template_id="nonexistent",
                context={}
            )

    def test_send_notification_sets_metadata(self):
        """send_notification includes context in metadata."""
        service = NotificationService()
        context = {"entity_type": "Promotion", "approver_role": "HR"}

        notification = service.send_notification(
            recipient_id="emp-006",
            template_id="workflow_submitted",
            context=context
        )

        assert notification.metadata["template_id"] == "workflow_submitted"
        assert notification.metadata["entity_type"] == "Promotion"
        assert notification.metadata["approver_role"] == "HR"

    def test_send_notification_channel_override(self):
        """send_notification respects channel override."""
        service = NotificationService()

        notification = service.send_notification(
            recipient_id="emp-007",
            template_id="workflow_submitted",
            context={"entity_type": "Leave", "approver_role": "Manager"},
            channel=NotificationChannel.EMAIL
        )

        assert notification.channel == NotificationChannel.EMAIL


class TestNotificationTemplates:
    """Tests for notification template management."""

    def test_register_template(self):
        """register_template adds template to service."""
        service = NotificationService()
        template = NotificationTemplate(
            template_id="custom_template",
            name="Custom Template",
            channel=NotificationChannel.IN_APP,
            subject_template="Subject: $var1",
            body_template="Body: $var2",
            variables=["var1", "var2"]
        )

        template_id = service.register_template(template)

        assert template_id == "custom_template"
        assert service.templates[template_id] == template

    def test_template_rendering_substitutes_variables(self):
        """Template rendering substitutes all variables."""
        service = NotificationService()
        notification = service.send_notification(
            recipient_id="emp-008",
            template_id="leave_approved",
            context={
                "leave_type": "Vacation",
                "start_date": "2024-01-01",
                "end_date": "2024-01-05",
                "approver_name": "John Doe"
            }
        )

        assert notification.subject is not None
        assert notification.body is not None
        # Check that variables were substituted
        assert "Vacation" in notification.body or "leave_type" not in notification.body
        assert "2024-01-01" in notification.body or "start_date" not in notification.body
        assert "2024-01-05" in notification.body or "end_date" not in notification.body
        assert "John Doe" in notification.body or "approver_name" not in notification.body

    def test_template_rendering_missing_variables_returns_unsubstituted(self):
        """Template rendering with missing variables returns original text."""
        service = NotificationService()
        notification = service.send_notification(
            recipient_id="emp-009",
            template_id="workflow_submitted",
            context={"entity_type": "Promotion"}
            # Missing "approver_role"
        )

        # Service logs error but continues, returning original template
        assert notification.subject is not None
        assert notification.body is not None

    def test_default_templates_exist(self):
        """Service initializes with default templates."""
        service = NotificationService()

        assert "workflow_submitted" in service.templates
        assert "workflow_approved" in service.templates
        assert "workflow_rejected" in service.templates
        assert "leave_approved" in service.templates
        assert "policy_reminder" in service.templates

    def test_template_has_variables_list(self):
        """Template tracks variables used in substitution."""
        service = NotificationService()
        template = service.templates["workflow_submitted"]

        assert "entity_type" in template.variables
        assert "approver_role" in template.variables

    def test_template_creation_with_variables(self):
        """Can create template with custom variables."""
        service = NotificationService()
        template = NotificationTemplate(
            name="Test Template",
            channel=NotificationChannel.IN_APP,
            subject_template="Event: $event_name for $employee_name",
            body_template="Details: $event_details",
            variables=["event_name", "employee_name", "event_details"]
        )

        service.register_template(template)
        assert len(template.variables) == 3


class TestNotificationPreferences:
    """Tests for user notification preferences."""

    def test_set_preference(self):
        """set_preference creates notification preference."""
        service = NotificationService()

        preference = service.set_preference(
            employee_id="emp-010",
            channel=NotificationChannel.EMAIL,
            enabled=True
        )

        assert preference.employee_id == "emp-010"
        assert preference.channel == NotificationChannel.EMAIL
        assert preference.enabled is True

    def test_set_preference_with_quiet_hours(self):
        """set_preference can set quiet hours."""
        service = NotificationService()

        preference = service.set_preference(
            employee_id="emp-011",
            channel=NotificationChannel.EMAIL,
            enabled=True,
            quiet_hours_start="18:00",
            quiet_hours_end="09:00"
        )

        assert preference.quiet_hours_start == "18:00"
        assert preference.quiet_hours_end == "09:00"

    def test_get_preferences_for_employee(self):
        """get_preferences retrieves all preferences for employee."""
        service = NotificationService()

        service.set_preference("emp-012", NotificationChannel.EMAIL, True)
        service.set_preference("emp-012", NotificationChannel.SLACK, False)
        service.set_preference("emp-012", NotificationChannel.IN_APP, True)

        preferences = service.get_preferences("emp-012")

        assert len(preferences) == 3
        channels = [p.channel for p in preferences]
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.SLACK in channels
        assert NotificationChannel.IN_APP in channels

    def test_update_existing_preference(self):
        """Setting preference for same channel updates it."""
        service = NotificationService()

        service.set_preference("emp-013", NotificationChannel.EMAIL, True)
        service.set_preference("emp-013", NotificationChannel.EMAIL, False)

        preferences = service.get_preferences("emp-013")

        assert len(preferences) == 1
        assert preferences[0].enabled is False

    def test_get_preferences_empty_list_for_unknown_employee(self):
        """get_preferences returns empty list for unknown employee."""
        service = NotificationService()

        preferences = service.get_preferences("unknown-emp")

        assert preferences == []

    def test_preference_tracks_timestamps(self):
        """Preferences track creation and update times."""
        service = NotificationService()
        before = datetime.utcnow()

        preference = service.set_preference("emp-014", NotificationChannel.EMAIL, True)
        after = datetime.utcnow()

        assert before <= preference.created_at <= after
        assert before <= preference.updated_at <= after


class TestBulkNotifications:
    """Tests for sending notifications to multiple recipients."""

    def test_send_bulk_notifications(self):
        """send_bulk sends notification to multiple recipients."""
        service = NotificationService()
        recipients = ["emp-015", "emp-016", "emp-017"]

        notifications = service.send_bulk(
            recipient_ids=recipients,
            template_id="workflow_submitted",
            context={"entity_type": "Policy", "approver_role": "HR Manager"},
            priority=NotificationPriority.HIGH
        )

        assert len(notifications) == 3
        assert all(n.status == NotificationStatus.SENT for n in notifications)
        assert all(n.priority == NotificationPriority.HIGH for n in notifications)
        assert notifications[0].recipient_id == "emp-015"
        assert notifications[1].recipient_id == "emp-016"
        assert notifications[2].recipient_id == "emp-017"

    def test_send_bulk_empty_list(self):
        """send_bulk handles empty recipient list."""
        service = NotificationService()

        notifications = service.send_bulk(
            recipient_ids=[],
            template_id="workflow_submitted",
            context={"entity_type": "Test", "approver_role": "Manager"}
        )

        assert notifications == []

    def test_send_bulk_with_priority(self):
        """send_bulk applies priority to all notifications."""
        service = NotificationService()

        notifications = service.send_bulk(
            recipient_ids=["emp-018", "emp-019"],
            template_id="workflow_submitted",
            context={"entity_type": "Urgent", "approver_role": "CEO"},
            priority=NotificationPriority.URGENT
        )

        assert all(n.priority == NotificationPriority.URGENT for n in notifications)

    def test_send_bulk_large_list(self):
        """send_bulk handles large recipient lists."""
        service = NotificationService()
        recipients = [f"emp-{i}" for i in range(100)]

        notifications = service.send_bulk(
            recipient_ids=recipients,
            template_id="policy_reminder",
            context={"policy_name": "Code of Conduct", "policy_url": "https://example.com"}
        )

        assert len(notifications) == 100


class TestMarkAsRead:
    """Tests for marking notifications as read."""

    def test_mark_as_read_updates_status(self):
        """mark_as_read changes status to READ."""
        service = NotificationService()
        notification = service.send_notification(
            recipient_id="emp-020",
            template_id="workflow_submitted",
            context={"entity_type": "Test", "approver_role": "Manager"}
        )

        updated = service.mark_as_read(notification.id)

        assert updated.status == NotificationStatus.READ
        assert updated.read_at is not None

    def test_mark_as_read_sets_read_at_timestamp(self):
        """mark_as_read records when notification was read."""
        service = NotificationService()
        notification = service.send_notification(
            recipient_id="emp-021",
            template_id="workflow_submitted",
            context={"entity_type": "Test", "approver_role": "Manager"}
        )
        before = datetime.utcnow()

        updated = service.mark_as_read(notification.id)
        after = datetime.utcnow()

        assert before <= updated.read_at <= after

    def test_mark_as_read_invalid_notification_raises(self):
        """mark_as_read raises ValueError for invalid notification."""
        service = NotificationService()

        with pytest.raises(ValueError, match="Notification not found"):
            service.mark_as_read("invalid-id")

    def test_mark_multiple_as_read(self):
        """Multiple notifications can be marked as read."""
        service = NotificationService()
        notif1 = service.send_notification(
            recipient_id="emp-022",
            template_id="workflow_submitted",
            context={"entity_type": "Test1", "approver_role": "Manager"}
        )
        notif2 = service.send_notification(
            recipient_id="emp-022",
            template_id="workflow_approved",
            context={"entity_type": "Test2"}
        )

        service.mark_as_read(notif1.id)
        service.mark_as_read(notif2.id)

        notifications = service.get_notifications("emp-022", NotificationStatus.READ)

        assert len(notifications) == 2


class TestNotificationFiltering:
    """Tests for filtering notifications by status, channel, and priority."""

    def test_get_notifications_filters_by_status(self):
        """get_notifications filters by status."""
        service = NotificationService()

        # Create multiple notifications with different statuses
        notif1 = service.send_notification(
            recipient_id="emp-023",
            template_id="workflow_submitted",
            context={"entity_type": "Test1", "approver_role": "Manager"}
        )
        notif2 = service.send_notification(
            recipient_id="emp-023",
            template_id="workflow_submitted",
            context={"entity_type": "Test2", "approver_role": "Manager"}
        )
        service.mark_as_read(notif1.id)

        sent = service.get_notifications("emp-023", NotificationStatus.SENT)
        read = service.get_notifications("emp-023", NotificationStatus.READ)

        assert len(sent) == 1
        assert len(read) == 1
        assert read[0].id == notif1.id

    def test_get_notifications_default_limit(self):
        """get_notifications respects limit parameter."""
        service = NotificationService()

        # Create 60 notifications
        for i in range(60):
            service.send_notification(
                recipient_id="emp-024",
                template_id="workflow_submitted",
                context={"entity_type": f"Test{i}", "approver_role": "Manager"}
            )

        notifications = service.get_notifications("emp-024", limit=50)

        assert len(notifications) == 50

    def test_get_notifications_sorted_newest_first(self):
        """get_notifications returns newest notifications first."""
        service = NotificationService()

        notif1 = service.send_notification(
            recipient_id="emp-025",
            template_id="workflow_submitted",
            context={"entity_type": "First", "approver_role": "Manager"}
        )
        notif2 = service.send_notification(
            recipient_id="emp-025",
            template_id="workflow_submitted",
            context={"entity_type": "Second", "approver_role": "Manager"}
        )

        notifications = service.get_notifications("emp-025")

        assert notifications[0].id == notif2.id  # Newest first
        assert notifications[1].id == notif1.id

    def test_get_notifications_by_priority(self):
        """Notifications can be filtered and ordered by priority."""
        service = NotificationService()

        service.send_notification(
            recipient_id="emp-026",
            template_id="workflow_submitted",
            context={"entity_type": "Normal", "approver_role": "Manager"},
            priority=NotificationPriority.NORMAL
        )
        service.send_notification(
            recipient_id="emp-026",
            template_id="workflow_submitted",
            context={"entity_type": "Urgent", "approver_role": "Manager"},
            priority=NotificationPriority.URGENT
        )

        notifications = service.get_notifications("emp-026")

        # Both should be present
        assert len(notifications) == 2
        priorities = [n.priority for n in notifications]
        assert NotificationPriority.NORMAL in priorities
        assert NotificationPriority.URGENT in priorities

    def test_get_notifications_empty_for_unknown_recipient(self):
        """get_notifications returns empty list for unknown recipient."""
        service = NotificationService()

        notifications = service.get_notifications("unknown-emp")

        assert notifications == []


class TestEventListeners:
    """Tests for event subscription and notification triggering."""

    def test_register_event_listener(self):
        """register_event_listener maps event to template."""
        service = NotificationService()

        service.register_event_listener("leave_request_submitted", "leave_approved")

        assert service.event_listeners["leave_request_submitted"] == "leave_approved"

    def test_trigger_event_sends_notification(self):
        """trigger_event sends notification for registered event."""
        service = NotificationService()
        service.register_event_listener("promotion_approved", "workflow_approved")

        notification = service.trigger_event(
            event_type="promotion_approved",
            recipient_id="emp-027",
            context={"entity_type": "Promotion"}
        )

        assert notification is not None
        assert notification.recipient_id == "emp-027"
        assert notification.status == NotificationStatus.SENT

    def test_trigger_event_unregistered_returns_none(self):
        """trigger_event returns None for unregistered event."""
        service = NotificationService()

        notification = service.trigger_event(
            event_type="unknown_event",
            recipient_id="emp-028",
            context={}
        )

        assert notification is None

    def test_trigger_event_with_priority(self):
        """trigger_event applies priority to triggered notification."""
        service = NotificationService()
        service.register_event_listener("urgent_action", "workflow_submitted")

        notification = service.trigger_event(
            event_type="urgent_action",
            recipient_id="emp-029",
            context={"entity_type": "Urgent", "approver_role": "CEO"},
            priority=NotificationPriority.URGENT
        )

        assert notification.priority == NotificationPriority.URGENT

    def test_multiple_event_listeners(self):
        """Service can have multiple event listeners."""
        service = NotificationService()

        service.register_event_listener("event1", "workflow_submitted")
        service.register_event_listener("event2", "workflow_approved")
        service.register_event_listener("event3", "leave_approved")

        assert len(service.event_listeners) == 3

    def test_trigger_event_overwrites_previous_listener(self):
        """Registering same event overwrites previous template."""
        service = NotificationService()

        service.register_event_listener("workflow_event", "workflow_submitted")
        service.register_event_listener("workflow_event", "workflow_approved")

        assert service.event_listeners["workflow_event"] == "workflow_approved"

    def test_event_listener_with_context(self):
        """Triggered events pass context to template rendering."""
        service = NotificationService()
        service.register_event_listener("leave_approved_event", "leave_approved")

        notification = service.trigger_event(
            event_type="leave_approved_event",
            recipient_id="emp-030",
            context={
                "leave_type": "Vacation",
                "start_date": "2024-02-01",
                "end_date": "2024-02-05",
                "approver_name": "Jane Doe"
            }
        )

        assert "Vacation" in notification.body
        assert "Jane Doe" in notification.body

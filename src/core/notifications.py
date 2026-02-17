"""
NOTIF-001: Notification Service Module
Centralized notification service for HR multi-agent platform.
Supports multiple channels, templates, and user preferences.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from string import Template
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ===== ENUMS =====


class NotificationChannel(str, Enum):
    """Notification delivery channels."""

    IN_APP = "in_app"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


class NotificationStatus(str, Enum):
    """Notification delivery status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class NotificationPriority(str, Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# ===== PYDANTIC MODELS =====


class NotificationTemplate(BaseModel):
    """Template for notification messages."""

    template_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # Human-readable name
    channel: NotificationChannel
    subject_template: str  # Uses $variable syntax
    body_template: str  # Uses $variable syntax
    variables: List[str] = Field(default_factory=list)  # List of variable names
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=False)


class Notification(BaseModel):
    """Notification instance."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recipient_id: str
    channel: NotificationChannel
    subject: str
    body: str
    status: NotificationStatus = NotificationStatus.PENDING
    priority: NotificationPriority = NotificationPriority.NORMAL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=False)


class NotificationPreference(BaseModel):
    """User notification preferences."""

    employee_id: str
    channel: NotificationChannel
    enabled: bool = True
    quiet_hours_start: Optional[str] = None  # HH:MM format
    quiet_hours_end: Optional[str] = None  # HH:MM format
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(use_enum_values=False)


# ===== MAIN SERVICE CLASS =====


class NotificationService:
    """
    Centralized notification service for HR platform.

    Manages notification templates, delivery, user preferences, and
    event listeners. Uses in-memory storage with extensible architecture
    for database persistence.
    """

    def __init__(self):
        """Initialize notification service."""
        self.templates: Dict[str, NotificationTemplate] = {}
        self.notifications: Dict[str, Notification] = {}
        self.preferences: Dict[str, List[NotificationPreference]] = {}
        self.event_listeners: Dict[str, str] = {}
        self._init_default_templates()

    def _init_default_templates(self) -> None:
        """Initialize default notification templates."""
        default_templates = [
            NotificationTemplate(
                template_id="workflow_submitted",
                name="Workflow Submitted",
                channel=NotificationChannel.IN_APP,
                subject_template="Workflow Submitted: $entity_type",
                body_template=(
                    "Your $entity_type workflow has been submitted for approval. "
                    "It is now pending review by $approver_role."
                ),
                variables=["entity_type", "approver_role"],
            ),
            NotificationTemplate(
                template_id="workflow_approved",
                name="Workflow Approved",
                channel=NotificationChannel.IN_APP,
                subject_template="Workflow Approved: $entity_type",
                body_template=(
                    "Your $entity_type workflow has been approved. "
                    "The requested changes are being processed."
                ),
                variables=["entity_type"],
            ),
            NotificationTemplate(
                template_id="workflow_rejected",
                name="Workflow Rejected",
                channel=NotificationChannel.IN_APP,
                subject_template="Workflow Rejected: $entity_type",
                body_template=(
                    "Your $entity_type workflow was rejected. "
                    "Reason: $rejection_reason. Please contact $contact_email for details."
                ),
                variables=["entity_type", "rejection_reason", "contact_email"],
            ),
            NotificationTemplate(
                template_id="leave_approved",
                name="Leave Request Approved",
                channel=NotificationChannel.IN_APP,
                subject_template="Leave Request Approved",
                body_template=(
                    "Your leave request for $leave_type from $start_date to $end_date "
                    "has been approved by $approver_name."
                ),
                variables=["leave_type", "start_date", "end_date", "approver_name"],
            ),
            NotificationTemplate(
                template_id="policy_reminder",
                name="Policy Reminder",
                channel=NotificationChannel.IN_APP,
                subject_template="Important Policy Reminder: $policy_name",
                body_template=(
                    "This is a reminder about our $policy_name policy. "
                    "Please review it at your earliest convenience: $policy_url"
                ),
                variables=["policy_name", "policy_url"],
            ),
        ]

        for template in default_templates:
            self.templates[template.template_id] = template

    # ===== PUBLIC API METHODS =====

    def send_notification(
        self,
        recipient_id: str,
        template_id: str,
        context: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channel: Optional[NotificationChannel] = None,
    ) -> Notification:
        """
        Send a notification to a recipient.

        Args:
            recipient_id: ID of recipient employee
            template_id: ID of notification template
            context: Dict of variables to substitute in template
            priority: Priority level for notification
            channel: Override template's default channel (optional)

        Returns:
            Notification instance

        Raises:
            ValueError: If template not found
        """
        if template_id not in self.templates:
            raise ValueError(f"Template not found: {template_id}")

        template = self.templates[template_id]
        use_channel = channel or template.channel

        # Render template
        subject, body = self._render_template(template, context)

        # Create notification
        notification = Notification(
            recipient_id=recipient_id,
            channel=use_channel,
            subject=subject,
            body=body,
            priority=priority,
            metadata={"template_id": template_id, **context},
        )

        # Check quiet hours
        if not self._check_quiet_hours(recipient_id, use_channel):
            logger.info(
                f"Notification {notification.id} queued due to quiet hours " f"for {recipient_id}"
            )

        # Dispatch
        success = self._dispatch_notification(notification)

        if success:
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
        else:
            notification.status = NotificationStatus.FAILED

        # Store
        self.notifications[notification.id] = notification

        logger.info(
            f"Notification {notification.id} sent to {recipient_id} " f"via {use_channel.value}"
        )

        return notification

    def send_bulk(
        self,
        recipient_ids: List[str],
        template_id: str,
        context: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> List[Notification]:
        """
        Send notification to multiple recipients.

        Args:
            recipient_ids: List of recipient IDs
            template_id: ID of notification template
            context: Context variables for template
            priority: Priority level

        Returns:
            List of created notifications
        """
        notifications = []

        for recipient_id in recipient_ids:
            notification = self.send_notification(
                recipient_id=recipient_id,
                template_id=template_id,
                context=context,
                priority=priority,
            )
            notifications.append(notification)

        logger.info(f"Bulk notification sent to {len(recipient_ids)} recipients")

        return notifications

    def get_notifications(
        self, recipient_id: str, status_filter: Optional[NotificationStatus] = None, limit: int = 50
    ) -> List[Notification]:
        """
        Get notifications for a recipient.

        Args:
            recipient_id: Employee ID
            status_filter: Filter by status (optional)
            limit: Max number of notifications

        Returns:
            List of notifications
        """
        notifications = [n for n in self.notifications.values() if n.recipient_id == recipient_id]

        if status_filter:
            notifications = [n for n in notifications if n.status == status_filter]

        # Sort by created_at, newest first
        notifications.sort(key=lambda n: n.created_at, reverse=True)

        return notifications[:limit]

    def mark_as_read(self, notification_id: str) -> Notification:
        """
        Mark notification as read.

        Args:
            notification_id: ID of notification

        Returns:
            Updated notification

        Raises:
            ValueError: If notification not found
        """
        if notification_id not in self.notifications:
            raise ValueError(f"Notification not found: {notification_id}")

        notification = self.notifications[notification_id]
        notification.status = NotificationStatus.READ
        notification.read_at = datetime.utcnow()

        return notification

    def register_template(self, template: NotificationTemplate) -> str:
        """
        Register a new notification template.

        Args:
            template: NotificationTemplate to register

        Returns:
            Template ID
        """
        self.templates[template.template_id] = template
        logger.info(f"Template registered: {template.template_id}")

        return template.template_id

    def set_preference(
        self,
        employee_id: str,
        channel: NotificationChannel,
        enabled: bool,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
    ) -> NotificationPreference:
        """
        Set notification preference for employee.

        Args:
            employee_id: Employee ID
            channel: Notification channel
            enabled: Whether notifications are enabled
            quiet_hours_start: Quiet hours start time (HH:MM)
            quiet_hours_end: Quiet hours end time (HH:MM)

        Returns:
            NotificationPreference instance
        """
        preference = NotificationPreference(
            employee_id=employee_id,
            channel=channel,
            enabled=enabled,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
        )

        if employee_id not in self.preferences:
            self.preferences[employee_id] = []

        # Update existing preference or add new
        existing = [p for p in self.preferences[employee_id] if p.channel == channel]

        if existing:
            self.preferences[employee_id].remove(existing[0])

        self.preferences[employee_id].append(preference)

        logger.info(f"Preference set for {employee_id} on {channel.value}: " f"enabled={enabled}")

        return preference

    def get_preferences(self, employee_id: str) -> List[NotificationPreference]:
        """
        Get all notification preferences for employee.

        Args:
            employee_id: Employee ID

        Returns:
            List of NotificationPreference instances
        """
        return self.preferences.get(employee_id, [])

    def register_event_listener(self, event_type: str, template_id: str) -> None:
        """
        Register event listener mapping.

        Args:
            event_type: Type of event (e.g., 'workflow_approved')
            template_id: Template to use for this event
        """
        self.event_listeners[event_type] = template_id
        logger.debug(f"Event listener registered: {event_type} -> {template_id}")

    def trigger_event(
        self,
        event_type: str,
        recipient_id: str,
        context: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> Optional[Notification]:
        """
        Trigger notification based on event type.

        Args:
            event_type: Type of event
            recipient_id: Recipient ID
            context: Event context
            priority: Notification priority

        Returns:
            Notification instance or None if no listener registered
        """
        if event_type not in self.event_listeners:
            logger.warning(f"No listener registered for event: {event_type}")
            return None

        template_id = self.event_listeners[event_type]

        return self.send_notification(
            recipient_id=recipient_id, template_id=template_id, context=context, priority=priority
        )

    # ===== PRIVATE HELPER METHODS =====

    def _render_template(
        self, template: NotificationTemplate, context: Dict[str, Any]
    ) -> tuple[str, str]:
        """
        Render template with context variables.

        Args:
            template: NotificationTemplate to render
            context: Variables for substitution

        Returns:
            Tuple of (subject, body)
        """
        try:
            subject_template = Template(template.subject_template)
            body_template = Template(template.body_template)

            subject = subject_template.substitute(context)
            body = body_template.substitute(context)

            return subject, body

        except KeyError as e:
            logger.error(f"Missing variable in template: {e}")
            # Return with unsubstituted variables
            return template.subject_template, template.body_template

    def _check_quiet_hours(self, employee_id: str, channel: NotificationChannel) -> bool:
        """
        Check if employee is within quiet hours.

        Args:
            employee_id: Employee ID
            channel: Notification channel

        Returns:
            True if not in quiet hours or preference disabled
        """
        preferences = self.get_preferences(employee_id)

        for pref in preferences:
            if pref.channel != channel:
                continue

            if not pref.enabled:
                return False

            if not pref.quiet_hours_start or not pref.quiet_hours_end:
                continue

            # Check current time against quiet hours
            now = datetime.utcnow()
            current_time = f"{now.hour:02d}:{now.minute:02d}"

            if pref.quiet_hours_start <= current_time <= pref.quiet_hours_end:
                return False

        return True

    def _dispatch_notification(self, notification: Notification) -> bool:
        """
        Dispatch notification via appropriate channel.

        Args:
            notification: Notification to dispatch

        Returns:
            True if dispatch succeeded
        """
        if notification.channel == NotificationChannel.IN_APP:
            return self._dispatch_in_app(notification)

        elif notification.channel == NotificationChannel.EMAIL:
            return self._dispatch_email(notification)

        elif notification.channel == NotificationChannel.WEBHOOK:
            return self._dispatch_webhook(notification)

        elif notification.channel == NotificationChannel.SLACK:
            return self._dispatch_slack(notification)

        else:
            logger.error(f"Unknown channel: {notification.channel}")
            return False

    def _dispatch_in_app(self, notification: Notification) -> bool:
        """
        Dispatch in-app notification by persisting to database or in-memory store.

        Stores the notification so it can be retrieved by the frontend
        via the notifications API endpoint.

        Args:
            notification: Notification to dispatch

        Returns:
            True if successful
        """
        try:
            from ..core.database import SessionLocal

            if SessionLocal is not None:
                try:
                    from sqlalchemy import text
                    import json as _json

                    session = SessionLocal()
                    try:
                        session.execute(
                            text("""
                                INSERT INTO in_app_notifications
                                (id, recipient_id, subject, body, priority, is_read, created_at, metadata)
                                VALUES (:id, :recipient_id, :subject, :body, :priority, :is_read, :created_at, :metadata)
                            """),
                            {
                                "id": notification.id,
                                "recipient_id": notification.recipient_id,
                                "subject": notification.subject,
                                "body": notification.body,
                                "priority": (
                                    notification.priority.value
                                    if notification.priority
                                    else "medium"
                                ),
                                "is_read": False,
                                "created_at": notification.created_at
                                or __import__("datetime").datetime.utcnow(),
                                "metadata": _json.dumps(notification.metadata or {}),
                            },
                        )
                        session.commit()
                        logger.info(
                            f"IN-APP Notification persisted for {notification.recipient_id}: "
                            f"{notification.subject}"
                        )
                        return True
                    except Exception as db_err:
                        session.rollback()
                        raise db_err
                    finally:
                        session.close()
                except Exception as db_err:
                    logger.debug(f"IN-APP DB persist skipped: {db_err}")
                    # Fall through to in-memory store

            # In-memory fallback (development / no DB)
            self._in_app_store = getattr(self, "_in_app_store", [])
            self._in_app_store.append(
                {
                    "id": notification.id,
                    "recipient_id": notification.recipient_id,
                    "subject": notification.subject,
                    "body": notification.body,
                    "priority": notification.priority.value if notification.priority else "medium",
                    "is_read": False,
                    "created_at": str(notification.created_at),
                }
            )
            logger.info(
                f"IN-APP Notification stored in-memory for {notification.recipient_id}: "
                f"{notification.subject}"
            )
            return True
        except Exception as e:
            logger.error(f"IN-APP dispatch failed: {e}")
            return False

    def _dispatch_email(self, notification: Notification) -> bool:
        """
        Dispatch email notification via SMTP.

        Uses SMTP configuration from environment variables:
        - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

        Args:
            notification: Notification to dispatch

        Returns:
            True if successful
        """
        import os

        smtp_host = os.environ.get("SMTP_HOST")
        smtp_from = os.environ.get("SMTP_FROM", "hr-platform@company.com")

        if smtp_host:
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart

                smtp_port = int(os.environ.get("SMTP_PORT", "587"))
                smtp_user = os.environ.get("SMTP_USER", "")
                smtp_pass = os.environ.get("SMTP_PASSWORD", "")

                msg = MIMEMultipart()
                msg["From"] = smtp_from
                msg["To"] = notification.recipient_id  # In production, resolve to real email
                msg["Subject"] = notification.subject
                msg.attach(MIMEText(notification.body, "plain"))

                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.ehlo()
                    if smtp_port == 587:
                        server.starttls()
                    if smtp_user and smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_from, notification.recipient_id, msg.as_string())

                logger.info(f"EMAIL sent to {notification.recipient_id}: {notification.subject}")
                return True
            except Exception as e:
                logger.error(f"EMAIL dispatch failed: {e}")
                return False
        else:
            # Fallback: log the email (development mode)
            logger.info(
                f"EMAIL Notification (dev mode) to {notification.recipient_id}: "
                f"{notification.subject} | {notification.body[:100]}"
            )
            return True

    def _dispatch_webhook(self, notification: Notification) -> bool:
        """
        Dispatch webhook notification to registered HTTP endpoints.

        Uses configuration from environment variables:
        - WEBHOOK_URLS: Comma-separated list of webhook endpoint URLs

        Args:
            notification: Notification to dispatch

        Returns:
            True if successful
        """
        import os
        import json

        webhook_urls = os.environ.get("WEBHOOK_URLS", "")

        if webhook_urls:
            try:
                import urllib.request
                import urllib.error

                payload = json.dumps(
                    {
                        "event": "notification",
                        "recipient": notification.recipient_id,
                        "subject": notification.subject,
                        "body": notification.body,
                        "priority": (
                            notification.priority.value if notification.priority else "medium"
                        ),
                        "channels": (
                            [c.value for c in notification.channels]
                            if notification.channels
                            else []
                        ),
                        "metadata": notification.metadata or {},
                        "timestamp": (
                            notification.created_at.isoformat() if notification.created_at else None
                        ),
                    }
                ).encode("utf-8")

                success = False
                for url in webhook_urls.split(","):
                    url = url.strip()
                    if not url:
                        continue
                    try:
                        req = urllib.request.Request(
                            url,
                            data=payload,
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            resp.read()
                        success = True
                    except Exception as e:
                        logger.warning(f"WEBHOOK failed for {url}: {e}")

                if success:
                    logger.info(
                        f"WEBHOOK sent for {notification.recipient_id}: {notification.subject}"
                    )
                return success
            except Exception as e:
                logger.error(f"WEBHOOK dispatch failed: {e}")
                return False
        else:
            # Fallback: log the webhook (development mode)
            logger.info(
                f"WEBHOOK Notification (dev mode) for {notification.recipient_id}: "
                f"{notification.subject} | {notification.body[:100]}"
            )
            return True

    def _dispatch_slack(self, notification: Notification) -> bool:
        """
        Dispatch Slack notification via webhook or Slack API.

        Uses configuration from environment variables:
        - SLACK_WEBHOOK_URL: Incoming webhook URL for channel notifications
        - SLACK_BOT_TOKEN: Bot token for direct messages (optional)

        Args:
            notification: Notification to dispatch

        Returns:
            True if successful
        """
        import os
        import json

        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        bot_token = os.environ.get("SLACK_BOT_TOKEN")

        if webhook_url or bot_token:
            try:
                import urllib.request
                import urllib.error

                priority_emoji = {
                    NotificationPriority.LOW: ":information_source:",
                    NotificationPriority.MEDIUM: ":large_blue_circle:",
                    NotificationPriority.HIGH: ":warning:",
                    NotificationPriority.URGENT: ":rotating_light:",
                }
                emoji = priority_emoji.get(notification.priority, ":bell:")

                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} {notification.subject}",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": notification.body[:3000],
                        },
                    },
                ]

                if webhook_url:
                    payload = json.dumps({"blocks": blocks}).encode("utf-8")
                    req = urllib.request.Request(
                        webhook_url,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        resp.read()
                elif bot_token:
                    payload = json.dumps(
                        {
                            "channel": notification.recipient_id,
                            "blocks": blocks,
                        }
                    ).encode("utf-8")
                    req = urllib.request.Request(
                        "https://slack.com/api/chat.postMessage",
                        data=payload,
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {bot_token}",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        resp.read()

                logger.info(f"SLACK sent to {notification.recipient_id}: {notification.subject}")
                return True
            except Exception as e:
                logger.error(f"SLACK dispatch failed: {e}")
                return False
        else:
            # Fallback: log the notification (development mode)
            logger.info(
                f"SLACK Notification (dev mode) to {notification.recipient_id}: "
                f"{notification.subject} | {notification.body[:100]}"
            )
            return True

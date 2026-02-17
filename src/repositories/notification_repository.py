"""Notification repository for notification persistence."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin
from src.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class NotificationModel(Base, TimestampMixin):
    """
    SQLAlchemy model for notification instances.

    Represents a single notification with delivery status and metadata.

    Attributes:
        id: Primary key
        recipient_id: Employee ID of recipient
        title: Notification title/subject
        message: Notification message body
        channel: Delivery channel (in_app/email/slack/webhook)
        status: Delivery status (pending/sent/failed/read)
        priority: Notification priority (low/normal/high/urgent)
        template_id: ID of template used (if any)
        created_at: Creation timestamp
        read_at: When notification was read (if any)
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    priority: Mapped[str] = mapped_column(String(50), default="normal", nullable=False)
    template_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<NotificationModel(id={self.id}, recipient_id={self.recipient_id}, status={self.status})>"


class NotificationPreferenceModel(Base, TimestampMixin):
    """
    SQLAlchemy model for user notification preferences.

    Represents user preferences for notification delivery channels and quiet hours.

    Attributes:
        id: Primary key
        user_id: Employee ID
        channel: Notification channel (in_app/email/slack/webhook)
        enabled: Whether notifications are enabled for this channel
        quiet_hours_start: Quiet hours start time (HH:MM format)
        quiet_hours_end: Quiet hours end time (HH:MM format)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    def __repr__(self) -> str:
        return f"<NotificationPreferenceModel(id={self.id}, user_id={self.user_id}, channel={self.channel})>"


class NotificationRepository(BaseRepository[NotificationModel]):
    """
    Repository for notification persistence and retrieval.

    Provides methods for sending, tracking, and managing notifications
    across multiple delivery channels.
    """

    def __init__(self) -> None:
        """Initialize notification repository."""
        super().__init__(NotificationModel)

    def get_notifications(
        self,
        recipient_id: int,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50,
    ) -> List[NotificationModel]:
        """
        Get notifications for recipient with optional filters.

        Args:
            recipient_id: Employee ID of recipient
            status: Filter by delivery status
            channel: Filter by delivery channel
            limit: Maximum results

        Returns:
            List of NotificationModel instances
        """
        filters = {"recipient_id": recipient_id}
        if status:
            filters["status"] = status
        if channel:
            filters["channel"] = channel

        try:
            with self._get_session() as session:
                stmt = select(NotificationModel).where(NotificationModel.recipient_id == recipient_id)

                if status:
                    stmt = stmt.where(NotificationModel.status == status)
                if channel:
                    stmt = stmt.where(NotificationModel.channel == channel)

                stmt = stmt.order_by(NotificationModel.created_at.desc()).limit(limit)
                return session.execute(stmt).scalars().all()
        except Exception as e:
            logger.error(f"Error getting notifications for {recipient_id}: {str(e)}")
            return []

    def create_notification(
        self,
        recipient_id: int,
        title: str,
        message: str,
        channel: str,
        priority: str = "normal",
        template_id: Optional[str] = None,
    ) -> Optional[NotificationModel]:
        """
        Create new notification.

        Args:
            recipient_id: Employee ID of recipient
            title: Notification title
            message: Notification message
            channel: Delivery channel
            priority: Notification priority
            template_id: Template ID if using template

        Returns:
            Created NotificationModel or None on error
        """
        try:
            data = {
                "recipient_id": recipient_id,
                "title": title,
                "message": message,
                "channel": channel,
                "priority": priority,
                "template_id": template_id,
                "status": "pending",
            }
            notification = self.create(data)
            if notification:
                logger.info(f"Created notification: id={notification.id}, recipient={recipient_id}")
            return notification
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            return None

    def mark_as_read(self, notification_id: int) -> Optional[NotificationModel]:
        """
        Mark notification as read.

        Args:
            notification_id: Notification ID

        Returns:
            Updated NotificationModel or None on error
        """
        try:
            notification = self.update(
                notification_id,
                {
                    "status": "read",
                    "read_at": datetime.utcnow(),
                },
            )
            if notification:
                logger.info(f"Marked notification {notification_id} as read")
            return notification
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            return None

    def get_unread_count(self, recipient_id: int) -> int:
        """
        Get count of unread notifications for recipient.

        Args:
            recipient_id: Employee ID of recipient

        Returns:
            Number of unread notifications
        """
        try:
            with self._get_session() as session:
                from sqlalchemy import func
                stmt = select(func.count(NotificationModel.id)).where(
                    (NotificationModel.recipient_id == recipient_id)
                    & (NotificationModel.status == "sent")
                )
                result = session.execute(stmt).scalar()
                return result or 0
        except Exception as e:
            logger.error(f"Error getting unread count for {recipient_id}: {str(e)}")
            return 0

    def mark_sent(self, notification_id: int) -> Optional[NotificationModel]:
        """
        Mark notification as sent.

        Args:
            notification_id: Notification ID

        Returns:
            Updated NotificationModel or None on error
        """
        return self.update(notification_id, {"status": "sent"})

    def mark_failed(self, notification_id: int) -> Optional[NotificationModel]:
        """
        Mark notification as failed.

        Args:
            notification_id: Notification ID

        Returns:
            Updated NotificationModel or None on error
        """
        return self.update(notification_id, {"status": "failed"})


class NotificationPreferenceRepository(BaseRepository[NotificationPreferenceModel]):
    """
    Repository for notification preferences.

    Manages user notification delivery preferences and quiet hours.
    """

    def __init__(self) -> None:
        """Initialize notification preference repository."""
        super().__init__(NotificationPreferenceModel)

    def get_preferences(self, user_id: int) -> List[NotificationPreferenceModel]:
        """
        Get all notification preferences for user.

        Args:
            user_id: Employee ID

        Returns:
            List of NotificationPreferenceModel instances
        """
        return self.list({"user_id": user_id})

    def get_preference(self, user_id: int, channel: str) -> Optional[NotificationPreferenceModel]:
        """
        Get notification preference for specific channel.

        Args:
            user_id: Employee ID
            channel: Notification channel

        Returns:
            NotificationPreferenceModel or None if not found
        """
        try:
            with self._get_session() as session:
                stmt = select(NotificationPreferenceModel).where(
                    (NotificationPreferenceModel.user_id == user_id)
                    & (NotificationPreferenceModel.channel == channel)
                )
                return session.execute(stmt).scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting preference for {user_id}/{channel}: {str(e)}")
            return None

    def save_preference(
        self,
        user_id: int,
        channel: str,
        enabled: bool,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
    ) -> Optional[NotificationPreferenceModel]:
        """
        Save or update notification preference.

        Args:
            user_id: Employee ID
            channel: Notification channel
            enabled: Whether notifications enabled
            quiet_hours_start: Quiet hours start time (HH:MM)
            quiet_hours_end: Quiet hours end time (HH:MM)

        Returns:
            Created or updated NotificationPreferenceModel or None on error
        """
        try:
            existing = self.get_preference(user_id, channel)

            if existing:
                preference = self.update(
                    existing.id,
                    {
                        "enabled": enabled,
                        "quiet_hours_start": quiet_hours_start,
                        "quiet_hours_end": quiet_hours_end,
                    },
                )
                logger.info(f"Updated preference for {user_id}/{channel}")
                return preference
            else:
                data = {
                    "user_id": user_id,
                    "channel": channel,
                    "enabled": enabled,
                    "quiet_hours_start": quiet_hours_start,
                    "quiet_hours_end": quiet_hours_end,
                }
                preference = self.create(data)
                logger.info(f"Created preference for {user_id}/{channel}")
                return preference
        except Exception as e:
            logger.error(f"Error saving preference: {str(e)}")
            return None

    def is_channel_enabled(self, user_id: int, channel: str) -> bool:
        """
        Check if channel is enabled for user.

        Args:
            user_id: Employee ID
            channel: Notification channel

        Returns:
            True if enabled, False otherwise
        """
        try:
            preference = self.get_preference(user_id, channel)
            if not preference:
                return True  # Default to enabled if no preference set
            return preference.enabled
        except Exception as e:
            logger.error(f"Error checking channel enabled: {str(e)}")
            return True

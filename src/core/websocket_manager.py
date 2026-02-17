"""
REALTIME-001: WebSocket Manager for Real-time Notifications.

This module implements WebSocket connection management, message routing, and
real-time event broadcasting for the HR agent platform. Supports user-targeted
messaging, broadcast notifications, and connection lifecycle management.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class WebSocketEvent(str, Enum):
    """WebSocket event types."""
    NOTIFICATION = "notification"
    QUERY_UPDATE = "query_update"
    AGENT_STATUS = "agent_status"
    SYSTEM_ALERT = "system_alert"
    WORKFLOW_UPDATE = "workflow_update"


# ============================================================================
# Pydantic Models
# ============================================================================

class WebSocketMessage(BaseModel):
    """Message sent over WebSocket connection."""
    message_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique message ID")
    event_type: WebSocketEvent = Field(..., description="Type of event")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event payload")
    sender: str = Field(default="system", description="Message sender ID")
    target_user: Optional[str] = Field(None, description="Target user ID (None for broadcast)")
    broadcast: bool = Field(default=False, description="Whether to broadcast to all users")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    priority: str = Field(
        default="medium",
        description="Message priority (low/medium/high)"
    )

    model_config = ConfigDict(use_enum_values=False)


class ConnectionInfo(BaseModel):
    """Information about an active WebSocket connection."""
    connection_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique connection ID")
    user_id: str = Field(..., description="Connected user ID")
    connected_at: datetime = Field(default_factory=datetime.utcnow, description="Connection timestamp")
    last_ping: datetime = Field(default_factory=datetime.utcnow, description="Last ping timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Connection metadata")

    model_config = ConfigDict(use_enum_values=False)


class WebSocketConfig(BaseModel):
    """Configuration for WebSocket manager."""
    max_connections_per_user: int = Field(5, description="Max connections per user")
    ping_interval: int = Field(30, description="Ping interval in seconds")
    ping_timeout: int = Field(10, description="Ping timeout in seconds")
    max_message_size: int = Field(65536, description="Max message size in bytes")
    allowed_events: List[WebSocketEvent] = Field(
        default_factory=lambda: [
            WebSocketEvent.NOTIFICATION,
            WebSocketEvent.QUERY_UPDATE,
            WebSocketEvent.AGENT_STATUS,
            WebSocketEvent.SYSTEM_ALERT,
            WebSocketEvent.WORKFLOW_UPDATE,
        ],
        description="Allowed event types"
    )

    model_config = ConfigDict(use_enum_values=False)


# ============================================================================
# WebSocket Manager
# ============================================================================

class WebSocketManager:
    """
    WebSocket connection and message manager for real-time notifications.

    Manages WebSocket connections, message routing, broadcasting, and
    connection lifecycle with support for user targeting and event filtering.
    """

    def __init__(self, config: WebSocketConfig) -> None:
        """
        Initialize WebSocket manager.

        Args:
            config: WebSocketConfig instance
        """
        self.config = config
        self.connections: Dict[str, ConnectionInfo] = {}
        self.user_connections: Dict[str, List[str]] = {}  # user_id -> [connection_ids]
        self.message_queue: List[WebSocketMessage] = []
        self.stats = {
            'total_connections': 0,
            'messages_sent': 0,
            'messages_broadcast': 0,
            'connected_users': 0,
        }

        logger.info("WebSocketManager initialized")

    def connect(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> ConnectionInfo:
        """
        Register a new WebSocket connection.

        Args:
            user_id: Connected user ID
            metadata: Optional connection metadata

        Returns:
            ConnectionInfo instance

        Raises:
            ValueError: If max connections per user exceeded
        """
        try:
            # Check connection limit
            user_conns = self.user_connections.get(user_id, [])
            if len(user_conns) >= self.config.max_connections_per_user:
                raise ValueError(
                    f"User {user_id} has exceeded max connections "
                    f"({self.config.max_connections_per_user})"
                )

            # Create connection info
            conn_info = ConnectionInfo(
                user_id=user_id,
                metadata=metadata or {}
            )

            self.connections[conn_info.connection_id] = conn_info
            user_conns.append(conn_info.connection_id)

            # Increment connected_users only if this is a new user
            if user_id not in self.user_connections or len(user_conns) == 1:
                self.stats['connected_users'] += 1

            self.user_connections[user_id] = user_conns
            self.stats['total_connections'] += 1

            logger.info(f"User {user_id} connected (connection_id: {conn_info.connection_id})")
            return conn_info

        except Exception as e:
            logger.error(f"Error connecting user {user_id}: {e}")
            raise ValueError(f"Failed to establish connection: {e}")

    def disconnect(self, connection_id: str) -> bool:
        """
        Unregister a WebSocket connection.

        Args:
            connection_id: Connection ID to disconnect

        Returns:
            True if disconnection successful
        """
        try:
            conn_info = self.connections.get(connection_id)
            if not conn_info:
                logger.warning(f"Connection not found: {connection_id}")
                return False

            user_id = conn_info.user_id
            del self.connections[connection_id]

            # Remove from user connections
            if user_id in self.user_connections:
                self.user_connections[user_id].remove(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
                    self.stats['connected_users'] -= 1

            logger.info(f"User {user_id} disconnected (connection_id: {connection_id})")
            return True

        except Exception as e:
            logger.error(f"Error disconnecting {connection_id}: {e}")
            return False

    def send_message(self, connection_id: str, message: WebSocketMessage) -> bool:
        """
        Send message to specific connection.

        Args:
            connection_id: Target connection ID
            message: WebSocketMessage to send

        Returns:
            True if message queued successfully

        Raises:
            ValueError: If connection not found or message invalid
        """
        try:
            if not self._validate_message(message):
                raise ValueError("Invalid message format")

            if connection_id not in self.connections:
                raise ValueError(f"Connection not found: {connection_id}")

            # Check message size
            import json
            msg_size = len(json.dumps(message.model_dump(), default=str))
            if msg_size > self.config.max_message_size:
                raise ValueError(f"Message exceeds max size ({msg_size} > {self.config.max_message_size})")

            self.message_queue.append(message)
            self.stats['messages_sent'] += 1

            conn_info = self.connections[connection_id]
            logger.debug(f"Queued message for {conn_info.user_id} (connection: {connection_id})")
            return True

        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            raise ValueError(f"Failed to send message: {e}")

    def broadcast(self, message: WebSocketMessage, exclude_users: Optional[List[str]] = None) -> int:
        """
        Broadcast message to all or multiple users.

        Args:
            message: WebSocketMessage to broadcast
            exclude_users: Optional list of user IDs to exclude

        Returns:
            Number of connections message sent to

        Raises:
            ValueError: If message invalid
        """
        try:
            if not self._validate_message(message):
                raise ValueError("Invalid message format")

            exclude_users = exclude_users or []
            sent_count = 0

            for connection_id, conn_info in self.connections.items():
                if conn_info.user_id not in exclude_users:
                    try:
                        self.send_message(connection_id, message)
                        sent_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to send to {connection_id}: {e}")

            self.stats['messages_broadcast'] += 1
            logger.info(f"Broadcast message to {sent_count} connections")
            return sent_count

        except Exception as e:
            logger.error(f"Error broadcasting message: {e}")
            raise ValueError(f"Failed to broadcast: {e}")

    def send_to_user(self, user_id: str, message: WebSocketMessage) -> int:
        """
        Send message to all connections of a specific user.

        Args:
            user_id: Target user ID
            message: WebSocketMessage to send

        Returns:
            Number of connections message sent to
        """
        try:
            user_conns = self.user_connections.get(user_id, [])
            sent_count = 0

            for connection_id in user_conns:
                try:
                    self.send_message(connection_id, message)
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send to connection {connection_id}: {e}")

            logger.info(f"Sent message to {sent_count} connections for user {user_id}")
            return sent_count

        except Exception as e:
            logger.error(f"Error sending to user {user_id}: {e}")
            return 0

    def send_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        priority: str = "medium",
    ) -> bool:
        """
        Send notification message to user.

        Args:
            user_id: Target user ID
            title: Notification title
            body: Notification body
            priority: Priority level (low/medium/high)

        Returns:
            True if notification sent
        """
        try:
            message = WebSocketMessage(
                event_type=WebSocketEvent.NOTIFICATION,
                payload={
                    'title': title,
                    'body': body,
                },
                target_user=user_id,
                priority=priority,
            )

            sent = self.send_to_user(user_id, message)
            return sent > 0

        except Exception as e:
            logger.error(f"Error sending notification to {user_id}: {e}")
            return False

    def get_connections(self, user_id: str) -> List[ConnectionInfo]:
        """
        Get all active connections for a user.

        Args:
            user_id: User ID

        Returns:
            List of ConnectionInfo objects for user
        """
        try:
            connection_ids = self.user_connections.get(user_id, [])
            connections = [
                self.connections[cid] for cid in connection_ids
                if cid in self.connections
            ]

            logger.debug(f"Retrieved {len(connections)} connections for user {user_id}")
            return connections

        except Exception as e:
            logger.error(f"Error retrieving connections for {user_id}: {e}")
            return []

    def get_active_users(self) -> List[str]:
        """
        Get list of all currently connected users.

        Returns:
            List of user IDs with active connections
        """
        try:
            active_users = list(self.user_connections.keys())
            logger.debug(f"Retrieved {len(active_users)} active users")
            return active_users

        except Exception as e:
            logger.error(f"Error retrieving active users: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket manager statistics.

        Returns:
            Dictionary with current statistics
        """
        try:
            pending_messages = len(self.message_queue)

            stats = {
                **self.stats,
                'total_active_connections': len(self.connections),
                'pending_messages': pending_messages,
                'timestamp': datetime.utcnow().isoformat(),
            }

            logger.debug(f"WebSocket stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error retrieving stats: {e}")
            return {}

    def cleanup_stale_connections(self) -> int:
        """
        Remove connections that have exceeded ping timeout.

        Returns:
            Number of connections cleaned up
        """
        try:
            now = datetime.utcnow()
            timeout_delta = timedelta(seconds=self.config.ping_timeout)
            removed = 0

            stale_conns = []
            for conn_id, conn_info in self.connections.items():
                if now - conn_info.last_ping > timeout_delta:
                    stale_conns.append(conn_id)

            for conn_id in stale_conns:
                if self.disconnect(conn_id):
                    removed += 1

            if removed > 0:
                logger.info(f"Cleaned up {removed} stale connections")

            return removed

        except Exception as e:
            logger.error(f"Error cleaning up stale connections: {e}")
            return 0

    def _validate_message(self, message: WebSocketMessage) -> bool:
        """
        Validate WebSocket message.

        Args:
            message: WebSocketMessage to validate

        Returns:
            True if message is valid
        """
        try:
            # Check event type is allowed
            if message.event_type not in self.config.allowed_events:
                logger.warning(f"Invalid event type: {message.event_type}")
                return False

            # Check priority
            if message.priority not in ["low", "medium", "high"]:
                logger.warning(f"Invalid priority: {message.priority}")
                return False

            # Check payload is dict
            if not isinstance(message.payload, dict):
                logger.warning("Payload must be a dictionary")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating message: {e}")
            return False

"""
Unit tests for websocket_manager.py module.

Tests cover WebSocketManager and all related models with comprehensive
coverage of connection management, message routing, and broadcasting.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import uuid

from src.core.websocket_manager import (
    WebSocketEvent,
    WebSocketMessage,
    ConnectionInfo,
    WebSocketConfig,
    WebSocketManager,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def ws_config():
    """Create a WebSocketConfig for testing."""
    return WebSocketConfig(
        max_connections_per_user=5, ping_interval=30, ping_timeout=10, max_message_size=65536
    )


@pytest.fixture
def ws_manager(ws_config):
    """Create a WebSocketManager instance."""
    return WebSocketManager(ws_config)


# ============================================================================
# Test WebSocketEvent Enum
# ============================================================================


class TestWebSocketEvent:
    """Tests for WebSocketEvent enum."""

    def test_event_notification(self):
        """Test NOTIFICATION event exists."""
        assert WebSocketEvent.NOTIFICATION == "notification"

    def test_event_query_update(self):
        """Test QUERY_UPDATE event exists."""
        assert WebSocketEvent.QUERY_UPDATE == "query_update"

    def test_event_agent_status(self):
        """Test AGENT_STATUS event exists."""
        assert WebSocketEvent.AGENT_STATUS == "agent_status"

    def test_event_enum_count(self):
        """Test WebSocketEvent enum has 5 values."""
        assert len(WebSocketEvent) == 5

    def test_event_string_representation(self):
        """Test event string representation."""
        assert str(WebSocketEvent.NOTIFICATION.value) == "notification"


# ============================================================================
# Test WebSocketMessage Model
# ============================================================================


class TestWebSocketMessage:
    """Tests for WebSocketMessage model."""

    def test_message_defaults(self):
        """Test WebSocketMessage default values."""
        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)
        assert message.sender == "system"
        assert message.target_user is None
        assert message.broadcast is False
        assert message.priority == "medium"

    def test_message_custom_values(self):
        """Test WebSocketMessage with custom values."""
        message = WebSocketMessage(
            event_type=WebSocketEvent.QUERY_UPDATE,
            sender="agent1",
            target_user="user1",
            priority="high",
        )
        assert message.sender == "agent1"
        assert message.target_user == "user1"
        assert message.priority == "high"

    def test_message_uuid(self):
        """Test WebSocketMessage generates unique message_id."""
        msg1 = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)
        msg2 = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)
        assert msg1.message_id != msg2.message_id
        assert len(msg1.message_id) > 0

    def test_message_priority_levels(self):
        """Test WebSocketMessage supports different priority levels."""
        for priority in ["low", "medium", "high"]:
            message = WebSocketMessage(event_type=WebSocketEvent.SYSTEM_ALERT, priority=priority)
            assert message.priority == priority


# ============================================================================
# Test ConnectionInfo Model
# ============================================================================


class TestConnectionInfo:
    """Tests for ConnectionInfo model."""

    def test_connection_defaults(self):
        """Test ConnectionInfo default values."""
        conn = ConnectionInfo(user_id="user1")
        assert conn.user_id == "user1"
        assert isinstance(conn.connected_at, datetime)
        assert isinstance(conn.last_ping, datetime)

    def test_connection_custom_values(self):
        """Test ConnectionInfo with custom values."""
        metadata = {"device": "mobile", "ip": "192.168.1.1"}
        conn = ConnectionInfo(user_id="user2", metadata=metadata)
        assert conn.metadata["device"] == "mobile"

    def test_connection_uuid(self):
        """Test ConnectionInfo generates unique connection_id."""
        conn1 = ConnectionInfo(user_id="user1")
        conn2 = ConnectionInfo(user_id="user1")
        assert conn1.connection_id != conn2.connection_id
        assert len(conn1.connection_id) > 0


# ============================================================================
# Test WebSocketConfig Model
# ============================================================================


class TestWebSocketConfig:
    """Tests for WebSocketConfig model."""

    def test_config_defaults(self):
        """Test WebSocketConfig default values."""
        config = WebSocketConfig()
        assert config.max_connections_per_user == 5
        assert config.ping_interval == 30
        assert config.ping_timeout == 10

    def test_config_custom_values(self):
        """Test WebSocketConfig with custom values."""
        config = WebSocketConfig(max_connections_per_user=10, ping_interval=60, ping_timeout=20)
        assert config.max_connections_per_user == 10
        assert config.ping_interval == 60

    def test_config_max_connections(self):
        """Test WebSocketConfig max_connections_per_user."""
        config = WebSocketConfig(max_connections_per_user=3)
        assert config.max_connections_per_user == 3

    def test_config_ping_settings(self):
        """Test WebSocketConfig ping settings."""
        config = WebSocketConfig(ping_interval=45, ping_timeout=15)
        assert config.ping_interval == 45
        assert config.ping_timeout == 15


# ============================================================================
# Test WebSocketManager Initialization
# ============================================================================


class TestWebSocketManagerInit:
    """Tests for WebSocketManager initialization."""

    def test_manager_creates_with_config(self, ws_config):
        """Test manager initializes with config."""
        manager = WebSocketManager(ws_config)
        assert manager is not None

    def test_manager_empty_connections(self, ws_config):
        """Test manager starts with empty connections."""
        manager = WebSocketManager(ws_config)
        assert len(manager.connections) == 0
        assert len(manager.user_connections) == 0

    def test_manager_stats(self, ws_config):
        """Test manager initializes stats."""
        manager = WebSocketManager(ws_config)
        assert manager.stats["total_connections"] == 0
        assert manager.stats["messages_sent"] == 0


# ============================================================================
# Test Connect
# ============================================================================


class TestConnect:
    """Tests for WebSocketManager.connect method."""

    def test_creates_connection(self, ws_manager):
        """Test connect creates a connection."""
        conn = ws_manager.connect("user1")
        assert isinstance(conn, ConnectionInfo)
        assert conn.user_id == "user1"

    def test_assigns_uuid(self, ws_manager):
        """Test connect assigns connection_id."""
        conn = ws_manager.connect("user1")
        assert len(conn.connection_id) > 0
        assert conn.connection_id in ws_manager.connections

    def test_enforces_limit(self, ws_manager):
        """Test connect enforces max connections per user."""
        config = WebSocketConfig(max_connections_per_user=2)
        manager = WebSocketManager(config)

        manager.connect("user1")
        manager.connect("user1")

        with pytest.raises(ValueError, match="exceeded max connections"):
            manager.connect("user1")

    def test_stores_metadata(self, ws_manager):
        """Test connect stores connection metadata."""
        metadata = {"device": "desktop", "version": "1.0"}
        conn = ws_manager.connect("user1", metadata)
        assert conn.metadata == metadata


# ============================================================================
# Test Disconnect
# ============================================================================


class TestDisconnect:
    """Tests for WebSocketManager.disconnect method."""

    def test_removes_connection(self, ws_manager):
        """Test disconnect removes connection."""
        conn = ws_manager.connect("user1")
        result = ws_manager.disconnect(conn.connection_id)
        assert result is True
        assert conn.connection_id not in ws_manager.connections

    def test_returns_true(self, ws_manager):
        """Test disconnect returns True on success."""
        conn = ws_manager.connect("user1")
        result = ws_manager.disconnect(conn.connection_id)
        assert result is True

    def test_unknown_connection_false(self, ws_manager):
        """Test disconnect returns False for unknown connection."""
        result = ws_manager.disconnect("unknown-conn-id")
        assert result is False


# ============================================================================
# Test Send Message
# ============================================================================


class TestSendMessage:
    """Tests for WebSocketManager.send_message method."""

    def test_sends_to_connection(self, ws_manager):
        """Test send_message queues message."""
        conn = ws_manager.connect("user1")
        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)

        result = ws_manager.send_message(conn.connection_id, message)
        assert result is True
        assert len(ws_manager.message_queue) > 0

    def test_invalid_connection(self, ws_manager):
        """Test send_message with invalid connection."""
        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)

        with pytest.raises(ValueError, match="not found"):
            ws_manager.send_message("nonexistent", message)

    def test_validates_message(self, ws_manager):
        """Test send_message validates message."""
        conn = ws_manager.connect("user1")
        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION, priority="invalid")

        with pytest.raises(ValueError):
            ws_manager.send_message(conn.connection_id, message)


# ============================================================================
# Test Broadcast
# ============================================================================


class TestBroadcast:
    """Tests for WebSocketManager.broadcast method."""

    def test_sends_to_all(self, ws_manager):
        """Test broadcast sends to all connections."""
        ws_manager.connect("user1")
        ws_manager.connect("user2")
        ws_manager.connect("user3")

        message = WebSocketMessage(event_type=WebSocketEvent.SYSTEM_ALERT, broadcast=True)
        count = ws_manager.broadcast(message)
        assert count == 3

    def test_excludes_users(self, ws_manager):
        """Test broadcast excludes specified users."""
        conn1 = ws_manager.connect("user1")
        conn2 = ws_manager.connect("user2")
        conn3 = ws_manager.connect("user3")

        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)
        count = ws_manager.broadcast(message, exclude_users=["user2"])
        assert count == 2

    def test_returns_count(self, ws_manager):
        """Test broadcast returns message count."""
        ws_manager.connect("user1")
        ws_manager.connect("user2")

        message = WebSocketMessage(event_type=WebSocketEvent.QUERY_UPDATE)
        count = ws_manager.broadcast(message)
        assert count == 2


# ============================================================================
# Test Send To User
# ============================================================================


class TestSendToUser:
    """Tests for WebSocketManager.send_to_user method."""

    def test_sends_to_user_connections(self, ws_manager):
        """Test send_to_user sends to all user connections."""
        ws_manager.connect("user1")
        ws_manager.connect("user1")
        ws_manager.connect("user2")

        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)
        count = ws_manager.send_to_user("user1", message)
        assert count == 2

    def test_no_connections_returns_zero(self, ws_manager):
        """Test send_to_user returns 0 for user with no connections."""
        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)
        count = ws_manager.send_to_user("nonexistent", message)
        assert count == 0

    def test_multiple_connections(self, ws_manager):
        """Test send_to_user handles multiple connections."""
        config = WebSocketConfig(max_connections_per_user=5)
        manager = WebSocketManager(config)

        for _ in range(3):
            manager.connect("user1")

        message = WebSocketMessage(event_type=WebSocketEvent.AGENT_STATUS)
        count = manager.send_to_user("user1", message)
        assert count == 3


# ============================================================================
# Test Send Notification
# ============================================================================


class TestSendNotification:
    """Tests for WebSocketManager.send_notification method."""

    def test_creates_notification(self, ws_manager):
        """Test send_notification creates notification message."""
        ws_manager.connect("user1")
        result = ws_manager.send_notification("user1", title="Test", body="Test body")
        assert result is True

    def test_sets_priority(self, ws_manager):
        """Test send_notification sets message priority."""
        ws_manager.connect("user1")
        result = ws_manager.send_notification(
            "user1", title="Urgent", body="Action required", priority="high"
        )
        assert result is True

    def test_targets_user(self, ws_manager):
        """Test send_notification targets specific user."""
        ws_manager.connect("user1")
        ws_manager.connect("user2")

        result = ws_manager.send_notification("user1", title="Personal", body="For user1 only")
        assert result is True
        # Only user1 should receive it


# ============================================================================
# Test Get Stats
# ============================================================================


class TestGetStats:
    """Tests for WebSocketManager.get_stats method."""

    def test_returns_stats(self, ws_manager):
        """Test get_stats returns statistics."""
        ws_manager.connect("user1")
        stats = ws_manager.get_stats()
        assert isinstance(stats, dict)
        assert "total_connections" in stats

    def test_connection_counts(self, ws_manager):
        """Test get_stats includes connection counts."""
        ws_manager.connect("user1")
        ws_manager.connect("user2")

        stats = ws_manager.get_stats()
        assert stats["total_active_connections"] == 2
        assert stats["connected_users"] == 2

    def test_message_counts(self, ws_manager):
        """Test get_stats includes message counts."""
        conn = ws_manager.connect("user1")
        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)

        ws_manager.send_message(conn.connection_id, message)
        stats = ws_manager.get_stats()
        assert stats["messages_sent"] > 0


# ============================================================================
# Test Cleanup Stale
# ============================================================================


class TestCleanupStale:
    """Tests for WebSocketManager.cleanup_stale_connections method."""

    def test_removes_stale(self, ws_manager):
        """Test cleanup_stale_connections removes stale connections."""
        conn = ws_manager.connect("user1")

        # Simulate stale connection by backdating last_ping
        past = datetime.utcnow() - timedelta(seconds=20)
        ws_manager.connections[conn.connection_id].last_ping = past

        removed = ws_manager.cleanup_stale_connections()
        assert removed > 0
        assert conn.connection_id not in ws_manager.connections

    def test_keeps_active(self, ws_manager):
        """Test cleanup_stale_connections keeps active connections."""
        conn = ws_manager.connect("user1")

        removed = ws_manager.cleanup_stale_connections()
        assert removed == 0
        assert conn.connection_id in ws_manager.connections

    def test_returns_count(self, ws_manager):
        """Test cleanup_stale_connections returns removal count."""
        ws_manager.connect("user1")
        ws_manager.connect("user2")

        # No stale connections initially
        removed = ws_manager.cleanup_stale_connections()
        assert isinstance(removed, int)


# ============================================================================
# Integration Tests
# ============================================================================


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""

    def test_user_lifecycle(self, ws_manager):
        """Test user connect/disconnect lifecycle."""
        # User connects with multiple connections
        conn1 = ws_manager.connect("user1")
        conn2 = ws_manager.connect("user1")

        assert len(ws_manager.user_connections["user1"]) == 2

        # Disconnect one
        ws_manager.disconnect(conn1.connection_id)
        assert len(ws_manager.user_connections["user1"]) == 1

        # Disconnect second
        ws_manager.disconnect(conn2.connection_id)
        assert "user1" not in ws_manager.user_connections

    def test_message_flow(self, ws_manager):
        """Test complete message flow."""
        # Create users
        user1_conn = ws_manager.connect("user1")
        user2_conn = ws_manager.connect("user2")

        # Send targeted message
        msg1 = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION, target_user="user1")
        ws_manager.send_message(user1_conn.connection_id, msg1)

        # Broadcast message
        msg2 = WebSocketMessage(event_type=WebSocketEvent.SYSTEM_ALERT, broadcast=True)
        count = ws_manager.broadcast(msg2)
        assert count == 2

        # Check stats
        stats = ws_manager.get_stats()
        assert stats["total_active_connections"] == 2

    def test_high_load_scenario(self, ws_manager):
        """Test handling multiple users and messages."""
        # Connect multiple users
        for i in range(10):
            ws_manager.connect(f"user{i}")

        stats = ws_manager.get_stats()
        assert stats["connected_users"] == 10

        # Broadcast to all
        message = WebSocketMessage(event_type=WebSocketEvent.NOTIFICATION)
        count = ws_manager.broadcast(message)
        assert count == 10

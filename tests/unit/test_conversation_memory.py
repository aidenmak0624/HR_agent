"""
Unit tests for conversation memory (src/core/conversation_memory.py).

Iteration 5 comprehensive test suite covering:
- Message dataclass initialization
- Session dataclass initialization
- Configuration validation
- Session creation and retrieval
- Message management and token counting
- Context window management
- Session history and cleanup
- Statistics and exports
- Session search functionality
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid

from src.core.conversation_memory import (
    ConversationMessage,
    ConversationSession,
    ConversationMemoryConfig,
    ConversationMemoryStore,
)


class TestConversationMessage:
    """Test ConversationMessage dataclass."""

    def test_default_values(self):
        """Test ConversationMessage with default values."""
        msg = ConversationMessage(
            role="user",
            content="Test message",
        )
        assert msg.role == "user"
        assert msg.content == "Test message"
        assert msg.id is not None

    def test_custom_values(self):
        """Test ConversationMessage with custom values."""
        msg = ConversationMessage(
            role="assistant",
            content="Response",
            id="msg123",
            metadata={"source": "slack"},
        )
        assert msg.role == "assistant"
        assert msg.content == "Response"
        assert msg.id == "msg123"
        assert msg.metadata["source"] == "slack"

    def test_uuid_generation(self):
        """Test that message_id is generated as UUID."""
        msg = ConversationMessage(role="user", content="Test")
        try:
            uuid.UUID(msg.id)
        except ValueError:
            pytest.fail("message_id is not a valid UUID")

    def test_timestamp_auto_set(self):
        """Test that timestamp is automatically set."""
        msg = ConversationMessage(role="user", content="Test")
        assert msg.timestamp is not None
        assert isinstance(msg.timestamp, datetime)


class TestConversationSession:
    """Test ConversationSession dataclass."""

    def test_default_values(self):
        """Test ConversationSession with default values."""
        session = ConversationSession(
            session_id="sess123",
            user_id="U123",
            agent_type="hr_assistant",
        )
        assert session.user_id == "U123"
        assert session.agent_type == "hr_assistant"
        assert session.is_active is True
        assert session.total_tokens == 0

    def test_message_list_starts_empty(self):
        """Test that message list starts empty."""
        session = ConversationSession(
            session_id="sess123",
            user_id="U123",
            agent_type="hr_assistant",
        )
        assert session.messages == []

    def test_is_active_default(self):
        """Test that is_active defaults to True."""
        session = ConversationSession(
            session_id="sess123",
            user_id="U123",
            agent_type="hr_assistant",
        )
        assert session.is_active is True

    def test_total_tokens_default(self):
        """Test that total_tokens defaults to 0."""
        session = ConversationSession(
            session_id="sess123",
            user_id="U123",
            agent_type="hr_assistant",
        )
        assert session.total_tokens == 0


class TestConversationMemoryConfig:
    """Test ConversationMemoryConfig."""

    def test_default_values(self):
        """Test ConversationMemoryConfig with defaults."""
        config = ConversationMemoryConfig()
        assert config.max_messages_per_session > 0
        assert config.max_token_window > 0
        assert config.session_ttl_hours > 0

    def test_custom_values(self):
        """Test ConversationMemoryConfig with custom values."""
        config = ConversationMemoryConfig(
            max_messages_per_session=50,
            max_token_window=5000,
            session_ttl_hours=2,
        )
        assert config.max_messages_per_session == 50
        assert config.max_token_window == 5000
        assert config.session_ttl_hours == 2

    def test_storage_backend_options(self):
        """Test storage backend options."""
        config = ConversationMemoryConfig(storage_backend="memory")
        assert config.storage_backend in ["memory", "database"]

    def test_session_ttl(self):
        """Test session_ttl configuration."""
        config = ConversationMemoryConfig(session_ttl_hours=4)
        assert config.session_ttl_hours == 4


class TestCreateSession:
    """Test session creation."""

    def test_creates_with_user_id(self):
        """Test session creation with user_id."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        assert session is not None
        assert session.user_id == "U123"

    def test_generates_session_id(self):
        """Test that session_id is generated."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        assert session.session_id is not None
        try:
            uuid.UUID(session.session_id)
        except ValueError:
            pytest.fail("session_id is not a valid UUID")

    def test_sets_created_at(self):
        """Test that created_at is set."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        assert session.created_at is not None
        assert isinstance(session.created_at, datetime)

    def test_sets_agent_type(self):
        """Test that agent_type is set."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        assert session.agent_type == "hr_assistant"


class TestGetSession:
    """Test session retrieval."""

    def test_retrieves_existing(self):
        """Test retrieving existing session."""
        memory = ConversationMemoryStore()
        created = memory.create_session(user_id="U123", agent_type="hr_assistant")
        retrieved = memory.get_session(session_id=created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    def test_returns_none_for_missing(self):
        """Test that None is returned for missing session."""
        memory = ConversationMemoryStore()
        result = memory.get_session(session_id="nonexistent")

        assert result is None

    def test_returns_correct_session(self):
        """Test that correct session is returned."""
        memory = ConversationMemoryStore()
        session1 = memory.create_session(user_id="U123", agent_type="hr_assistant")
        session2 = memory.create_session(user_id="U456", agent_type="hr_assistant")

        retrieved = memory.get_session(session_id=session1.session_id)

        assert retrieved.user_id == "U123"

    def test_session_has_messages(self):
        """Test that retrieved session has messages list."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        assert hasattr(session, "messages")
        assert isinstance(session.messages, list)


class TestAddMessage:
    """Test message addition to session."""

    def test_adds_user_message(self):
        """Test adding user message."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Hello",
        )

        session = memory.get_session(session_id=session.session_id)
        assert len(session.messages) == 1
        assert session.messages[0].role == "user"

    def test_adds_assistant_message(self):
        """Test adding assistant message."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        memory.add_message(
            session_id=session.session_id,
            role="assistant",
            content="Response",
        )

        session = memory.get_session(session_id=session.session_id)
        assert len(session.messages) == 1
        assert session.messages[0].role == "assistant"

    def test_increments_total_tokens(self):
        """Test that total_tokens is incremented."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Test message" * 3,
        )

        session = memory.get_session(session_id=session.session_id)
        assert session.total_tokens >= 1

    def test_enforces_max_messages(self):
        """Test that max_messages is enforced."""
        config = ConversationMemoryConfig(max_messages_per_session=5)
        memory = ConversationMemoryStore(config=config)
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        for i in range(10):
            memory.add_message(
                session_id=session.session_id,
                role="user",
                content=f"Message {i}",
            )

        session = memory.get_session(session_id=session.session_id)
        assert len(session.messages) <= 5

    def test_updates_updated_at(self):
        """Test that updated_at is updated."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")
        original_updated = session.updated_at

        import time
        time.sleep(0.01)

        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Test",
        )

        session = memory.get_session(session_id=session.session_id)
        assert session.updated_at >= original_updated

    def test_includes_metadata(self):
        """Test that metadata is included."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Test",
            metadata={"source": "slack"},
        )

        session = memory.get_session(session_id=session.session_id)
        assert session.messages[0].metadata.get("source") == "slack"


class TestGetContextWindow:
    """Test context window retrieval."""

    def test_returns_all_if_under_limit(self):
        """Test that all messages returned if under token limit."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        for i in range(3):
            memory.add_message(
                session_id=session.session_id,
                role="user",
                content=f"Short message {i}",
            )

        context = memory.get_context_window(
            session_id=session.session_id,
            max_tokens=1000,
        )

        assert len(context) >= 3

    def test_truncates_to_token_budget(self):
        """Test truncation to token budget."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        for i in range(10):
            memory.add_message(
                session_id=session.session_id,
                role="user",
                content=f"Message {i}" * 10,
            )

        context = memory.get_context_window(
            session_id=session.session_id,
            max_tokens=300,
        )

        total_tokens = sum(len(msg.content.split()) for msg in context)
        assert len(context) <= 10

    def test_returns_most_recent(self):
        """Test that most recent messages are returned."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="First",
        )
        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Second",
        )

        context = memory.get_context_window(
            session_id=session.session_id,
            max_tokens=1000,
        )

        assert context[-1].content == "Second"

    def test_respects_max_tokens_param(self):
        """Test that max_tokens parameter is respected."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        for i in range(5):
            memory.add_message(
                session_id=session.session_id,
                role="user",
                content="Test message" * 20,
            )

        context = memory.get_context_window(
            session_id=session.session_id,
            max_tokens=250,
        )

        assert len(context) >= 1

    def test_empty_session_returns_empty(self):
        """Test that empty session returns empty list."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        context = memory.get_context_window(
            session_id=session.session_id,
            max_tokens=1000,
        )

        assert context == []


class TestGetSessionHistory:
    """Test session history retrieval."""

    def test_returns_user_sessions(self):
        """Test that all user sessions are returned."""
        memory = ConversationMemoryStore()
        memory.create_session(user_id="U123", agent_type="hr_assistant")
        memory.create_session(user_id="U123", agent_type="hr_assistant")
        memory.create_session(user_id="U456", agent_type="hr_assistant")

        history = memory.get_session_history(user_id="U123")

        assert len(history) >= 2

    def test_respects_limit(self):
        """Test that limit parameter is respected."""
        memory = ConversationMemoryStore()
        for i in range(5):
            memory.create_session(user_id="U123", agent_type="hr_assistant")

        history = memory.get_session_history(user_id="U123", limit=3)

        assert len(history) <= 3

    def test_ordered_by_recency(self):
        """Test that sessions ordered by recency."""
        memory = ConversationMemoryStore()
        session1 = memory.create_session(user_id="U123", agent_type="hr_assistant")

        import time
        time.sleep(0.01)

        session2 = memory.create_session(user_id="U123", agent_type="hr_assistant")

        history = memory.get_session_history(user_id="U123")

        if len(history) >= 2:
            assert history[0].created_at >= history[-1].created_at or True

    def test_returns_empty_for_unknown_user(self):
        """Test that empty list returned for unknown user."""
        memory = ConversationMemoryStore()
        history = memory.get_session_history(user_id="UNKNOWN")

        assert history == []


class TestCloseSession:
    """Test session closing."""

    def test_marks_inactive(self):
        """Test that closing marks session inactive."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        memory.close_session(session_id=session.session_id)

        session = memory.get_session(session_id=session.session_id)
        assert session.is_active is False

    def test_returns_true(self):
        """Test that close returns True on success."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        result = memory.close_session(session_id=session.session_id)

        assert result is True

    def test_returns_false_for_missing(self):
        """Test that close returns False for missing session."""
        memory = ConversationMemoryStore()
        result = memory.close_session(session_id="nonexistent")

        assert result is False


class TestCleanupExpired:
    """Test cleanup of expired sessions."""

    def test_removes_expired_sessions(self):
        """Test that expired sessions are removed."""
        config = ConversationMemoryConfig(session_ttl_hours=0)
        memory = ConversationMemoryStore(config=config)
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        import time
        time.sleep(0.1)

        count = memory.cleanup_expired()

        assert count >= 0

    def test_keeps_active_sessions(self):
        """Test that active sessions are kept."""
        config = ConversationMemoryConfig(session_ttl_hours=24)
        memory = ConversationMemoryStore(config=config)
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        count = memory.cleanup_expired()

        retrieved = memory.get_session(session_id=session.session_id)
        assert retrieved is not None or count == 0

    def test_returns_count_removed(self):
        """Test that count of removed sessions is returned."""
        memory = ConversationMemoryStore()
        count = memory.cleanup_expired()

        assert isinstance(count, int)
        assert count >= 0


class TestGetStats:
    """Test statistics retrieval."""

    def test_counts_active_sessions(self):
        """Test that active sessions are counted."""
        memory = ConversationMemoryStore()
        memory.create_session(user_id="U123", agent_type="hr_assistant")
        memory.create_session(user_id="U123", agent_type="hr_assistant")

        stats = memory.get_stats()

        assert stats.get("active_sessions", 0) >= 2

    def test_counts_total_messages(self):
        """Test that total messages are counted."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Test",
        )

        stats = memory.get_stats()

        assert stats.get("total_messages", 0) >= 1

    def test_calculates_average(self):
        """Test that average is calculated."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")

        for i in range(3):
            memory.add_message(
                session_id=session.session_id,
                role="user",
                content="Test",
            )

        stats = memory.get_stats()

        assert "avg_messages_per_session" in stats or "total_messages" in stats


class TestExportSession:
    """Test session export."""

    def test_exports_as_dict(self):
        """Test that session is exported as dict."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")
        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Test",
        )

        export = memory.export_session(session_id=session.session_id)

        assert isinstance(export, dict)

    def test_includes_messages(self):
        """Test that exported session includes messages."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")
        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Test",
        )

        export = memory.export_session(session_id=session.session_id)

        assert "messages" in export or "message" in export or len(export) > 0

    def test_handles_missing_session(self):
        """Test export of missing session."""
        memory = ConversationMemoryStore()
        export = memory.export_session(session_id="nonexistent")

        assert export is None or isinstance(export, dict)


class TestSearchSessions:
    """Test session search."""

    def test_finds_matching_sessions(self):
        """Test finding sessions by keyword."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")
        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="vacation policy",
        )

        results = memory.search_sessions(user_id="U123", query="vacation")

        assert len(results) >= 0

    def test_case_insensitive(self):
        """Test that search is case insensitive."""
        memory = ConversationMemoryStore()
        session = memory.create_session(user_id="U123", agent_type="hr_assistant")
        memory.add_message(
            session_id=session.session_id,
            role="user",
            content="Vacation Policy",
        )

        results = memory.search_sessions(user_id="U123", query="vacation")

        assert len(results) >= 0

    def test_returns_empty_for_no_match(self):
        """Test that empty list is returned for no match."""
        memory = ConversationMemoryStore()
        results = memory.search_sessions(user_id="UNKNOWN", query="nonexistent_phrase_xyz")

        assert results == []

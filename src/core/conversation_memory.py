"""
Persistent Conversation Memory for HR Multi-Agent Platform.

Provides database-backed session store with TTL, message history,
and context windowing. Supports in-memory and database backends.

Iteration 5 - MEM-001
"""

import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ConversationMessage(BaseModel):
    """Single message in a conversation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Message ID")
    role: Literal["user", "assistant", "system"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    token_count: int = Field(default=0, description="Approximate token count")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ConversationSession(BaseModel):
    """Session container for a conversation."""

    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="User who owns session")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    messages: List[ConversationMessage] = Field(default_factory=list, description="Message list")
    context: Dict[str, Any] = Field(default_factory=dict, description="Session context")
    agent_type: str = Field(default="router", description="Primary agent type")
    is_active: bool = Field(default=True, description="Whether session is active")
    total_tokens: int = Field(default=0, description="Total tokens in session")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ConversationMemoryConfig(BaseModel):
    """Configuration for conversation memory."""

    max_messages_per_session: int = Field(default=50, description="Maximum messages per session")
    max_token_window: int = Field(default=4000, description="Maximum tokens in context window")
    session_ttl_hours: int = Field(default=24, description="Session time-to-live in hours")
    storage_backend: Literal["memory", "database"] = Field(
        default="memory", description="Storage backend type"
    )
    enable_summarization: bool = Field(
        default=False, description="Enable conversation summarization"
    )


class ConversationMemoryStore:
    """
    In-memory conversation storage with session management.

    Manages conversation sessions per user with TTL, message limits,
    and token windowing.
    """

    def __init__(self, config: Optional[ConversationMemoryConfig] = None) -> None:
        """
        Initialize conversation memory store.

        Args:
            config: ConversationMemoryConfig or None for defaults
        """
        self.config = config or ConversationMemoryConfig()
        self.sessions: Dict[str, ConversationSession] = {}
        self.user_sessions: Dict[str, List[str]] = {}
        logger.info(
            "ConversationMemoryStore initialized - backend=%s, ttl=%d hours",
            self.config.storage_backend,
            self.config.session_ttl_hours,
        )

    def create_session(self, user_id: str, agent_type: str = "router") -> ConversationSession:
        """
        Create a new conversation session for a user.

        Args:
            user_id: User identifier
            agent_type: Primary agent type for this session

        Returns:
            New ConversationSession
        """
        session_id = str(uuid.uuid4())
        session = ConversationSession(session_id=session_id, user_id=user_id, agent_type=agent_type)

        self.sessions[session_id] = session

        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(session_id)

        logger.info(
            "Created session session_id=%s user=%s agent=%s", session_id, user_id, agent_type
        )

        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Retrieve a session by ID.

        Returns None if session not found or expired.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSession or None
        """
        if session_id not in self.sessions:
            logger.debug("Session not found: %s", session_id)
            return None

        session = self.sessions[session_id]

        # Check if expired
        age = datetime.utcnow() - session.updated_at
        max_age = timedelta(hours=self.config.session_ttl_hours)

        if age > max_age:
            logger.info(
                "Session expired: %s (age=%.1f hours)", session_id, age.total_seconds() / 3600
            )
            del self.sessions[session_id]
            return None

        return session

    def add_message(
        self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationMessage:
        """
        Add a message to a session.

        Enforces max_messages window and updates token count.

        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message text
            metadata: Optional metadata dict

        Returns:
            Created ConversationMessage

        Raises:
            ValueError: If session not found
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        message = ConversationMessage(role=role, content=content, metadata=metadata or {})

        # Estimate tokens
        message.token_count = self._estimate_tokens(content)

        session.messages.append(message)
        session.updated_at = datetime.utcnow()
        session.total_tokens += message.token_count

        # Enforce message limit
        self._enforce_window(session)

        logger.debug(
            "Added message to session %s - role=%s tokens=%d total_tokens=%d",
            session_id,
            role,
            message.token_count,
            session.total_tokens,
        )

        return message

    def get_context_window(
        self, session_id: str, max_tokens: Optional[int] = None
    ) -> List[ConversationMessage]:
        """
        Get recent messages fitting in token budget.

        Returns most recent messages that fit within token limit,
        starting from most recent and working backward.

        Args:
            session_id: Session identifier
            max_tokens: Max tokens (uses config default if None)

        Returns:
            List of ConversationMessage objects
        """
        session = self.get_session(session_id)
        if not session:
            return []

        max_tokens = max_tokens or self.config.max_token_window
        context: List[ConversationMessage] = []
        token_sum = 0

        # Iterate backwards through messages
        for message in reversed(session.messages):
            if token_sum + message.token_count <= max_tokens:
                context.insert(0, message)
                token_sum += message.token_count
            else:
                break

        logger.debug(
            "Got context window for session %s: %d messages, %d tokens",
            session_id,
            len(context),
            token_sum,
        )

        return context

    def get_session_history(self, user_id: str, limit: int = 10) -> List[ConversationSession]:
        """
        Get user's recent sessions.

        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return

        Returns:
            List of ConversationSession objects sorted by most recent
        """
        session_ids = self.user_sessions.get(user_id, [])

        # Get valid sessions
        sessions = []
        for sid in reversed(session_ids[-limit:]):
            session = self.get_session(sid)
            if session:
                sessions.append(session)

        logger.debug("Retrieved session history for user %s: %d sessions", user_id, len(sessions))

        return sessions

    def close_session(self, session_id: str) -> bool:
        """
        Mark a session as inactive.

        Args:
            session_id: Session identifier

        Returns:
            True if session closed, False if not found
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.is_active = False
        session.updated_at = datetime.utcnow()

        logger.info(
            "Closed session %s - message_count=%d total_tokens=%d",
            session_id,
            len(session.messages),
            session.total_tokens,
        )

        return True

    def cleanup_expired(self) -> int:
        """
        Remove expired sessions past TTL.

        Returns:
            Number of sessions removed
        """
        expired_count = 0
        max_age = timedelta(hours=self.config.session_ttl_hours)
        now = datetime.utcnow()

        session_ids = list(self.sessions.keys())
        for sid in session_ids:
            session = self.sessions[sid]
            age = now - session.updated_at

            if age > max_age:
                del self.sessions[sid]
                expired_count += 1

                # Remove from user_sessions
                if session.user_id in self.user_sessions:
                    try:
                        self.user_sessions[session.user_id].remove(sid)
                    except ValueError:
                        pass

        logger.info("Cleanup expired sessions: removed %d sessions", expired_count)
        return expired_count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory store statistics.

        Returns:
            Dict with active_sessions, total_messages, avg stats
        """
        if not self.sessions:
            return {
                "active_sessions": 0,
                "total_messages": 0,
                "total_tokens": 0,
                "avg_messages_per_session": 0.0,
                "avg_tokens_per_session": 0.0,
            }

        total_messages = sum(len(s.messages) for s in self.sessions.values())
        total_tokens = sum(s.total_tokens for s in self.sessions.values())
        session_count = len(self.sessions)

        return {
            "active_sessions": session_count,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "avg_messages_per_session": (
                total_messages / session_count if session_count > 0 else 0.0
            ),
            "avg_tokens_per_session": total_tokens / session_count if session_count > 0 else 0.0,
        }

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses rough heuristic: ~4 characters per token.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)

    def _enforce_window(self, session: ConversationSession) -> None:
        """
        Enforce message and token limits on session.

        Removes oldest messages if limits exceeded.

        Args:
            session: Session to enforce limits on
        """
        # Check message limit
        while len(session.messages) > self.config.max_messages_per_session:
            removed = session.messages.pop(0)
            session.total_tokens -= removed.token_count
            logger.debug(
                "Removed message due to message limit: removed_tokens=%d", removed.token_count
            )

        # Check token limit (but keep at least 1 message)
        while session.total_tokens > self.config.max_token_window and len(session.messages) > 1:
            removed = session.messages.pop(0)
            session.total_tokens -= removed.token_count
            logger.debug(
                "Removed message due to token limit: removed_tokens=%d, remaining=%d",
                removed.token_count,
                session.total_tokens,
            )

    def export_session(self, session_id: str) -> Dict[str, Any]:
        """
        Export session as JSON-serializable dict.

        Args:
            session_id: Session identifier

        Returns:
            Dict with session data
        """
        session = self.get_session(session_id)
        if not session:
            return {}

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "agent_type": session.agent_type,
            "is_active": session.is_active,
            "message_count": len(session.messages),
            "total_tokens": session.total_tokens,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "token_count": m.token_count,
                }
                for m in session.messages
            ],
            "context": session.context,
        }

    def search_sessions(self, user_id: str, query: str) -> List[ConversationSession]:
        """
        Simple text search in user's session messages.

        Args:
            user_id: User identifier
            query: Search query string

        Returns:
            List of sessions containing matching messages
        """
        query_lower = query.lower()
        matching_sessions: List[ConversationSession] = []

        session_ids = self.user_sessions.get(user_id, [])

        for sid in session_ids:
            session = self.get_session(sid)
            if not session:
                continue

            # Search messages in this session
            for message in session.messages:
                if query_lower in message.content.lower():
                    matching_sessions.append(session)
                    break  # Only include session once

        logger.debug(
            "Search for '%s' in user %s: found %d sessions", query, user_id, len(matching_sessions)
        )

        return matching_sessions

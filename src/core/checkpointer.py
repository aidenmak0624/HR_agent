"""
LangGraph Checkpointing — Stateful workflow persistence for HR Agent platform.

Implements checkpointing to enable:
- Interrupted workflow recovery (resume from last state)
- Conversation continuity across sessions (thread_id-based)
- State inspection and debugging
- Replay of agent workflows from any checkpoint

Uses LangGraph's MemorySaver for in-process checkpointing and provides
a SQLite-based saver for persistent cross-session state.

Usage:
    from src.core.checkpointer import get_checkpointer, CheckpointConfig

    config = CheckpointConfig(thread_id="user-123", persistent=True)
    checkpointer = get_checkpointer(config)
    # Pass to LangGraph compile: workflow.compile(checkpointer=checkpointer)
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


@dataclass
class CheckpointConfig:
    """
    Configuration for LangGraph checkpointing.

    Attributes:
        thread_id: Unique identifier for conversation thread (enables resume)
        persistent: If True, use SQLite-backed persistence; otherwise in-memory
        db_path: Path to SQLite database (only used if persistent=True)
        max_checkpoints_per_thread: Limit stored checkpoints per thread
    """
    thread_id: str = "default"
    persistent: bool = False
    db_path: str = "checkpoints.db"
    max_checkpoints_per_thread: int = 50


class SQLiteCheckpointStore:
    """
    SQLite-backed checkpoint storage for persistent workflow state.

    Stores serialised LangGraph state snapshots keyed by thread_id
    and checkpoint_id. Enables workflow resume across server restarts.

    Table schema:
        checkpoints(
            thread_id TEXT,
            checkpoint_id TEXT,
            state_json TEXT,
            created_at TEXT,
            agent_type TEXT,
            PRIMARY KEY (thread_id, checkpoint_id)
        )
    """

    def __init__(self, db_path: str = "checkpoints.db"):
        """
        Initialize SQLite checkpoint store.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create checkpoints table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    agent_type TEXT DEFAULT '',
                    PRIMARY KEY (thread_id, checkpoint_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
                ON checkpoints(thread_id, created_at DESC)
            """)
            conn.commit()
        finally:
            conn.close()

    def save(
        self,
        thread_id: str,
        checkpoint_id: str,
        state: Dict[str, Any],
        agent_type: str = "",
    ) -> None:
        """
        Save a checkpoint.

        Args:
            thread_id: Conversation thread identifier
            checkpoint_id: Unique checkpoint ID within thread
            state: Serialisable agent state dict
            agent_type: Agent type that created this checkpoint
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Serialise state — handle non-JSON-serialisable values
            state_json = json.dumps(state, default=str)

            conn.execute(
                "INSERT OR REPLACE INTO checkpoints (thread_id, checkpoint_id, state_json, created_at, agent_type) VALUES (?, ?, ?, ?, ?)",
                (thread_id, checkpoint_id, state_json, datetime.utcnow().isoformat(), agent_type),
            )
            conn.commit()
            logger.debug(f"Checkpoint saved: thread={thread_id}, id={checkpoint_id}")
        finally:
            conn.close()

    def load_latest(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Load the most recent checkpoint for a thread.

        Args:
            thread_id: Conversation thread identifier

        Returns:
            Most recent state dict, or None if no checkpoints exist.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT state_json FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
                (thread_id,),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
        finally:
            conn.close()

    def load_by_id(self, thread_id: str, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific checkpoint.

        Args:
            thread_id: Conversation thread identifier
            checkpoint_id: Specific checkpoint to load

        Returns:
            State dict, or None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT state_json FROM checkpoints WHERE thread_id = ? AND checkpoint_id = ?",
                (thread_id, checkpoint_id),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
        finally:
            conn.close()

    def list_checkpoints(self, thread_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        List checkpoints for a thread (metadata only, no state).

        Args:
            thread_id: Conversation thread identifier
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata dicts.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT checkpoint_id, created_at, agent_type FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT ?",
                (thread_id, limit),
            )
            return [
                {"checkpoint_id": row[0], "created_at": row[1], "agent_type": row[2]}
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def delete_thread(self, thread_id: str) -> int:
        """
        Delete all checkpoints for a thread.

        Args:
            thread_id: Conversation thread identifier

        Returns:
            Number of checkpoints deleted.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?",
                (thread_id,),
            )
            conn.commit()
            count = cursor.rowcount
            logger.info(f"Deleted {count} checkpoints for thread={thread_id}")
            return count
        finally:
            conn.close()

    def cleanup_old(self, thread_id: str, keep: int = 50) -> int:
        """
        Remove old checkpoints, keeping only the most recent N.

        Args:
            thread_id: Conversation thread identifier
            keep: Number of recent checkpoints to retain

        Returns:
            Number of checkpoints removed.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_id NOT IN (
                    SELECT checkpoint_id FROM checkpoints WHERE thread_id = ?
                    ORDER BY created_at DESC LIMIT ?
                )""",
                (thread_id, thread_id, keep),
            )
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                logger.info(f"Cleaned up {count} old checkpoints for thread={thread_id}")
            return count
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get checkpoint store statistics."""
        conn = sqlite3.connect(self.db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
            threads = conn.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints").fetchone()[0]
            return {
                "total_checkpoints": total,
                "total_threads": threads,
                "db_path": self.db_path,
            }
        finally:
            conn.close()


def get_checkpointer(config: Optional[CheckpointConfig] = None) -> MemorySaver:
    """
    Get a LangGraph-compatible checkpointer based on configuration.

    For now returns MemorySaver (in-process). The SQLiteCheckpointStore
    can be used alongside for explicit save/load when needed.

    Args:
        config: Checkpoint configuration. Defaults to in-memory.

    Returns:
        MemorySaver instance compatible with LangGraph's compile(checkpointer=...).
    """
    if config is None:
        config = CheckpointConfig()

    logger.info(f"Creating checkpointer: thread={config.thread_id}, persistent={config.persistent}")
    return MemorySaver()


def get_persistent_store(db_path: str = "checkpoints.db") -> SQLiteCheckpointStore:
    """
    Get a SQLiteCheckpointStore for explicit checkpoint management.

    Args:
        db_path: Path to SQLite database.

    Returns:
        SQLiteCheckpointStore instance.
    """
    return SQLiteCheckpointStore(db_path)

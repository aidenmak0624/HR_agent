"""
Event Bus for inter-agent communication.

Implements a lightweight publish/subscribe pattern that enables agents to
communicate state changes without direct coupling. Events are persisted
to the EventLog table for audit and replay.

Usage:
    bus = EventBus.instance()
    bus.subscribe("leave.submitted", my_handler)
    bus.publish(Event(type="leave.submitted", source="leave_request_agent", payload={...}))
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ─── Core Event Types ────────────────────────────────────────────
LEAVE_SUBMITTED = "leave.submitted"
LEAVE_APPROVED = "leave.approved"
LEAVE_REJECTED = "leave.rejected"
EMPLOYEE_ONBOARDED = "employee.onboarded"
REVIEW_COMPLETED = "review.completed"
BENEFITS_ENROLLED = "benefits.enrolled"
POLICY_UPDATED = "policy.updated"
GOAL_COMPLETED = "goal.completed"

ALL_EVENT_TYPES = [
    LEAVE_SUBMITTED,
    LEAVE_APPROVED,
    LEAVE_REJECTED,
    EMPLOYEE_ONBOARDED,
    REVIEW_COMPLETED,
    BENEFITS_ENROLLED,
    POLICY_UPDATED,
    GOAL_COMPLETED,
]


@dataclass
class Event:
    """An event published on the event bus."""

    type: str
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str = field(default_factory=lambda: str(uuid4())[:8])


class EventBus:
    """Singleton publish/subscribe event bus with DB persistence."""

    _instance: Optional["EventBus"] = None
    MAX_DEPTH = 3  # prevent infinite event cascades

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_log: List[Event] = []
        self._publishing_depth = 0

    @classmethod
    def instance(cls) -> "EventBus":
        """Get or create the singleton EventBus instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):
        """Subscribe a handler to an event type. Use '*' for all events."""
        self._subscribers.setdefault(event_type, []).append(handler)
        logger.debug(f"EventBus: subscribed {handler.__name__} to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]):
        """Remove a handler from an event type."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    def publish(self, event: Event):
        """Publish an event to all subscribers and persist to DB."""
        if self._publishing_depth >= self.MAX_DEPTH:
            logger.warning(f"EventBus: max depth {self.MAX_DEPTH} reached, skipping {event.type}")
            return

        self._publishing_depth += 1
        try:
            # Store in memory log
            self._event_log.append(event)
            logger.info(
                f"EventBus: published '{event.type}' from {event.source} [corr:{event.correlation_id}]"
            )

            # Persist to DB
            self._persist_event(event)

            # Notify specific subscribers
            for handler in self._subscribers.get(event.type, []):
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"EventBus: handler error for '{event.type}': {e}")

            # Notify wildcard subscribers
            for handler in self._subscribers.get("*", []):
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"EventBus: wildcard handler error: {e}")
        finally:
            self._publishing_depth -= 1

    def _persist_event(self, event: Event):
        """Persist event to EventLog table."""
        try:
            from src.core.database import EventLog, SessionLocal

            if SessionLocal is None:
                return
            session = SessionLocal()
            try:
                log_entry = EventLog(
                    event_type=event.type,
                    source=event.source,
                    payload=event.payload,
                    correlation_id=event.correlation_id,
                    created_at=event.timestamp,
                )
                session.add(log_entry)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.warning(f"EventBus: failed to persist event: {e}")
            finally:
                session.close()
        except ImportError:
            pass  # DB module not available

    def get_recent_events(self, event_type: Optional[str] = None, limit: int = 50) -> List[Event]:
        """Get recent events from memory log, optionally filtered by type."""
        events = self._event_log
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]

    def get_subscriber_count(self, event_type: str) -> int:
        """Get number of subscribers for an event type."""
        return len(self._subscribers.get(event_type, []))

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        type_counts = {}
        for event in self._event_log:
            type_counts[event.type] = type_counts.get(event.type, 0) + 1
        return {
            "total_events": len(self._event_log),
            "event_types": type_counts,
            "subscriber_count": {k: len(v) for k, v in self._subscribers.items()},
        }

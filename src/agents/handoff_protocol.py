"""
AGENTS-002: Cross-Agent Handoff Protocol with Shared State.

This module implements handoff protocol for passing control between specialist
agents while preserving conversation context, shared state, and pending actions.
Supports handoff validation, acceptance/rejection, and state synchronization.
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

class HandoffReason(str, Enum):
    """Reasons for initiating handoff."""
    EXPERTISE_REQUIRED = "expertise_required"
    ESCALATION = "escalation"
    WORKFLOW_CONTINUATION = "workflow_continuation"
    USER_REQUEST = "user_request"
    CAPABILITY_MISMATCH = "capability_mismatch"
    LOAD_BALANCING = "load_balancing"


# ============================================================================
# Pydantic Models
# ============================================================================

class HandoffState(BaseModel):
    """Record of a handoff between agents."""
    handoff_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique handoff ID")
    source_agent: str = Field(..., description="Source agent type")
    target_agent: str = Field(..., description="Target agent type")
    reason: HandoffReason = Field(..., description="Reason for handoff")
    context: Dict[str, Any] = Field(default_factory=dict, description="Handoff context data")
    status: str = Field(
        default="initiated",
        description="Handoff status (initiated/accepted/rejected/completed/failed)"
    )
    initiated_at: datetime = Field(default_factory=datetime.utcnow, description="Initiation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(use_enum_values=False)


class SharedAgentState(BaseModel):
    """Shared state across agent handoffs in a session."""
    state_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique state ID")
    session_id: str = Field(..., description="Session ID")
    current_agent: str = Field(..., description="Currently active agent")
    previous_agents: List[str] = Field(default_factory=list, description="Previously active agents")
    shared_context: Dict[str, Any] = Field(default_factory=dict, description="Shared context data")
    accumulated_facts: List[str] = Field(default_factory=list, description="Accumulated facts/findings")
    pending_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Pending actions")
    handoff_history: List[HandoffState] = Field(default_factory=list, description="Handoff history")

    model_config = ConfigDict(use_enum_values=False)


class HandoffConfig(BaseModel):
    """Configuration for handoff protocol."""
    max_handoffs_per_session: int = Field(5, description="Max handoffs allowed per session")
    handoff_timeout_seconds: int = Field(30, description="Timeout for handoff acceptance")
    require_acceptance: bool = Field(True, description="Require target agent acceptance")
    preserve_full_context: bool = Field(True, description="Preserve full conversation context")
    allowed_handoff_pairs: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "leave_agent": ["compensation_agent", "policy_agent", "general_agent"],
            "compensation_agent": ["leave_agent", "benefits_agent", "policy_agent"],
            "benefits_agent": ["compensation_agent", "policy_agent", "general_agent"],
            "policy_agent": ["leave_agent", "compensation_agent", "benefits_agent"],
            "general_agent": ["leave_agent", "compensation_agent", "benefits_agent"],
        },
        description="Allowed agent pairs for handoff"
    )

    model_config = ConfigDict(use_enum_values=False)


# ============================================================================
# Handoff Protocol
# ============================================================================

class HandoffProtocol:
    """
    Cross-agent handoff protocol with shared state management.

    Manages handoff initiation, acceptance/rejection, state preservation,
    and maintains shared context across agent transitions in a session.
    """

    def __init__(
        self,
        config: HandoffConfig,
        agent_registry: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize handoff protocol.

        Args:
            config: HandoffConfig instance
            agent_registry: Optional registry of available agents
        """
        self.config = config
        self.agent_registry = agent_registry or {}
        self.shared_states: Dict[str, SharedAgentState] = {}
        self.handoff_records: Dict[str, HandoffState] = {}
        self.pending_handoffs: Dict[str, HandoffState] = {}  # handoff_id -> HandoffState
        self.stats = {
            'total_handoffs': 0,
            'accepted_handoffs': 0,
            'rejected_handoffs': 0,
            'failed_handoffs': 0,
            'active_sessions': 0,
        }

        logger.info("HandoffProtocol initialized")

    def initiate_handoff(
        self,
        session_id: str,
        source_agent: str,
        target_agent: str,
        reason: HandoffReason,
        context: Optional[Dict[str, Any]] = None,
    ) -> HandoffState:
        """
        Initiate a handoff from source to target agent.

        Args:
            session_id: Session ID
            source_agent: Source agent type
            target_agent: Target agent type
            reason: Handoff reason
            context: Optional handoff context

        Returns:
            HandoffState instance

        Raises:
            ValueError: If handoff validation fails
        """
        try:
            # Validate handoff pair
            if not self.can_handoff(source_agent, target_agent):
                raise ValueError(
                    f"Handoff from {source_agent} to {target_agent} is not allowed"
                )

            # Get or create shared state
            if session_id not in self.shared_states:
                shared_state = SharedAgentState(
                    session_id=session_id,
                    current_agent=source_agent,
                )
                self.shared_states[session_id] = shared_state
                self.stats['active_sessions'] += 1
            else:
                shared_state = self.shared_states[session_id]

            # Check handoff limit
            handoff_count = len([
                h for h in self.handoff_records.values()
                if h.status != "failed"
            ])
            if handoff_count >= self.config.max_handoffs_per_session:
                raise ValueError(
                    f"Session {session_id} has exceeded max handoffs "
                    f"({self.config.max_handoffs_per_session})"
                )

            # Create handoff state
            handoff = HandoffState(
                source_agent=source_agent,
                target_agent=target_agent,
                reason=reason,
                context=context or {},
                status="initiated",
            )

            # Store handoff
            self.handoff_records[handoff.handoff_id] = handoff
            self.pending_handoffs[handoff.handoff_id] = handoff
            self.stats['total_handoffs'] += 1

            logger.info(
                f"Initiated handoff {handoff.handoff_id}: "
                f"{source_agent} -> {target_agent} ({reason})"
            )

            return handoff

        except Exception as e:
            logger.error(f"Error initiating handoff: {e}")
            raise ValueError(f"Failed to initiate handoff: {e}")

    def accept_handoff(self, handoff_id: str) -> HandoffState:
        """
        Accept a pending handoff request.

        Args:
            handoff_id: Handoff ID to accept

        Returns:
            Updated HandoffState

        Raises:
            ValueError: If handoff not found or invalid state
        """
        try:
            handoff = self._get_handoff(handoff_id)

            if handoff.status != "initiated":
                raise ValueError(f"Cannot accept handoff in {handoff.status} state")

            handoff.status = "accepted"

            # Remove from pending
            if handoff_id in self.pending_handoffs:
                del self.pending_handoffs[handoff_id]

            self.stats['accepted_handoffs'] += 1

            logger.info(f"Accepted handoff: {handoff_id}")
            return handoff

        except Exception as e:
            logger.error(f"Error accepting handoff: {e}")
            raise ValueError(f"Failed to accept handoff: {e}")

    def reject_handoff(self, handoff_id: str, reason: str = "") -> HandoffState:
        """
        Reject a pending handoff request.

        Args:
            handoff_id: Handoff ID to reject
            reason: Rejection reason

        Returns:
            Updated HandoffState

        Raises:
            ValueError: If handoff not found or invalid state
        """
        try:
            handoff = self._get_handoff(handoff_id)

            if handoff.status != "initiated":
                raise ValueError(f"Cannot reject handoff in {handoff.status} state")

            handoff.status = "rejected"
            handoff.metadata['rejection_reason'] = reason

            # Remove from pending
            if handoff_id in self.pending_handoffs:
                del self.pending_handoffs[handoff_id]

            self.stats['rejected_handoffs'] += 1

            logger.info(f"Rejected handoff: {handoff_id} - {reason}")
            return handoff

        except Exception as e:
            logger.error(f"Error rejecting handoff: {e}")
            raise ValueError(f"Failed to reject handoff: {e}")

    def complete_handoff(self, handoff_id: str, result: Optional[Dict[str, Any]] = None) -> HandoffState:
        """
        Mark a handoff as completed with optional result data.

        Args:
            handoff_id: Handoff ID to complete
            result: Optional result data from target agent

        Returns:
            Updated HandoffState

        Raises:
            ValueError: If handoff not found
        """
        try:
            handoff = self._get_handoff(handoff_id)

            if handoff.status not in ["accepted", "initiated"]:
                raise ValueError(f"Cannot complete handoff in {handoff.status} state")

            handoff.status = "completed"
            handoff.completed_at = datetime.utcnow()
            if result:
                handoff.metadata['result'] = result

            # Remove from pending
            if handoff_id in self.pending_handoffs:
                del self.pending_handoffs[handoff_id]

            logger.info(f"Completed handoff: {handoff_id}")
            return handoff

        except Exception as e:
            logger.error(f"Error completing handoff: {e}")
            raise ValueError(f"Failed to complete handoff: {e}")

    def get_shared_state(self, session_id: str) -> SharedAgentState:
        """
        Get shared state for a session.

        Args:
            session_id: Session ID

        Returns:
            SharedAgentState instance

        Raises:
            ValueError: If session not found
        """
        try:
            if session_id not in self.shared_states:
                raise ValueError(f"Session not found: {session_id}")

            return self.shared_states[session_id]

        except Exception as e:
            logger.error(f"Error retrieving shared state: {e}")
            raise ValueError(f"Failed to retrieve shared state: {e}")

    def update_shared_context(self, session_id: str, key: str, value: Any) -> SharedAgentState:
        """
        Update shared context data for a session.

        Args:
            session_id: Session ID
            key: Context key
            value: Context value

        Returns:
            Updated SharedAgentState

        Raises:
            ValueError: If session not found
        """
        try:
            shared_state = self.get_shared_state(session_id)
            shared_state.shared_context[key] = value
            logger.debug(f"Updated context for session {session_id}: {key}")
            return shared_state

        except Exception as e:
            logger.error(f"Error updating shared context: {e}")
            raise ValueError(f"Failed to update shared context: {e}")

    def add_accumulated_fact(self, session_id: str, fact: str) -> SharedAgentState:
        """
        Add accumulated fact to session state.

        Args:
            session_id: Session ID
            fact: Fact to accumulate

        Returns:
            Updated SharedAgentState
        """
        try:
            shared_state = self.get_shared_state(session_id)

            if fact not in shared_state.accumulated_facts:
                shared_state.accumulated_facts.append(fact)

            logger.debug(f"Added fact to session {session_id}")
            return shared_state

        except Exception as e:
            logger.error(f"Error adding accumulated fact: {e}")
            raise ValueError(f"Failed to add fact: {e}")

    def add_pending_action(self, session_id: str, action: Dict[str, Any]) -> SharedAgentState:
        """
        Add pending action to session state.

        Args:
            session_id: Session ID
            action: Action dictionary with 'type' and 'details'

        Returns:
            Updated SharedAgentState

        Raises:
            ValueError: If action format invalid
        """
        try:
            if 'type' not in action:
                raise ValueError("Action must have 'type' field")

            shared_state = self.get_shared_state(session_id)
            action['added_at'] = datetime.utcnow().isoformat()
            shared_state.pending_actions.append(action)

            logger.debug(f"Added pending action to session {session_id}: {action['type']}")
            return shared_state

        except Exception as e:
            logger.error(f"Error adding pending action: {e}")
            raise ValueError(f"Failed to add pending action: {e}")

    def get_handoff_history(self, session_id: str) -> List[HandoffState]:
        """
        Get handoff history for a session.

        Args:
            session_id: Session ID

        Returns:
            List of HandoffState objects

        Raises:
            ValueError: If session not found
        """
        try:
            shared_state = self.get_shared_state(session_id)
            logger.debug(f"Retrieved handoff history for session {session_id}")
            return shared_state.handoff_history

        except Exception as e:
            logger.error(f"Error retrieving handoff history: {e}")
            raise ValueError(f"Failed to retrieve handoff history: {e}")

    def can_handoff(self, source_agent: str, target_agent: str) -> bool:
        """
        Check if handoff from source to target agent is allowed.

        Args:
            source_agent: Source agent type
            target_agent: Target agent type

        Returns:
            True if handoff is allowed
        """
        try:
            allowed_targets = self.config.allowed_handoff_pairs.get(source_agent, [])
            is_allowed = target_agent in allowed_targets

            if not is_allowed:
                logger.debug(
                    f"Handoff {source_agent} -> {target_agent} not in allowed pairs"
                )

            return is_allowed

        except Exception as e:
            logger.error(f"Error checking handoff permission: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get handoff protocol statistics.

        Returns:
            Dictionary with current statistics
        """
        try:
            stats = {
                **self.stats,
                'pending_handoffs': len(self.pending_handoffs),
                'total_recorded_handoffs': len(self.handoff_records),
                'active_sessions': len(self.shared_states),
                'timestamp': datetime.utcnow().isoformat(),
            }

            logger.debug(f"Handoff protocol stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error retrieving stats: {e}")
            return {}

    def _get_handoff(self, handoff_id: str) -> HandoffState:
        """
        Internal helper to retrieve handoff record.

        Args:
            handoff_id: Handoff ID

        Returns:
            HandoffState instance

        Raises:
            ValueError: If handoff not found
        """
        handoff = self.handoff_records.get(handoff_id)
        if not handoff:
            raise ValueError(f"Handoff not found: {handoff_id}")
        return handoff

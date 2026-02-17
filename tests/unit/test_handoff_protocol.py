"""
Unit tests for handoff_protocol.py module.

Tests cover HandoffProtocol and all related models with comprehensive
coverage of handoff lifecycle, shared state management, and validation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import uuid

from src.agents.handoff_protocol import (
    HandoffReason,
    HandoffState,
    SharedAgentState,
    HandoffConfig,
    HandoffProtocol,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def handoff_config():
    """Create a HandoffConfig for testing."""
    return HandoffConfig(
        max_handoffs_per_session=5,
        handoff_timeout_seconds=30,
        require_acceptance=True
    )


@pytest.fixture
def handoff_protocol(handoff_config):
    """Create a HandoffProtocol instance."""
    return HandoffProtocol(handoff_config)


# ============================================================================
# Test HandoffReason Enum
# ============================================================================

class TestHandoffReason:
    """Tests for HandoffReason enum."""

    def test_reason_expertise_required(self):
        """Test EXPERTISE_REQUIRED reason exists."""
        assert HandoffReason.EXPERTISE_REQUIRED == "expertise_required"

    def test_reason_escalation(self):
        """Test ESCALATION reason exists."""
        assert HandoffReason.ESCALATION == "escalation"

    def test_reason_workflow_continuation(self):
        """Test WORKFLOW_CONTINUATION reason exists."""
        assert HandoffReason.WORKFLOW_CONTINUATION == "workflow_continuation"

    def test_reason_enum_count(self):
        """Test HandoffReason enum has 6 values."""
        assert len(HandoffReason) == 6

    def test_reason_string_representation(self):
        """Test reason string representation."""
        assert str(HandoffReason.EXPERTISE_REQUIRED.value) == "expertise_required"


# ============================================================================
# Test HandoffState Model
# ============================================================================

class TestHandoffState:
    """Tests for HandoffState model."""

    def test_state_defaults(self):
        """Test HandoffState default values."""
        state = HandoffState(
            source_agent="agent1",
            target_agent="agent2",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        assert state.status == "initiated"
        assert state.completed_at is None

    def test_state_custom_values(self):
        """Test HandoffState with custom values."""
        context = {"user_id": "user1", "session": "sess1"}
        state = HandoffState(
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.ESCALATION,
            context=context
        )
        assert state.context == context

    def test_state_uuid(self):
        """Test HandoffState generates unique handoff_id."""
        state1 = HandoffState(
            source_agent="agent1",
            target_agent="agent2",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        state2 = HandoffState(
            source_agent="agent1",
            target_agent="agent2",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        assert state1.handoff_id != state2.handoff_id
        assert len(state1.handoff_id) > 0

    def test_state_status_tracking(self):
        """Test HandoffState tracks status correctly."""
        state = HandoffState(
            source_agent="agent1",
            target_agent="agent2",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        assert state.status == "initiated"
        state.status = "accepted"
        assert state.status == "accepted"


# ============================================================================
# Test SharedAgentState Model
# ============================================================================

class TestSharedAgentState:
    """Tests for SharedAgentState model."""

    def test_state_defaults(self):
        """Test SharedAgentState default values."""
        state = SharedAgentState(
            session_id="session1",
            current_agent="agent1"
        )
        assert state.previous_agents == []
        assert state.shared_context == {}

    def test_state_custom_values(self):
        """Test SharedAgentState with custom values."""
        state = SharedAgentState(
            session_id="session1",
            current_agent="agent2",
            previous_agents=["agent1"],
            shared_context={"key": "value"}
        )
        assert state.previous_agents == ["agent1"]
        assert state.shared_context["key"] == "value"

    def test_state_previous_agents_list(self):
        """Test SharedAgentState maintains previous agents list."""
        state = SharedAgentState(
            session_id="session1",
            current_agent="agent1",
            previous_agents=["agent0", "agent1"]
        )
        assert isinstance(state.previous_agents, list)
        assert len(state.previous_agents) == 2

    def test_state_accumulated_facts(self):
        """Test SharedAgentState accumulates facts."""
        state = SharedAgentState(
            session_id="session1",
            current_agent="agent1",
            accumulated_facts=["fact1", "fact2"]
        )
        assert isinstance(state.accumulated_facts, list)
        assert len(state.accumulated_facts) == 2


# ============================================================================
# Test HandoffConfig Model
# ============================================================================

class TestHandoffConfig:
    """Tests for HandoffConfig model."""

    def test_config_defaults(self):
        """Test HandoffConfig default values."""
        config = HandoffConfig()
        assert config.max_handoffs_per_session == 5
        assert config.require_acceptance is True
        assert config.preserve_full_context is True

    def test_config_custom_values(self):
        """Test HandoffConfig with custom values."""
        config = HandoffConfig(
            max_handoffs_per_session=10,
            require_acceptance=False
        )
        assert config.max_handoffs_per_session == 10
        assert config.require_acceptance is False

    def test_config_max_handoffs(self):
        """Test HandoffConfig max_handoffs_per_session."""
        config = HandoffConfig(max_handoffs_per_session=3)
        assert config.max_handoffs_per_session == 3

    def test_config_allowed_pairs(self):
        """Test HandoffConfig allowed handoff pairs."""
        config = HandoffConfig()
        assert "leave_agent" in config.allowed_handoff_pairs
        assert "compensation_agent" in config.allowed_handoff_pairs["leave_agent"]


# ============================================================================
# Test HandoffProtocol Initialization
# ============================================================================

class TestHandoffProtocolInit:
    """Tests for HandoffProtocol initialization."""

    def test_protocol_creates_with_config(self, handoff_config):
        """Test protocol initializes with config."""
        protocol = HandoffProtocol(handoff_config)
        assert protocol is not None

    def test_protocol_empty_state(self, handoff_config):
        """Test protocol starts with empty state."""
        protocol = HandoffProtocol(handoff_config)
        assert len(protocol.shared_states) == 0
        assert len(protocol.handoff_records) == 0

    def test_protocol_no_registry(self, handoff_config):
        """Test protocol initializes without agent registry."""
        protocol = HandoffProtocol(handoff_config)
        assert protocol.agent_registry == {}


# ============================================================================
# Test Initiate Handoff
# ============================================================================

class TestInitiateHandoff:
    """Tests for HandoffProtocol.initiate_handoff method."""

    def test_creates_handoff(self, handoff_protocol):
        """Test initiate_handoff creates a handoff."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        assert isinstance(handoff, HandoffState)

    def test_assigns_uuid(self, handoff_protocol):
        """Test initiate_handoff assigns handoff_id."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.ESCALATION
        )
        assert len(handoff.handoff_id) > 0

    def test_validates_agents(self, handoff_protocol):
        """Test initiate_handoff validates agent pair."""
        with pytest.raises(ValueError, match="not allowed"):
            handoff_protocol.initiate_handoff(
                session_id="sess1",
                source_agent="invalid_agent",
                target_agent="compensation_agent",
                reason=HandoffReason.EXPERTISE_REQUIRED
            )

    def test_stores_state(self, handoff_protocol):
        """Test initiate_handoff stores handoff state."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        assert handoff.handoff_id in handoff_protocol.handoff_records


# ============================================================================
# Test Accept Handoff
# ============================================================================

class TestAcceptHandoff:
    """Tests for HandoffProtocol.accept_handoff method."""

    def test_accepts_handoff(self, handoff_protocol):
        """Test accept_handoff updates status."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        accepted = handoff_protocol.accept_handoff(handoff.handoff_id)
        assert accepted.status == "accepted"

    def test_updates_status(self, handoff_protocol):
        """Test accept_handoff changes initiated to accepted."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.WORKFLOW_CONTINUATION
        )
        original_status = handoff.status
        accepted = handoff_protocol.accept_handoff(handoff.handoff_id)
        assert original_status == "initiated"
        assert accepted.status == "accepted"

    def test_missing_handoff(self, handoff_protocol):
        """Test accept_handoff with missing handoff."""
        with pytest.raises(ValueError):
            handoff_protocol.accept_handoff("nonexistent")


# ============================================================================
# Test Reject Handoff
# ============================================================================

class TestRejectHandoff:
    """Tests for HandoffProtocol.reject_handoff method."""

    def test_rejects_handoff(self, handoff_protocol):
        """Test reject_handoff updates status."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        rejected = handoff_protocol.reject_handoff(handoff.handoff_id)
        assert rejected.status == "rejected"

    def test_records_reason(self, handoff_protocol):
        """Test reject_handoff records rejection reason."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.ESCALATION
        )
        reason = "Agent unavailable"
        rejected = handoff_protocol.reject_handoff(handoff.handoff_id, reason)
        assert rejected.metadata['rejection_reason'] == reason

    def test_missing_handoff(self, handoff_protocol):
        """Test reject_handoff with missing handoff."""
        with pytest.raises(ValueError):
            handoff_protocol.reject_handoff("nonexistent")


# ============================================================================
# Test Complete Handoff
# ============================================================================

class TestCompleteHandoff:
    """Tests for HandoffProtocol.complete_handoff method."""

    def test_completes_handoff(self, handoff_protocol):
        """Test complete_handoff updates status."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        completed = handoff_protocol.complete_handoff(handoff.handoff_id)
        assert completed.status == "completed"

    def test_stores_result(self, handoff_protocol):
        """Test complete_handoff stores result data."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        result = {"outcome": "success"}
        completed = handoff_protocol.complete_handoff(handoff.handoff_id, result)
        assert completed.metadata['result'] == result

    def test_timestamps(self, handoff_protocol):
        """Test complete_handoff records completion timestamp."""
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.WORKFLOW_CONTINUATION
        )
        completed = handoff_protocol.complete_handoff(handoff.handoff_id)
        assert completed.completed_at is not None


# ============================================================================
# Test Get Shared State
# ============================================================================

class TestGetSharedState:
    """Tests for HandoffProtocol.get_shared_state method."""

    def test_returns_state(self, handoff_protocol):
        """Test get_shared_state returns state."""
        handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        state = handoff_protocol.get_shared_state("sess1")
        assert isinstance(state, SharedAgentState)

    def test_creates_if_missing(self, handoff_protocol):
        """Test get_shared_state creates state if missing."""
        handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        assert "sess1" in handoff_protocol.shared_states
        state = handoff_protocol.get_shared_state("sess1")
        assert state.session_id == "sess1"

    def test_stores_session(self, handoff_protocol):
        """Test get_shared_state stores session state."""
        handoff_protocol.initiate_handoff(
            session_id="sess2",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.USER_REQUEST
        )
        state = handoff_protocol.get_shared_state("sess2")
        assert state in handoff_protocol.shared_states.values()


# ============================================================================
# Test Update Shared Context
# ============================================================================

class TestUpdateSharedContext:
    """Tests for HandoffProtocol.update_shared_context method."""

    def test_adds_key_value(self, handoff_protocol):
        """Test update_shared_context adds key-value pair."""
        handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        state = handoff_protocol.update_shared_context("sess1", "user_id", "user123")
        assert state.shared_context["user_id"] == "user123"

    def test_updates_existing(self, handoff_protocol):
        """Test update_shared_context updates existing key."""
        handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        handoff_protocol.update_shared_context("sess1", "key1", "value1")
        state = handoff_protocol.update_shared_context("sess1", "key1", "value2")
        assert state.shared_context["key1"] == "value2"

    def test_returns_state(self, handoff_protocol):
        """Test update_shared_context returns updated state."""
        handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        state = handoff_protocol.update_shared_context("sess1", "test", "value")
        assert isinstance(state, SharedAgentState)


# ============================================================================
# Test Can Handoff
# ============================================================================

class TestCanHandoff:
    """Tests for HandoffProtocol.can_handoff method."""

    def test_allowed_pair_true(self, handoff_protocol):
        """Test can_handoff returns True for allowed pair."""
        result = handoff_protocol.can_handoff("leave_agent", "compensation_agent")
        assert result is True

    def test_disallowed_pair_false(self, handoff_protocol):
        """Test can_handoff returns False for disallowed pair."""
        result = handoff_protocol.can_handoff("invalid_agent", "compensation_agent")
        assert result is False

    def test_no_restrictions_allows_all(self):
        """Test can_handoff with no restrictions."""
        config = HandoffConfig(allowed_handoff_pairs={})
        protocol = HandoffProtocol(config)
        # Empty pairs means no handoffs allowed
        result = protocol.can_handoff("any_agent", "other_agent")
        assert result is False


# ============================================================================
# Test Get Stats
# ============================================================================

class TestGetStats:
    """Tests for HandoffProtocol.get_stats method."""

    def test_returns_stats(self, handoff_protocol):
        """Test get_stats returns statistics."""
        stats = handoff_protocol.get_stats()
        assert isinstance(stats, dict)
        assert 'total_handoffs' in stats

    def test_handoff_counts(self, handoff_protocol):
        """Test get_stats includes handoff counts."""
        handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        stats = handoff_protocol.get_stats()
        assert stats['total_handoffs'] == 1

    def test_session_counts(self, handoff_protocol):
        """Test get_stats includes session counts."""
        handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        stats = handoff_protocol.get_stats()
        assert stats['active_sessions'] > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestHandoffLifecycle:
    """Integration tests for complete handoff lifecycle."""

    def test_full_handoff_workflow(self, handoff_protocol):
        """Test complete handoff workflow."""
        # Initiate handoff
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        assert handoff.status == "initiated"

        # Accept handoff
        accepted = handoff_protocol.accept_handoff(handoff.handoff_id)
        assert accepted.status == "accepted"

        # Complete handoff
        completed = handoff_protocol.complete_handoff(handoff.handoff_id)
        assert completed.status == "completed"

    def test_rejection_workflow(self, handoff_protocol):
        """Test handoff rejection workflow."""
        # Initiate handoff
        handoff = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.ESCALATION
        )

        # Reject handoff
        rejected = handoff_protocol.reject_handoff(
            handoff.handoff_id,
            "Not available"
        )
        assert rejected.status == "rejected"
        assert rejected.metadata['rejection_reason'] == "Not available"

    def test_shared_state_accumulation(self, handoff_protocol):
        """Test shared state accumulation across handoffs."""
        # First handoff
        handoff1 = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )

        # Update context
        handoff_protocol.update_shared_context("sess1", "user_id", "user1")
        handoff_protocol.update_shared_context("sess1", "leave_type", "annual")

        # Verify context
        state = handoff_protocol.get_shared_state("sess1")
        assert state.shared_context["user_id"] == "user1"
        assert state.shared_context["leave_type"] == "annual"

    def test_multiple_handoffs_same_session(self, handoff_protocol):
        """Test multiple handoffs in same session."""
        # First handoff
        h1 = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        handoff_protocol.complete_handoff(h1.handoff_id)

        # Second handoff
        h2 = handoff_protocol.initiate_handoff(
            session_id="sess1",
            source_agent="compensation_agent",
            target_agent="benefits_agent",
            reason=HandoffReason.WORKFLOW_CONTINUATION
        )

        stats = handoff_protocol.get_stats()
        assert stats['total_handoffs'] == 2
        assert len(handoff_protocol.handoff_records) == 2

    def test_handoff_limit_enforcement(self):
        """Test handoff limit enforcement."""
        config = HandoffConfig(max_handoffs_per_session=2)
        protocol = HandoffProtocol(config)

        # First two handoffs should succeed
        h1 = protocol.initiate_handoff(
            session_id="sess1",
            source_agent="leave_agent",
            target_agent="compensation_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )
        h2 = protocol.initiate_handoff(
            session_id="sess1",
            source_agent="compensation_agent",
            target_agent="benefits_agent",
            reason=HandoffReason.EXPERTISE_REQUIRED
        )

        # Third handoff should fail
        with pytest.raises(ValueError, match="exceeded max handoffs"):
            protocol.initiate_handoff(
                session_id="sess1",
                source_agent="benefits_agent",
                target_agent="policy_agent",
                reason=HandoffReason.EXPERTISE_REQUIRED
            )

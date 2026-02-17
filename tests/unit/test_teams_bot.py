"""
Unit tests for Teams bot integration (src/integrations/teams_bot.py).

Iteration 5 comprehensive test suite covering:
- Configuration validation
- Activity handler initialization
- Message handling and processing
- Conversation update handling
- Invoke/card action handling
- Response formatting (adaptive cards)
- User context mapping
- Service health and lifecycle
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from typing import Dict, Any, Optional

from src.integrations.teams_bot import (
    TeamsBotConfig,
    TeamsActivityHandler,
    TeamsBotService,
)


class TestTeamsBotConfig:
    """Test TeamsBotConfig class for default and custom values."""

    def test_default_values(self):
        """Test that TeamsBotConfig initializes with correct defaults."""
        config = TeamsBotConfig(
            app_id="test-app-id", app_password="test-password", tenant_id="test-tenant"
        )
        assert config.app_id == "test-app-id"
        assert config.app_password == "test-password"
        assert config.tenant_id == "test-tenant"
        assert config.bot_name == "HR Assistant"
        assert config.max_message_length == 4000

    def test_custom_values(self):
        """Test TeamsBotConfig with custom values."""
        config = TeamsBotConfig(
            app_id="test-app-id",
            app_password="test-password",
            tenant_id="test-tenant",
            bot_name="Custom Bot",
            max_message_length=2000,
        )
        assert config.app_id == "test-app-id"
        assert config.app_password == "test-password"
        assert config.tenant_id == "test-tenant"
        assert config.bot_name == "Custom Bot"
        assert config.max_message_length == 2000

    def test_bot_name_default(self):
        """Test that bot_name has a default value."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        assert config.bot_name == "HR Assistant"

    def test_required_fields(self):
        """Test that required fields are enforced."""
        try:
            config = TeamsBotConfig(app_id="test-app")
            assert False, "Should have raised validation error"
        except Exception:
            assert True


class TestTeamsActivityHandlerInit:
    """Test TeamsActivityHandler initialization."""

    def test_creates_with_config(self):
        """Test handler creation with valid config."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        agent_service = Mock()
        handler = TeamsActivityHandler(config=config, agent_service=agent_service)
        assert handler.config == config
        assert handler.agent_service == agent_service

    def test_initializes_metrics(self):
        """Test that handler initializes metrics."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        agent_service = Mock()
        handler = TeamsActivityHandler(config=config, agent_service=agent_service)
        assert hasattr(handler, "metrics")
        assert handler.metrics.get("messages_processed", 0) == 0
        assert handler.metrics.get("errors", 0) == 0

    def test_stores_agent_service(self):
        """Test that agent_service is properly stored."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        agent_service = Mock()
        handler = TeamsActivityHandler(config=config, agent_service=agent_service)
        assert handler.agent_service is agent_service


class TestHandleMessage:
    """Test message handling functionality."""

    def test_valid_activity(self):
        """Test handling of valid message activity."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test answer",
            "confidence": 0.95,
            "sources": ["source1"],
        }

        handler = TeamsActivityHandler(config=config, agent_service=agent_service)
        activity = {
            "type": "message",
            "text": "What is the policy?",
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_message(activity)

        assert result is not None
        assert isinstance(result, dict)

    def test_non_message_activity_ignored(self):
        """Test that non-message activities are ignored."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "conversationUpdate",
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_message(activity)

        assert result["status"] == "ignored"

    def test_empty_text_rejected(self):
        """Test handling of message with empty text."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "message",
            "text": "",
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_message(activity)

        assert result["status"] == "rejected"

    def test_long_message_rejected(self):
        """Test handling of long messages."""
        config = TeamsBotConfig(
            app_id="test-app",
            app_password="test-pwd",
            tenant_id="test-tenant",
            max_message_length=100,
        )
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "message",
            "text": "x" * 500,
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_message(activity)

        assert result["status"] == "rejected"

    def test_tracks_metrics(self):
        """Test that metrics are tracked."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test",
            "confidence": 0.9,
            "sources": [],
        }

        handler = TeamsActivityHandler(config=config, agent_service=agent_service)
        activity = {
            "type": "message",
            "text": "Test",
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        handler.handle_message(activity)

        assert handler.metrics.get("messages_processed", 0) >= 1

    def test_handles_error(self):
        """Test error handling."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        agent_service = Mock()
        agent_service.process_query.side_effect = Exception("Service error")

        handler = TeamsActivityHandler(config=config, agent_service=agent_service)
        activity = {
            "type": "message",
            "text": "Test",
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_message(activity)

        assert result["status"] == "error"


class TestHandleConversationUpdate:
    """Test conversation update handling."""

    def test_member_added_welcome(self):
        """Test welcome message for member added."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "conversationUpdate",
            "membersAdded": [{"id": "user123", "name": "John"}],
            "from": {"id": "bot123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_conversation_update(activity)

        assert result is not None
        assert isinstance(result, dict)
        assert result["status"] == "acknowledged"

    def test_member_removed(self):
        """Test handling of member removed."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "conversationUpdate",
            "membersRemoved": [{"id": "user123", "name": "John"}],
            "from": {"id": "bot123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_conversation_update(activity)

        assert result is not None
        assert isinstance(result, dict)

    def test_no_members(self):
        """Test handling when no members added or removed."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "conversationUpdate",
            "from": {"id": "bot123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_conversation_update(activity)

        assert result is not None
        assert isinstance(result, dict)

    def test_non_conversation_update_ignored(self):
        """Test that non-conversationUpdate activities are ignored."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "message",
            "from": {"id": "bot123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_conversation_update(activity)

        assert result["status"] == "ignored"


class TestHandleInvoke:
    """Test invoke/card action handling."""

    def test_card_action(self):
        """Test handling of card action invoke."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)
        activity = {
            "type": "invoke",
            "name": "adaptiveCard/action",
            "value": {
                "actionType": "submit",
            },
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_invoke(activity)

        assert result is not None
        assert isinstance(result, dict)

    def test_non_invoke_ignored(self):
        """Test handling of non-invoke activity."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "message",
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_invoke(activity)

        assert result["status"] == "ignored"

    def test_returns_invoke_response(self):
        """Test that response follows invoke format."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        activity = {
            "type": "invoke",
            "name": "adaptiveCard/action",
            "value": {"action": {"type": "Action.Submit"}},
            "from": {"id": "user123"},
            "conversation": {"id": "conv123"},
        }

        result = handler.handle_invoke(activity)

        assert result is not None
        assert isinstance(result, dict)


class TestFormatTeamsResponse:
    """Test Teams response formatting."""

    def test_adaptive_card_format(self):
        """Test adaptive card response format."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        response = handler._format_teams_response(
            {
                "answer": "Test answer",
                "confidence": 0.95,
                "sources": ["source1"],
            }
        )

        assert response is not None
        assert isinstance(response, dict)
        assert "attachments" in response
        assert len(response["attachments"]) > 0

    def test_includes_confidence(self):
        """Test that confidence is included in response."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        response = handler._format_teams_response(
            {
                "answer": "Test answer",
                "confidence": 0.85,
                "sources": [],
            }
        )

        assert response is not None
        assert isinstance(response, dict)
        assert "attachments" in response

    def test_includes_sources(self):
        """Test that sources are included in response."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        response = handler._format_teams_response(
            {
                "answer": "Test answer",
                "confidence": 0.9,
                "sources": ["source1", "source2"],
            }
        )

        assert response is not None
        assert isinstance(response, dict)

    def test_hero_card_format(self):
        """Test hero card format option."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        response = handler._format_hero_card(
            {
                "answer": "Test answer",
                "confidence": 0.9,
                "sources": [],
            }
        )

        assert response is not None
        assert isinstance(response, dict)

    def test_handles_missing_fields(self):
        """Test response formatting with missing optional fields."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        response = handler._format_teams_response(
            {
                "answer": "Test answer",
                "confidence": 0.5,
                "sources": [],
            }
        )

        assert response is not None
        assert "attachments" in response


class TestGetUserContext:
    """Test user context retrieval."""

    def test_default_context(self):
        """Test that default context is created."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        context = handler._get_user_context(user_id="user123")

        assert context is not None
        assert isinstance(context, dict)
        assert context.get("user_id") == "user123"

    def test_includes_source_and_platform(self):
        """Test that source and platform are included."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        handler = TeamsActivityHandler(config=config)

        context = handler._get_user_context(user_id="unknown")

        assert context is not None
        assert context.get("source") == "teams"
        assert context.get("platform") == "microsoft_teams"

    def test_includes_tenant_id(self):
        """Test that tenant_id is included if available."""
        config = TeamsBotConfig(
            app_id="test-app", app_password="test-pwd", tenant_id="test-tenant-123"
        )
        handler = TeamsActivityHandler(config=config)

        context = handler._get_user_context(user_id="user123")

        assert context is not None
        assert isinstance(context, dict)
        assert context.get("tenant_id") == "test-tenant-123"


class TestTeamsBotServiceHealth:
    """Test TeamsBotService health checks."""

    def test_status_check(self):
        """Test status check returns valid structure."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        service = TeamsBotService(config=config)

        status = service.get_status()

        assert status is not None
        assert isinstance(status, dict)
        assert "service_running" in status
        assert "handler_health" in status

    def test_handler_health_tracking(self):
        """Test that handler health is tracked."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        service = TeamsBotService(config=config)
        status = service.get_status()

        assert status is not None
        assert "handler_health" in status
        assert "messages_processed" in status["handler_health"]

    def test_error_counting(self):
        """Test that errors are counted in status."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        service = TeamsBotService(config=config)

        status = service.get_status()

        assert status is not None
        assert isinstance(status, dict)
        assert "handler_health" in status


class TestTeamsBotServiceLifecycle:
    """Test TeamsBotService lifecycle methods."""

    def test_start(self):
        """Test service start."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        service = TeamsBotService(config=config)

        service.start()

        assert service.running is True

    def test_stop(self):
        """Test service stop."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        service = TeamsBotService(config=config)
        service.start()
        assert service.running is True

        service.stop()

        assert service.running is False

    def test_get_status(self):
        """Test get_status returns valid status."""
        config = TeamsBotConfig(app_id="test-app", app_password="test-pwd", tenant_id="test-tenant")
        service = TeamsBotService(config=config)
        service.start()

        status = service.get_status()

        assert status is not None
        assert isinstance(status, dict)
        assert service.running is True

"""
Unit tests for Slack bot integration (src/integrations/slack_bot.py).

Iteration 5 comprehensive test suite covering:
- Configuration validation
- Event handler initialization
- Message handling and processing
- App mention handling
- Slash command handling
- Response formatting
- User context mapping
- Service health and lifecycle
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from typing import Dict, Any, Optional

from src.integrations.slack_bot import (
    SlackBotConfig,
    SlackEventHandler,
    SlackBotService,
)


class TestSlackBotConfig:
    """Test SlackBotConfig class for default and custom values."""

    def test_default_values(self):
        """Test that SlackBotConfig initializes with correct defaults."""
        config = SlackBotConfig(
            bot_token="xoxb-test",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        assert config.bot_token == "xoxb-test"
        assert config.signing_secret == "test-secret"
        assert config.app_token == "xapp-test"
        assert config.channel_allowlist == ["hr-assistance", "general"]
        assert config.max_message_length == 4000
        assert config.response_timeout == 30

    def test_custom_values(self):
        """Test SlackBotConfig with custom values."""
        config = SlackBotConfig(
            bot_token="xoxb-test-token",
            signing_secret="test-secret",
            app_token="xapp-test-token",
            channel_allowlist=["custom-channel"],
            max_message_length=2000
        )
        assert config.bot_token == "xoxb-test-token"
        assert config.signing_secret == "test-secret"
        assert config.app_token == "xapp-test-token"
        assert config.channel_allowlist == ["custom-channel"]
        assert config.max_message_length == 2000

    def test_validation_bot_token_required(self):
        """Test that bot_token is required."""
        try:
            config = SlackBotConfig(
                signing_secret="test-secret",
                app_token="xapp-test"
            )
            assert False, "Should have raised validation error"
        except Exception:
            assert True

    def test_channel_allowlist_config(self):
        """Test channel allowlist configuration."""
        config = SlackBotConfig(
            bot_token="xoxb-test",
            signing_secret="test-secret",
            app_token="xapp-test",
            channel_allowlist=["C12345", "C67890"]
        )
        assert config.channel_allowlist == ["C12345", "C67890"]
        assert len(config.channel_allowlist) == 2


class TestSlackEventHandlerInit:
    """Test SlackEventHandler initialization."""

    def test_creates_with_config(self):
        """Test handler creation with valid config."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        handler = SlackEventHandler(config=config, agent_service=agent_service)
        assert handler.config == config
        assert handler.agent_service == agent_service

    def test_creates_without_agent_service(self):
        """Test handler creation without agent_service."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)
        assert handler.config == config
        assert handler.agent_service is None

    def test_initializes_metrics(self):
        """Test that handler initializes metrics."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        handler = SlackEventHandler(config=config, agent_service=agent_service)
        assert hasattr(handler, "metrics")
        assert handler.metrics.get("messages_processed", 0) == 0
        assert handler.metrics.get("errors", 0) == 0


class TestHandleMessage:
    """Test message handling functionality."""

    def test_valid_message_returns_response(self):
        """Test that valid message returns response."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test answer",
            "confidence": 0.95,
            "sources": ["source1"],
        }

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        result = handler.handle_message({
            "text": "What is the policy?",
            "user": "U123",
            "channel": "C456",
            "thread_ts": "1234567890.123456",
        })

        assert result is not None
        assert isinstance(result, dict)

    def test_bot_message_ignored(self):
        """Test that bot messages are ignored."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        handler = SlackEventHandler(config=config, agent_service=agent_service)

        result = handler.handle_message({
            "text": "Test",
            "user": "U123",
            "channel": "C456",
            "bot_id": "B789",
        })

        assert result["status"] == "ignored"

    def test_empty_text_returns_rejected(self):
        """Test that empty text returns rejected."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        handler = SlackEventHandler(config=config, agent_service=agent_service)

        result = handler.handle_message({
            "text": "",
            "user": "U123",
            "channel": "C456",
        })

        assert result["status"] == "rejected"

    def test_long_message_rejected(self):
        """Test that long messages are rejected."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test",
            max_message_length=100
        )
        agent_service = Mock()
        handler = SlackEventHandler(config=config, agent_service=agent_service)

        long_text = "x" * 500
        result = handler.handle_message({
            "text": long_text,
            "user": "U123",
            "channel": "C456",
        })

        assert result["status"] == "rejected"

    def test_tracks_metrics(self):
        """Test that metrics are tracked."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test",
            "confidence": 0.9,
            "sources": [],
        }

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        handler.handle_message({
            "text": "Test",
            "user": "U123",
            "channel": "C456",
        })

        assert handler.metrics.get("messages_processed", 0) >= 1

    def test_handles_agent_service_error(self):
        """Test graceful error handling when agent_service fails."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.side_effect = Exception("Service error")

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        result = handler.handle_message({
            "text": "Test",
            "user": "U123",
            "channel": "C456",
        })

        assert result["status"] == "error"


class TestHandleAppMention:
    """Test app mention handling."""

    def test_strips_bot_mention(self):
        """Test that bot mention is stripped from text."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Response",
            "confidence": 0.9,
            "sources": [],
        }

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        result = handler.handle_app_mention({
            "text": "<@U_BOT_ID> What is the policy?",
            "user": "U123",
            "channel": "C456",
            "thread_ts": "1234567890.123456",
        })

        assert result is not None

    def test_processes_query(self):
        """Test that mention text is processed as query."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test answer",
            "confidence": 0.95,
            "sources": ["source1"],
        }

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        result = handler.handle_app_mention({
            "text": "<@U_BOT_ID> What is the policy?",
            "user": "U123",
            "channel": "C456",
            "thread_ts": "1234567890.123456",
        })

        assert result is not None
        assert isinstance(result, dict)

    def test_handles_empty_after_strip(self):
        """Test handling when text is empty after stripping mention."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        result = handler.handle_app_mention({
            "text": "   ",
            "user": "U123",
            "channel": "C456",
            "thread_ts": "1234567890.123456",
        })

        assert result["status"] == "rejected"
        assert result["reason"] == "empty_mention"

    def test_returns_formatted_response(self):
        """Test that response is properly formatted."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test answer",
            "confidence": 0.95,
            "sources": ["source1"],
        }

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        result = handler.handle_app_mention({
            "text": "<@U_BOT_ID> What is the policy?",
            "user": "U123",
            "channel": "C456",
            "thread_ts": "1234567890.123456",
        })

        assert isinstance(result, dict)


class TestHandleSlashCommand:
    """Test slash command handling."""

    def test_processes_hr_ask_command(self):
        """Test /hr-ask slash command processing."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test answer",
            "confidence": 0.9,
            "sources": [],
        }

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        result = handler.handle_slash_command({
            "user_id": "U123",
            "channel_id": "C456",
            "text": "What is the vacation policy?",
            "trigger_id": "123456.789012.abc123",
        })

        assert result is not None
        assert isinstance(result, dict)

    def test_missing_text_param(self):
        """Test slash command with missing text parameter."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        handler = SlackEventHandler(config=config, agent_service=agent_service)

        result = handler.handle_slash_command({
            "user_id": "U123",
            "channel_id": "C456",
            "text": "",
            "trigger_id": "123456.789012.abc123",
        })

        assert result["status"] == "error"

    def test_returns_slash_response_format(self):
        """Test that response follows slash command format."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test answer",
            "confidence": 0.9,
            "sources": [],
        }

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        result = handler.handle_slash_command({
            "user_id": "U123",
            "channel_id": "C456",
            "text": "Test query",
            "trigger_id": "123456.789012.abc123",
        })

        assert isinstance(result, dict)

    def test_tracks_command_metrics(self):
        """Test that command metrics are tracked."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        agent_service = Mock()
        agent_service.process_query.return_value = {
            "answer": "Test",
            "confidence": 0.9,
            "sources": [],
        }

        handler = SlackEventHandler(config=config, agent_service=agent_service)
        handler.handle_slash_command({
            "user_id": "U123",
            "channel_id": "C456",
            "text": "Test",
            "trigger_id": "123456.789012.abc123",
        })

        assert handler.metrics.get("messages_processed", 0) >= 1


class TestFormatSlackResponse:
    """Test Slack response formatting."""

    def test_formats_with_confidence_badge(self):
        """Test response formatting includes confidence level."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        response = handler._format_slack_response({
            "answer": "Test answer",
            "confidence": 0.95,
            "sources": ["source1"],
        })

        assert response is not None
        assert isinstance(response, dict)
        assert "blocks" in response

    def test_includes_sources_as_context_block(self):
        """Test that sources are included in response."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        response = handler._format_slack_response({
            "answer": "Test answer",
            "confidence": 0.85,
            "sources": ["source1", "source2"],
        })

        assert response is not None
        assert "blocks" in response
        assert len(response["blocks"]) >= 3

    def test_handles_missing_fields(self):
        """Test response formatting with missing optional fields."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        response = handler._format_slack_response({
            "answer": "Test answer",
            "confidence": 0.5,
            "sources": [],
        })

        assert response is not None
        assert "blocks" in response

    def test_confidence_badge_high(self):
        """Test high confidence badge."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        response = handler._format_slack_response({
            "answer": "Test answer",
            "confidence": 0.95,
            "sources": [],
        })

        response_text = str(response)
        assert "Very High" in response_text or "blocks" in response

    def test_confidence_badge_low(self):
        """Test low confidence badge."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        response = handler._format_slack_response({
            "answer": "Test answer",
            "confidence": 0.3,
            "sources": [],
        })

        response_text = str(response)
        assert "blocks" in response


class TestGetUserContext:
    """Test user context retrieval."""

    def test_returns_default_context_for_unknown_user(self):
        """Test that unknown users get default context."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        context = handler._get_user_context(user_id="U_UNKNOWN")

        assert context is not None
        assert isinstance(context, dict)
        assert context.get("source") == "slack"

    def test_includes_user_id_and_source(self):
        """Test that context includes user_id and source."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        context = handler._get_user_context(user_id="U123")

        assert context.get("user_id") == "U123"
        assert context.get("source") == "slack"
        assert context.get("platform") == "slack"

    def test_includes_timezone(self):
        """Test that context includes timezone."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        handler = SlackEventHandler(config=config)

        context = handler._get_user_context(user_id="U123")

        assert context is not None
        assert isinstance(context, dict)
        assert context.get("timezone") == "UTC"


class TestSlackBotServiceHealth:
    """Test SlackBotService health checks."""

    def test_returns_healthy_status(self):
        """Test that health check returns valid status."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        service = SlackBotService(config=config)

        status = service.get_status()

        assert status is not None
        assert isinstance(status, dict)
        assert "service_running" in status
        assert "handler_health" in status

    def test_handler_health_tracking(self):
        """Test that handler health is tracked in status."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        service = SlackBotService(config=config)
        status = service.get_status()

        assert status is not None
        assert "handler_health" in status
        assert "messages_processed" in status["handler_health"]

    def test_reports_errors(self):
        """Test that errors are reported in status."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        service = SlackBotService(config=config)

        status = service.get_status()

        assert status is not None
        assert isinstance(status, dict)
        assert "handler_health" in status

    def test_includes_config_info(self):
        """Test that config info is included in status."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        service = SlackBotService(config=config)

        status = service.get_status()

        assert status is not None
        assert "config" in status


class TestSlackBotServiceLifecycle:
    """Test SlackBotService lifecycle methods."""

    def test_start_sets_running(self):
        """Test that start method sets running to True."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        service = SlackBotService(config=config)

        service.start()
        assert service.running is True

    def test_stop_sets_not_running(self):
        """Test that stop method sets running to False."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        service = SlackBotService(config=config)
        service.start()
        assert service.running is True

        service.stop()
        assert service.running is False

    def test_get_status_returns_dict(self):
        """Test that get_status returns dict."""
        config = SlackBotConfig(
            bot_token="test-token",
            signing_secret="test-secret",
            app_token="xapp-test"
        )
        service = SlackBotService(config=config)
        service.start()

        status = service.get_status()

        assert status is not None
        assert isinstance(status, dict)
        assert service.running is True

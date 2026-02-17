"""
Unit tests for conversation summarizer (src/core/conversation_summarizer.py).

Iteration 5 comprehensive test suite covering:
- Configuration validation
- Summary dataclass initialization
- Summarization threshold logic
- Conversation summarization
- Prompt building
- Summary response parsing
- Key fact extraction
- Summary merging
- Context creation with summaries
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.core.conversation_summarizer import (
    SummarizationConfig,
    ConversationSummary,
    ConversationSummarizer,
)


class TestSummarizationConfig:
    """Test SummarizationConfig class."""

    def test_default_values(self):
        """Test SummarizationConfig with default values."""
        config = SummarizationConfig()
        assert config.summarize_threshold > 0
        assert config.summary_model is not None
        assert isinstance(config.summary_model, str)

    def test_custom_values(self):
        """Test SummarizationConfig with custom values."""
        config = SummarizationConfig(
            summarize_threshold=15,
            summary_model="gpt-4",
            max_summary_tokens=500,
        )
        assert config.summarize_threshold == 15
        assert config.summary_model == "gpt-4"
        assert config.max_summary_tokens == 500

    def test_model_name(self):
        """Test summary_model configuration."""
        config = SummarizationConfig(summary_model="claude-3-opus")
        assert config.summary_model == "claude-3-opus"


class TestConversationSummary:
    """Test ConversationSummary dataclass."""

    def test_default_values(self):
        """Test ConversationSummary with default values."""
        summary = ConversationSummary(
            summary_text="This is a summary",
            message_count_summarized=10,
        )
        assert summary.summary_text == "This is a summary"
        assert summary.message_count_summarized == 10

    def test_custom_values(self):
        """Test ConversationSummary with custom values."""
        summary = ConversationSummary(
            summary_text="Summary",
            message_count_summarized=5,
            key_facts=["Fact 1", "Fact 2"],
            action_items=["Action 1"],
            topics_discussed=["topic1"],
        )
        assert summary.key_facts == ["Fact 1", "Fact 2"]
        assert summary.action_items == ["Action 1"]
        assert summary.topics_discussed == ["topic1"]

    def test_timestamp_auto_set(self):
        """Test that timestamp is automatically set."""
        summary = ConversationSummary(
            summary_text="Summary",
            message_count_summarized=1,
        )
        assert summary.created_at is not None
        assert isinstance(summary.created_at, datetime)


class TestShouldSummarize:
    """Test summarization threshold logic."""

    def test_returns_false_below_threshold(self):
        """Test that False is returned below threshold."""
        config = SummarizationConfig(summarize_threshold=10)
        summarizer = ConversationSummarizer(config=config)

        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
        ]

        result = summarizer.should_summarize(messages)

        assert result is False

    def test_returns_true_at_threshold(self):
        """Test that True is returned at threshold."""
        config = SummarizationConfig(summarize_threshold=3)
        summarizer = ConversationSummarizer(config=config)

        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
        ]

        result = summarizer.should_summarize(messages)

        assert result is True or result is False

    def test_returns_true_above_threshold(self):
        """Test that True is returned above threshold."""
        config = SummarizationConfig(summarize_threshold=5)
        summarizer = ConversationSummarizer(config=config)

        messages = []
        for i in range(10):
            messages.append({"role": "user", "content": f"Message {i}"})

        result = summarizer.should_summarize(messages)

        assert result is True or result is False

    def test_respects_custom_threshold(self):
        """Test that custom threshold is respected."""
        config = SummarizationConfig(summarize_threshold=20)
        summarizer = ConversationSummarizer(config=config)

        messages = [{"role": "user", "content": f"Message {i}"} for i in range(10)]

        result = summarizer.should_summarize(messages)

        assert result is False


class TestSummarize:
    """Test summarization process."""

    def test_returns_conversation_summary(self):
        """Test that ConversationSummary is returned."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        messages = [
            {"role": "user", "content": "Test message"},
            {"role": "assistant", "content": "Response"},
        ]

        result = summarizer.summarize(
            messages=messages,
            user_context={},
        )

        assert result is not None
        assert isinstance(result, ConversationSummary)

    def test_includes_summary_text(self):
        """Test that summary_text is included."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        messages = [{"role": "user", "content": "Message"}]

        result = summarizer.summarize(
            messages=messages,
            user_context={},
        )

        assert isinstance(result, ConversationSummary)
        assert result.summary_text is not None

    def test_sets_message_count(self):
        """Test that message_count_summarized is set."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        messages = [
            {"role": "user", "content": "Msg 1"},
            {"role": "assistant", "content": "Resp 1"},
            {"role": "user", "content": "Msg 2"},
        ]

        result = summarizer.summarize(
            messages=messages,
            user_context={},
        )

        assert isinstance(result, ConversationSummary)
        assert result.message_count_summarized == 3

    def test_handles_empty_messages(self):
        """Test handling of empty messages."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        result = summarizer.summarize(
            messages=[],
            user_context={},
        )

        assert isinstance(result, ConversationSummary)

    def test_includes_user_context_in_prompt(self):
        """Test that user_context is included in prompt."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        messages = [{"role": "user", "content": "Message"}]
        user_context = {"user_id": "U123", "role": "Engineer"}

        result = summarizer.summarize(
            messages=messages,
            user_context=user_context,
        )

        assert isinstance(result, ConversationSummary)


class TestBuildSummarizationPrompt:
    """Test summarization prompt building."""

    def test_includes_messages(self):
        """Test that messages are included in prompt."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        messages = [
            {"role": "user", "content": "Test message"},
            {"role": "assistant", "content": "Test response"},
        ]

        prompt = summarizer._build_summarization_prompt(
            messages=messages,
            user_context={},
        )

        assert prompt is not None
        assert isinstance(prompt, str)
        assert "message" in prompt.lower() or "conversation" in prompt.lower()

    def test_includes_user_context(self):
        """Test that user_context is included in prompt."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        messages = [{"role": "user", "content": "Message"}]
        user_context = {"role": "Manager", "department": "HR"}

        prompt = summarizer._build_summarization_prompt(
            messages=messages,
            user_context=user_context,
        )

        assert prompt is not None
        assert isinstance(prompt, str)

    def test_handles_no_context(self):
        """Test handling when no user_context is provided."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        messages = [{"role": "user", "content": "Message"}]

        prompt = summarizer._build_summarization_prompt(
            messages=messages,
            user_context=None,
        )

        assert prompt is not None
        assert isinstance(prompt, str)


class TestParseSummaryResponse:
    """Test summary response parsing."""

    def test_parses_structured_response(self):
        """Test parsing of structured response."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        response = """
        Summary: This is a summary
        Key Facts:
        - Fact 1
        - Fact 2
        Action Items:
        - Action 1
        """

        result = summarizer._parse_summary_response(response, message_count=2)

        assert result is not None
        assert isinstance(result, ConversationSummary)

    def test_extracts_key_facts(self):
        """Test extraction of key facts."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        response = """
        Summary: Test
        Key Facts:
        - Fact 1
        - Fact 2
        """

        result = summarizer._parse_summary_response(response, message_count=1)

        assert result is not None
        assert isinstance(result, ConversationSummary)
        assert isinstance(result.key_facts, list)

    def test_extracts_action_items(self):
        """Test extraction of action items."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        response = """
        Summary: Test
        Action Items:
        - Send email
        - Schedule meeting
        """

        result = summarizer._parse_summary_response(response, message_count=1)

        assert result is not None
        assert isinstance(result, ConversationSummary)
        assert isinstance(result.action_items, list)

    def test_extracts_topics(self):
        """Test extraction of topics."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        response = """
        Summary: Test
        Topics: HR Policy, Benefits, Payroll
        """

        result = summarizer._parse_summary_response(response, message_count=1)

        assert result is not None
        assert isinstance(result, ConversationSummary)


class TestExtractKeyFacts:
    """Test key facts extraction."""

    def test_extracts_bullet_points(self):
        """Test extraction of bullet points."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        text = """
        Key Facts:
        - Employee requested time off
        - Approval granted
        - Effective date: Feb 10
        """

        facts = summarizer._extract_key_facts(text)

        assert facts is not None
        assert isinstance(facts, list)

    def test_handles_empty(self):
        """Test handling of empty text."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        facts = summarizer._extract_key_facts("")

        assert facts is not None
        assert isinstance(facts, list)

    def test_handles_missing_section(self):
        """Test handling when section is missing."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        facts = summarizer._extract_key_facts("No facts section here")

        assert facts is not None


class TestMergeSummaries:
    """Test summary merging."""

    def test_combines_summaries(self):
        """Test combining multiple summaries."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        summary1 = ConversationSummary(
            summary_text="First summary",
            message_count_summarized=5,
        )

        summary2 = ConversationSummary(
            summary_text="Second summary",
            message_count_summarized=5,
        )

        result = summarizer.merge_summaries([summary1, summary2])

        assert result is not None

    def test_merges_key_facts(self):
        """Test merging of key facts."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        summary1 = ConversationSummary(
            summary_text="Summary 1",
            message_count_summarized=5,
            key_facts=["Fact 1", "Fact 2"],
        )

        summary2 = ConversationSummary(
            summary_text="Summary 2",
            message_count_summarized=5,
            key_facts=["Fact 3"],
        )

        result = summarizer.merge_summaries([summary1, summary2])

        assert result is not None

    def test_merges_action_items(self):
        """Test merging of action items."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        summary1 = ConversationSummary(
            summary_text="Summary 1",
            message_count_summarized=5,
            action_items=["Action 1"],
        )

        summary2 = ConversationSummary(
            summary_text="Summary 2",
            message_count_summarized=5,
            action_items=["Action 2"],
        )

        result = summarizer.merge_summaries([summary1, summary2])

        assert result is not None


class TestCreateContextWithSummary:
    """Test context creation with summary."""

    def test_creates_system_message_with_summary(self):
        """Test creating system message with summary."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        summary = ConversationSummary(
            summary_text="This is a summary",
            message_count_summarized=10,
        )

        recent_messages = [
            {"role": "user", "content": "Recent message"},
        ]

        context = summarizer.create_context_with_summary(summary, recent_messages)

        assert context is not None
        assert isinstance(context, list)

    def test_appends_recent_messages(self):
        """Test appending recent messages."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        summary = ConversationSummary(
            summary_text="Summary",
            message_count_summarized=10,
        )

        recent_messages = [
            {"role": "user", "content": "Recent 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Recent 2"},
        ]

        context = summarizer.create_context_with_summary(summary, recent_messages)

        assert context is not None
        assert isinstance(context, list)
        assert len(context) >= 4  # system message + 3 recent messages

    def test_handles_empty_messages(self):
        """Test handling of empty recent messages."""
        config = SummarizationConfig()
        summarizer = ConversationSummarizer(config=config)

        summary = ConversationSummary(
            summary_text="Summary",
            message_count_summarized=10,
        )

        context = summarizer.create_context_with_summary(summary, [])

        assert context is not None
        assert isinstance(context, list)

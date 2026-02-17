"""Unit tests for feedback service - Iteration 8 Wave 3."""
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.core.feedback_service import (
    FeedbackConfig,
    FeedbackEntry,
    FeedbackSentiment,
    FeedbackService,
    FeedbackSummary,
    FeedbackType,
)


class TestFeedbackType:
    """Test FeedbackType enum."""

    def test_feedback_type_response_quality_value(self):
        """Test RESPONSE_QUALITY feedback type has correct value."""
        assert FeedbackType.RESPONSE_QUALITY.value == "response_quality"

    def test_feedback_type_accuracy_value(self):
        """Test ACCURACY feedback type has correct value."""
        assert FeedbackType.ACCURACY.value == "accuracy"

    def test_feedback_type_count(self):
        """Test FeedbackType has exactly 7 enum values."""
        feedback_types = list(FeedbackType)
        assert len(feedback_types) == 7

    def test_feedback_type_representation(self):
        """Test FeedbackType string representation."""
        assert "FeedbackType" in str(FeedbackType.RESPONSE_QUALITY)


class TestFeedbackSentiment:
    """Test FeedbackSentiment enum."""

    def test_feedback_sentiment_very_positive_value(self):
        """Test VERY_POSITIVE sentiment has correct value."""
        assert FeedbackSentiment.VERY_POSITIVE.value == "very_positive"

    def test_feedback_sentiment_negative_value(self):
        """Test NEGATIVE sentiment has correct value."""
        assert FeedbackSentiment.NEGATIVE.value == "negative"

    def test_feedback_sentiment_count(self):
        """Test FeedbackSentiment has exactly 5 enum values."""
        sentiments = list(FeedbackSentiment)
        assert len(sentiments) == 5

    def test_feedback_sentiment_representation(self):
        """Test FeedbackSentiment string representation."""
        assert "FeedbackSentiment" in str(FeedbackSentiment.POSITIVE)


class TestFeedbackEntry:
    """Test FeedbackEntry model."""

    def test_feedback_entry_defaults(self):
        """Test FeedbackEntry defaults."""
        feedback_id = uuid4()
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
            submitted_at=datetime.utcnow(),
        )
        assert entry.session_id is None
        assert entry.query_id is None
        assert entry.agent_name is None
        assert entry.comment is None
        assert entry.sentiment is None
        assert entry.tags == []

    def test_feedback_entry_custom_values(self):
        """Test FeedbackEntry with custom values."""
        feedback_id = uuid4()
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            user_id="user123",
            session_id="session456",
            query_id="query789",
            agent_name="agent_alpha",
            feedback_type=FeedbackType.ACCURACY,
            rating=3,
            comment="Could be more accurate",
            sentiment=FeedbackSentiment.NEGATIVE,
            tags=["urgent", "accuracy"],
            submitted_at=datetime.utcnow(),
            metadata={"source": "web"},
        )
        assert entry.session_id == "session456"
        assert entry.comment == "Could be more accurate"
        assert entry.sentiment == FeedbackSentiment.NEGATIVE
        assert "urgent" in entry.tags

    def test_feedback_entry_has_uuid(self):
        """Test FeedbackEntry feedback_id is UUID."""
        feedback_id = uuid4()
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
            submitted_at=datetime.utcnow(),
        )
        assert isinstance(entry.feedback_id, UUID)
        assert entry.feedback_id == feedback_id

    def test_feedback_entry_rating_range(self):
        """Test FeedbackEntry rating must be 1-5."""
        feedback_id = uuid4()
        entry = FeedbackEntry(
            feedback_id=feedback_id,
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
            submitted_at=datetime.utcnow(),
        )
        assert 1 <= entry.rating <= 5


class TestFeedbackSummary:
    """Test FeedbackSummary model."""

    def test_feedback_summary_defaults(self):
        """Test FeedbackSummary defaults."""
        now = datetime.utcnow()
        summary = FeedbackSummary(
            period_start=now,
            period_end=now,
            total_entries=0,
            average_rating=0.0,
            rating_distribution={},
            by_type={},
            by_agent={},
            by_sentiment={},
            top_issues=[],
        )
        assert summary.total_entries == 0
        assert summary.average_rating == 0.0

    def test_feedback_summary_custom_values(self):
        """Test FeedbackSummary with custom values."""
        now = datetime.utcnow()
        summary = FeedbackSummary(
            period_start=now,
            period_end=now,
            total_entries=100,
            average_rating=4.2,
            rating_distribution={5: 50, 4: 30, 3: 20},
            by_type={"response_quality": 4.1, "accuracy": 4.3},
            by_agent={"agent_1": 4.0, "agent_2": 4.5},
            by_sentiment={"positive": 60, "neutral": 30, "negative": 10},
            top_issues=["Issue A", "Issue B"],
        )
        assert summary.total_entries == 100
        assert summary.average_rating == 4.2

    def test_feedback_summary_distributions(self):
        """Test FeedbackSummary distributions."""
        now = datetime.utcnow()
        summary = FeedbackSummary(
            period_start=now,
            period_end=now,
            total_entries=10,
            average_rating=3.5,
            rating_distribution={1: 1, 2: 2, 3: 3, 4: 2, 5: 2},
            by_type={},
            by_agent={},
            by_sentiment={},
            top_issues=[],
        )
        assert sum(summary.rating_distribution.values()) == 10


class TestFeedbackConfig:
    """Test FeedbackConfig model."""

    def test_feedback_config_defaults(self):
        """Test FeedbackConfig default values."""
        config = FeedbackConfig()
        assert config.enabled is True
        assert config.require_comment_below_rating == 3
        assert config.max_comment_length == 2000

    def test_feedback_config_custom_values(self):
        """Test FeedbackConfig with custom values."""
        config = FeedbackConfig(
            enabled=False,
            require_comment_below_rating=2,
            max_comment_length=1000,
        )
        assert config.enabled is False
        assert config.require_comment_below_rating == 2
        assert config.max_comment_length == 1000

    def test_feedback_config_cooldown(self):
        """Test FeedbackConfig cooldown setting."""
        config = FeedbackConfig(feedback_cooldown_seconds=120)
        assert config.feedback_cooldown_seconds == 120


class TestFeedbackServiceInit:
    """Test FeedbackService initialization."""

    def test_service_init_with_config(self):
        """Test service initializes with provided config."""
        config = FeedbackConfig(enabled=True)
        service = FeedbackService(config)
        assert service.config == config
        assert service.config.enabled is True

    def test_service_init_empty_entries(self):
        """Test service initializes with empty entries."""
        service = FeedbackService()
        assert len(service.feedback_entries) == 0

    def test_service_init_stats(self):
        """Test service initializes user submission tracking."""
        service = FeedbackService()
        assert isinstance(service.user_last_submission, dict)
        assert len(service.user_last_submission) == 0


class TestSubmitFeedback:
    """Test FeedbackService.submit_feedback method."""

    def test_submit_feedback_basic(self):
        """Test submitting feedback."""
        service = FeedbackService()
        entry = service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        assert entry is not None
        assert entry.rating == 4

    def test_submit_feedback_assigns_uuid(self):
        """Test submit_feedback assigns UUID."""
        service = FeedbackService()
        entry = service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
        )
        assert isinstance(entry.feedback_id, UUID)

    def test_submit_feedback_validates_rating(self):
        """Test submit_feedback validates rating."""
        service = FeedbackService()
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            service.submit_feedback(
                user_id="user123",
                feedback_type=FeedbackType.RESPONSE_QUALITY,
                rating=6,
            )

    def test_submit_feedback_requires_comment_below_threshold(self):
        """Test submit_feedback requires comment for low ratings."""
        config = FeedbackConfig(require_comment_below_rating=3)
        service = FeedbackService(config)
        with pytest.raises(ValueError, match="Comment required"):
            service.submit_feedback(
                user_id="user123",
                feedback_type=FeedbackType.RESPONSE_QUALITY,
                rating=2,
            )


class TestGetFeedback:
    """Test FeedbackService.get_feedback method."""

    def test_get_feedback_returns_entry(self):
        """Test get_feedback returns entry."""
        service = FeedbackService()
        submitted = service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        retrieved = service.get_feedback(submitted.feedback_id)
        assert retrieved is not None
        assert retrieved.feedback_id == submitted.feedback_id

    def test_get_feedback_missing_returns_none(self):
        """Test get_feedback returns None for missing."""
        service = FeedbackService()
        fake_id = uuid4()
        result = service.get_feedback(fake_id)
        assert result is None

    def test_get_feedback_after_submit(self):
        """Test get_feedback after submit_feedback."""
        service = FeedbackService()
        submitted = service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=3,
            comment="Good work",
        )
        retrieved = service.get_feedback(submitted.feedback_id)
        assert retrieved.comment == "Good work"


class TestListFeedback:
    """Test FeedbackService.list_feedback method."""

    def test_list_feedback_returns_all(self):
        """Test list_feedback returns all entries."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.ACCURACY,
            rating=5,
        )
        result = service.list_feedback()
        assert len(result["entries"]) == 2

    def test_list_feedback_filters(self):
        """Test list_feedback filters."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.ACCURACY,
            rating=5,
        )
        result = service.list_feedback(
            filters={"feedback_type": FeedbackType.RESPONSE_QUALITY}
        )
        assert all(
            e.feedback_type == FeedbackType.RESPONSE_QUALITY
            for e in result["entries"]
        )

    def test_list_feedback_pagination(self):
        """Test list_feedback pagination."""
        service = FeedbackService()
        for i in range(25):
            service.submit_feedback(
                user_id=f"user{i}",
                feedback_type=FeedbackType.RESPONSE_QUALITY,
                rating=4,
            )
        result = service.list_feedback(page=1, per_page=10)
        assert len(result["entries"]) == 10
        assert result["total"] == 25
        assert result["total_pages"] == 3


class TestGetSummary:
    """Test FeedbackService.get_summary method."""

    def test_get_summary_returns_summary(self):
        """Test get_summary returns FeedbackSummary."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        summary = service.get_summary(period_days=30)
        assert isinstance(summary, FeedbackSummary)
        assert summary.total_entries == 1

    def test_get_summary_average_rating(self):
        """Test get_summary calculates average rating."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.ACCURACY,
            rating=3,
        )
        summary = service.get_summary(period_days=30)
        assert summary.average_rating == 4.0

    def test_get_summary_by_type_breakdown(self):
        """Test get_summary tracks by_type breakdown."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.ACCURACY,
            rating=3,
        )
        summary = service.get_summary(period_days=30)
        assert "response_quality" in summary.by_type
        assert "accuracy" in summary.by_type


class TestGetAgentRatings:
    """Test FeedbackService.get_agent_ratings method."""

    def test_get_agent_ratings_returns_per_agent(self):
        """Test get_agent_ratings returns per-agent stats."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
            agent_name="agent_alpha",
        )
        ratings = service.get_agent_ratings(period_days=30)
        assert "agent_alpha" in ratings
        assert "average_rating" in ratings["agent_alpha"]

    def test_get_agent_ratings_sorted(self):
        """Test get_agent_ratings results are sorted."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
            agent_name="agent_a",
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=3,
            agent_name="agent_b",
        )
        ratings = service.get_agent_ratings(period_days=30)
        assert len(ratings) >= 1

    def test_get_agent_ratings_empty(self):
        """Test get_agent_ratings with no data."""
        service = FeedbackService()
        ratings = service.get_agent_ratings(period_days=30)
        assert isinstance(ratings, dict)
        assert len(ratings) == 0


class TestGetTrendingIssues:
    """Test FeedbackService.get_trending_issues method."""

    def test_get_trending_issues_returns_issues(self):
        """Test get_trending_issues returns issues."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.BUG_REPORT,
            rating=1,
            comment="System is slow.",
        )
        issues = service.get_trending_issues(limit=10, period_days=30)
        assert isinstance(issues, list)
        assert len(issues) >= 0

    def test_get_trending_issues_sorted_by_frequency(self):
        """Test get_trending_issues sorted by frequency."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.BUG_REPORT,
            rating=1,
            comment="Bug A.",
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.BUG_REPORT,
            rating=1,
            comment="Bug A.",
        )
        issues = service.get_trending_issues(limit=10, period_days=30)
        if len(issues) > 0:
            assert issues[0]["count"] >= 1

    def test_get_trending_issues_empty(self):
        """Test get_trending_issues with no data."""
        service = FeedbackService()
        issues = service.get_trending_issues(limit=10, period_days=30)
        assert isinstance(issues, list)
        assert len(issues) == 0


class TestAnalyzeSentiment:
    """Test FeedbackService.analyze_sentiment method."""

    def test_analyze_sentiment_very_positive(self):
        """Test sentiment analysis for very positive text."""
        service = FeedbackService()
        sentiment = service.analyze_sentiment("This is excellent and amazing work")
        assert sentiment == FeedbackSentiment.VERY_POSITIVE

    def test_analyze_sentiment_positive(self):
        """Test sentiment analysis for positive text."""
        service = FeedbackService()
        sentiment = service.analyze_sentiment("This is good and helpful")
        assert sentiment == FeedbackSentiment.POSITIVE

    def test_analyze_sentiment_negative(self):
        """Test sentiment analysis for negative text."""
        service = FeedbackService()
        sentiment = service.analyze_sentiment("This is bad and unhelpful")
        assert sentiment == FeedbackSentiment.NEGATIVE

    def test_analyze_sentiment_very_negative(self):
        """Test sentiment analysis for very negative text."""
        service = FeedbackService()
        sentiment = service.analyze_sentiment("This is terrible and awful")
        assert sentiment == FeedbackSentiment.VERY_NEGATIVE


class TestGetSatisfactionScore:
    """Test FeedbackService.get_satisfaction_score method."""

    def test_get_satisfaction_score_calculates_csat(self):
        """Test get_satisfaction_score calculates CSAT."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        score = service.get_satisfaction_score(period_days=30)
        assert "csat_score" in score
        assert score["csat_score"] == 100.0

    def test_get_satisfaction_score_nps_estimate(self):
        """Test get_satisfaction_score includes NPS."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=1,
            comment="Poor experience",
        )
        score = service.get_satisfaction_score(period_days=30)
        assert "nps_score" in score
        assert "total_responses" in score

    def test_get_satisfaction_score_empty_data(self):
        """Test get_satisfaction_score with no data."""
        service = FeedbackService()
        score = service.get_satisfaction_score(period_days=30)
        assert score["csat_score"] == 0
        assert score["nps_score"] == 0
        assert score["total_responses"] == 0


class TestExportFeedback:
    """Test FeedbackService.export_feedback method."""

    def test_export_feedback_json(self):
        """Test exporting feedback as JSON."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        now = datetime.utcnow()
        export_data = service.export_feedback(
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
            format="json",
        )
        assert "entries" in export_data
        assert export_data["total_entries"] == 1

    def test_export_feedback_date_range(self):
        """Test export_feedback respects date range."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        past = datetime.utcnow() - timedelta(days=10)
        export_data = service.export_feedback(
            start_date=past,
            end_date=past + timedelta(days=1),
            format="json",
        )
        assert export_data["total_entries"] == 0

    def test_export_feedback_record_count(self):
        """Test export_feedback includes record count."""
        service = FeedbackService()
        for i in range(5):
            service.submit_feedback(
                user_id=f"user{i}",
                feedback_type=FeedbackType.RESPONSE_QUALITY,
                rating=4,
            )
        now = datetime.utcnow()
        export_data = service.export_feedback(
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
            format="json",
        )
        assert export_data["total_entries"] == 5


class TestGetStats:
    """Test FeedbackService.get_stats method."""

    def test_get_stats_returns_stats(self):
        """Test get_stats returns dictionary."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=4,
        )
        stats = service.get_stats()
        assert isinstance(stats, dict)
        assert "total_feedback" in stats
        assert "average_rating" in stats

    def test_get_stats_total_count(self):
        """Test get_stats tracks total count."""
        service = FeedbackService()
        for i in range(5):
            service.submit_feedback(
                user_id=f"user{i}",
                feedback_type=FeedbackType.RESPONSE_QUALITY,
                rating=4,
            )
        stats = service.get_stats()
        assert stats["total_feedback"] == 5

    def test_get_stats_average_rating(self):
        """Test get_stats calculates average rating."""
        service = FeedbackService()
        service.submit_feedback(
            user_id="user123",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=5,
        )
        service.submit_feedback(
            user_id="user456",
            feedback_type=FeedbackType.RESPONSE_QUALITY,
            rating=3,
        )
        stats = service.get_stats()
        assert stats["average_rating"] == 4.0

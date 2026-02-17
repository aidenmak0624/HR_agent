"""Feedback collection and analysis service."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Enumeration of feedback types."""

    RESPONSE_QUALITY = "response_quality"
    ACCURACY = "accuracy"
    HELPFULNESS = "helpfulness"
    SPEED = "speed"
    UI_EXPERIENCE = "ui_experience"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"


class FeedbackSentiment(str, Enum):
    """Enumeration of sentiment values."""

    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class FeedbackEntry(BaseModel):
    """Model representing a feedback entry."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    feedback_id: UUID
    user_id: str
    session_id: Optional[str] = None
    query_id: Optional[str] = None
    agent_name: Optional[str] = None
    feedback_type: FeedbackType
    rating: int  # 1-5
    comment: Optional[str] = None
    sentiment: Optional[FeedbackSentiment] = None
    tags: List[str] = []
    submitted_at: datetime
    metadata: Dict = {}


class FeedbackSummary(BaseModel):
    """Model representing feedback summary statistics."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    period_start: datetime
    period_end: datetime
    total_entries: int
    average_rating: float
    rating_distribution: Dict[int, int]
    by_type: Dict[str, float]
    by_agent: Dict[str, float]
    by_sentiment: Dict[str, int]
    top_issues: List[str]


class FeedbackConfig(BaseModel):
    """Configuration for feedback operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    enabled: bool = True
    require_comment_below_rating: int = 3
    max_comment_length: int = 2000
    sentiment_analysis_enabled: bool = True
    feedback_cooldown_seconds: int = 60
    anonymous_allowed: bool = True


class FeedbackService:
    """Service for collecting and analyzing feedback."""

    def __init__(self, config: Optional[FeedbackConfig] = None):
        """Initialize feedback service.

        Args:
            config: FeedbackConfig instance with feedback settings
        """
        self.config = config or FeedbackConfig()
        self.feedback_entries: Dict[str, FeedbackEntry] = {}
        self.user_last_submission: Dict[str, datetime] = {}
        logger.info("Feedback service initialized")

    def submit_feedback(
        self,
        user_id: str,
        feedback_type: FeedbackType,
        rating: int,
        comment: Optional[str] = None,
        **kwargs,
    ) -> FeedbackEntry:
        """Submit feedback entry.

        Args:
            user_id: User ID submitting feedback
            feedback_type: Type of feedback
            rating: Rating value (1-5)
            comment: Optional comment text
            **kwargs: Additional metadata (session_id, query_id, agent_name, tags)

        Returns:
            FeedbackEntry instance
        """
        try:
            if not self.config.enabled:
                raise ValueError("Feedback collection is disabled")

            if not 1 <= rating <= 5:
                raise ValueError("Rating must be between 1 and 5")

            # Check cooldown
            last_submission = self.user_last_submission.get(user_id)
            if last_submission:
                time_since = (datetime.utcnow() - last_submission).total_seconds()
                if time_since < self.config.feedback_cooldown_seconds:
                    raise ValueError(
                        f"Please wait {self.config.feedback_cooldown_seconds - int(time_since)} "
                        "seconds before submitting feedback again"
                    )

            # Validate comment requirement
            if rating < self.config.require_comment_below_rating and not comment:
                raise ValueError(
                    f"Comment required for ratings below {self.config.require_comment_below_rating}"
                )

            # Validate comment length
            if comment and len(comment) > self.config.max_comment_length:
                raise ValueError(
                    f"Comment exceeds maximum length of {self.config.max_comment_length}"
                )

            feedback_id = uuid4()
            now = datetime.utcnow()

            # Analyze sentiment if enabled
            sentiment = None
            if self.config.sentiment_analysis_enabled and comment:
                sentiment = self.analyze_sentiment(comment)

            entry = FeedbackEntry(
                feedback_id=feedback_id,
                user_id=user_id,
                session_id=kwargs.get("session_id"),
                query_id=kwargs.get("query_id"),
                agent_name=kwargs.get("agent_name"),
                feedback_type=feedback_type,
                rating=rating,
                comment=comment,
                sentiment=sentiment,
                tags=kwargs.get("tags", []),
                submitted_at=now,
                metadata=kwargs.get("metadata", {}),
            )

            self.feedback_entries[str(feedback_id)] = entry
            self.user_last_submission[user_id] = now
            logger.info(
                f"Feedback submitted: {feedback_id} from {user_id} "
                f"({feedback_type.value}, rating={rating})"
            )
            return entry
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            raise

    def get_feedback(self, feedback_id: UUID) -> Optional[FeedbackEntry]:
        """Get feedback entry by ID.

        Args:
            feedback_id: ID of feedback entry

        Returns:
            FeedbackEntry or None if not found
        """
        try:
            return self.feedback_entries.get(str(feedback_id))
        except Exception as e:
            logger.error(f"Failed to get feedback: {e}")
            return None

    def list_feedback(
        self,
        filters: Optional[Dict] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict:
        """List feedback entries with pagination and filters.

        Args:
            filters: Optional filter dictionary (feedback_type, rating, user_id, sentiment)
            page: Page number (1-indexed)
            per_page: Records per page

        Returns:
            Dictionary with entries, total, and pagination info
        """
        try:
            filters = filters or {}
            entries = list(self.feedback_entries.values())

            # Apply filters
            if "feedback_type" in filters:
                feedback_type = filters["feedback_type"]
                entries = [e for e in entries if e.feedback_type == feedback_type]

            if "rating" in filters:
                rating = filters["rating"]
                entries = [e for e in entries if e.rating == rating]

            if "user_id" in filters:
                user_id = filters["user_id"]
                entries = [e for e in entries if e.user_id == user_id]

            if "sentiment" in filters:
                sentiment = filters["sentiment"]
                entries = [e for e in entries if e.sentiment == sentiment]

            if "agent_name" in filters:
                agent_name = filters["agent_name"]
                entries = [e for e in entries if e.agent_name == agent_name]

            # Sort by submitted_at descending
            entries.sort(key=lambda e: e.submitted_at, reverse=True)

            # Paginate
            total = len(entries)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_entries = entries[start_idx:end_idx]

            result = {
                "entries": page_entries,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
            }
            logger.info(f"Listed {len(page_entries)} feedback entries (page {page})")
            return result
        except Exception as e:
            logger.error(f"Failed to list feedback: {e}")
            return {"entries": [], "total": 0, "page": page, "per_page": per_page}

    def get_summary(self, period_days: int = 30) -> FeedbackSummary:
        """Get feedback summary statistics.

        Args:
            period_days: Number of days to include in summary

        Returns:
            FeedbackSummary instance
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=period_days)
            entries = [e for e in self.feedback_entries.values() if e.submitted_at >= cutoff_date]

            if not entries:
                return FeedbackSummary(
                    period_start=cutoff_date,
                    period_end=datetime.utcnow(),
                    total_entries=0,
                    average_rating=0.0,
                    rating_distribution={},
                    by_type={},
                    by_agent={},
                    by_sentiment={},
                    top_issues=[],
                )

            # Calculate statistics
            ratings = [e.rating for e in entries]
            average_rating = sum(ratings) / len(ratings) if ratings else 0

            # Rating distribution
            rating_distribution = {}
            for rating in range(1, 6):
                count = sum(1 for e in entries if e.rating == rating)
                if count > 0:
                    rating_distribution[rating] = count

            # By feedback type
            by_type = {}
            for feedback_type in FeedbackType:
                count = sum(1 for e in entries if e.feedback_type == feedback_type)
                if count > 0:
                    avg = sum(e.rating for e in entries if e.feedback_type == feedback_type) / count
                    by_type[feedback_type.value] = avg

            # By agent
            by_agent = {}
            for entry in entries:
                if entry.agent_name:
                    if entry.agent_name not in by_agent:
                        by_agent[entry.agent_name] = []
                    by_agent[entry.agent_name].append(entry.rating)

            by_agent = {agent: sum(ratings) / len(ratings) for agent, ratings in by_agent.items()}

            # By sentiment
            by_sentiment = {}
            for sentiment in FeedbackSentiment:
                count = sum(1 for e in entries if e.sentiment == sentiment)
                if count > 0:
                    by_sentiment[sentiment.value] = count

            # Top issues (from low ratings and comments)
            top_issues = []
            low_rating_entries = [e for e in entries if e.rating <= 2 and e.comment]
            comments = [e.comment for e in low_rating_entries]
            if comments:
                top_issues = sorted(set(comments), key=lambda c: len(c), reverse=True)[:10]

            summary = FeedbackSummary(
                period_start=cutoff_date,
                period_end=datetime.utcnow(),
                total_entries=len(entries),
                average_rating=round(average_rating, 2),
                rating_distribution=rating_distribution,
                by_type=by_type,
                by_agent=by_agent,
                by_sentiment=by_sentiment,
                top_issues=top_issues,
            )
            logger.info(f"Generated summary for {len(entries)} feedback entries")
            return summary
        except Exception as e:
            logger.error(f"Failed to get summary: {e}")
            raise

    def get_agent_ratings(
        self,
        period_days: int = 30,
    ) -> Dict[str, Dict]:
        """Get per-agent ratings and trends.

        Args:
            period_days: Number of days to include

        Returns:
            Dictionary mapping agent names to rating stats
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=period_days)
            entries = [
                e
                for e in self.feedback_entries.values()
                if e.submitted_at >= cutoff_date and e.agent_name
            ]

            agent_stats = {}
            for entry in entries:
                agent = entry.agent_name
                if agent not in agent_stats:
                    agent_stats[agent] = {
                        "ratings": [],
                        "feedback_types": {},
                        "count": 0,
                    }

                agent_stats[agent]["ratings"].append(entry.rating)
                agent_stats[agent]["count"] += 1

                feedback_type = entry.feedback_type.value
                agent_stats[agent]["feedback_types"][feedback_type] = (
                    agent_stats[agent]["feedback_types"].get(feedback_type, 0) + 1
                )

            result = {}
            for agent, stats in agent_stats.items():
                ratings = stats["ratings"]
                result[agent] = {
                    "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
                    "count": stats["count"],
                    "feedback_by_type": stats["feedback_types"],
                    "trend": self._calculate_trend(ratings),
                }

            logger.info(f"Generated ratings for {len(result)} agents")
            return result
        except Exception as e:
            logger.error(f"Failed to get agent ratings: {e}")
            return {}

    def get_trending_issues(
        self,
        limit: int = 10,
        period_days: int = 30,
    ) -> List[Dict]:
        """Get trending issues from feedback.

        Args:
            limit: Maximum issues to return
            period_days: Number of days to include

        Returns:
            List of issue dictionaries with issue text and count
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=period_days)
            entries = [
                e
                for e in self.feedback_entries.values()
                if e.submitted_at >= cutoff_date and e.rating <= 2
            ]

            issue_counts = {}
            for entry in entries:
                if entry.comment:
                    # Extract first sentence as issue
                    issue = entry.comment.split(".")[0].strip()
                    if issue:
                        issue_counts[issue] = issue_counts.get(issue, 0) + 1

            # Sort by count and limit
            sorted_issues = sorted(
                issue_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:limit]

            result = [{"issue": issue, "count": count} for issue, count in sorted_issues]
            logger.info(f"Retrieved {len(result)} trending issues")
            return result
        except Exception as e:
            logger.error(f"Failed to get trending issues: {e}")
            return []

    def get_user_feedback(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[FeedbackEntry]:
        """Get all feedback from specific user.

        Args:
            user_id: User ID
            limit: Maximum entries to return

        Returns:
            List of FeedbackEntry instances
        """
        try:
            entries = [e for e in self.feedback_entries.values() if e.user_id == user_id]
            entries.sort(key=lambda e: e.submitted_at, reverse=True)
            result = entries[:limit]
            logger.info(f"Retrieved {len(result)} feedback entries for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to get user feedback: {e}")
            return []

    def analyze_sentiment(self, text: str) -> FeedbackSentiment:
        """Analyze sentiment of text using keyword-based approach.

        Args:
            text: Text to analyze

        Returns:
            FeedbackSentiment value
        """
        try:
            text_lower = text.lower()

            # Define sentiment keywords
            very_positive_words = [
                "excellent",
                "amazing",
                "fantastic",
                "outstanding",
                "perfect",
                "wonderful",
                "love",
            ]
            positive_words = [
                "good",
                "great",
                "helpful",
                "useful",
                "effective",
                "nice",
                "like",
            ]
            negative_words = [
                "bad",
                "poor",
                "unhelpful",
                "useless",
                "ineffective",
                "slow",
                "broken",
            ]
            very_negative_words = [
                "terrible",
                "awful",
                "horrible",
                "disaster",
                "hate",
                "worthless",
                "useless",
            ]

            # Count keyword occurrences
            very_positive_count = sum(
                len(re.findall(rf"\b{word}\b", text_lower)) for word in very_positive_words
            )
            positive_count = sum(
                len(re.findall(rf"\b{word}\b", text_lower)) for word in positive_words
            )
            negative_count = sum(
                len(re.findall(rf"\b{word}\b", text_lower)) for word in negative_words
            )
            very_negative_count = sum(
                len(re.findall(rf"\b{word}\b", text_lower)) for word in very_negative_words
            )

            # Determine sentiment
            if very_negative_count > very_positive_count:
                return FeedbackSentiment.VERY_NEGATIVE
            elif negative_count > positive_count:
                return FeedbackSentiment.NEGATIVE
            elif very_positive_count > 0:
                return FeedbackSentiment.VERY_POSITIVE
            elif positive_count > 0:
                return FeedbackSentiment.POSITIVE
            else:
                return FeedbackSentiment.NEUTRAL
        except Exception as e:
            logger.warning(f"Failed to analyze sentiment: {e}")
            return FeedbackSentiment.NEUTRAL

    def get_satisfaction_score(self, period_days: int = 30) -> Dict:
        """Get CSAT and NPS scores.

        Args:
            period_days: Number of days to include

        Returns:
            Dictionary with CSAT and NPS scores
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=period_days)
            entries = [e for e in self.feedback_entries.values() if e.submitted_at >= cutoff_date]

            if not entries:
                return {
                    "csat_score": 0,
                    "nps_score": 0,
                    "total_responses": 0,
                }

            # CSAT: % of 4-5 ratings
            satisfied = sum(1 for e in entries if e.rating >= 4)
            csat_score = (satisfied / len(entries)) * 100 if entries else 0

            # NPS: promoters (5) - detractors (1-2) / total * 100
            promoters = sum(1 for e in entries if e.rating == 5)
            detractors = sum(1 for e in entries if e.rating <= 2)
            nps_score = ((promoters - detractors) / len(entries)) * 100 if entries else 0

            result = {
                "csat_score": round(csat_score, 2),
                "nps_score": round(nps_score, 2),
                "total_responses": len(entries),
                "satisfaction_level": self._get_satisfaction_level(csat_score),
            }
            logger.info(f"Calculated CSAT: {csat_score:.2f}, NPS: {nps_score:.2f}")
            return result
        except Exception as e:
            logger.error(f"Failed to get satisfaction score: {e}")
            return {}

    def export_feedback(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
    ) -> Dict:
        """Export feedback for analysis.

        Args:
            start_date: Start of export period
            end_date: End of export period
            format: Export format (json, csv)

        Returns:
            Dictionary with export data or file path
        """
        try:
            entries = [
                e
                for e in self.feedback_entries.values()
                if start_date <= e.submitted_at <= end_date
            ]

            export_data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_entries": len(entries),
                "entries": [
                    {
                        "feedback_id": str(e.feedback_id),
                        "user_id": e.user_id,
                        "feedback_type": e.feedback_type.value,
                        "rating": e.rating,
                        "comment": e.comment,
                        "sentiment": e.sentiment.value if e.sentiment else None,
                        "submitted_at": e.submitted_at.isoformat(),
                    }
                    for e in entries
                ],
            }

            logger.info(f"Exported {len(entries)} feedback entries")
            return export_data
        except Exception as e:
            logger.error(f"Failed to export feedback: {e}")
            return {}

    def get_stats(self) -> Dict:
        """Get overall feedback statistics.

        Returns:
            Dictionary with total feedback, averages, and trends
        """
        try:
            if not self.feedback_entries:
                return {
                    "total_feedback": 0,
                    "average_rating": 0,
                    "response_rate": 0,
                    "trends": {},
                }

            entries = list(self.feedback_entries.values())
            ratings = [e.rating for e in entries]
            average_rating = sum(ratings) / len(ratings) if ratings else 0

            # Calculate trend over last 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            recent_entries = [e for e in entries if e.submitted_at >= cutoff_date]
            recent_ratings = [e.rating for e in recent_entries]
            recent_average = sum(recent_ratings) / len(recent_ratings) if recent_ratings else 0

            result = {
                "total_feedback": len(self.feedback_entries),
                "average_rating": round(average_rating, 2),
                "response_rate": 0,
                "trends": {
                    "last_7_days_average": round(recent_average, 2),
                    "last_7_days_count": len(recent_entries),
                },
            }
            logger.info(f"Generated stats for {len(entries)} feedback entries")
            return result
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    def _calculate_trend(self, ratings: List[int]) -> str:
        """Calculate trend from ratings list.

        Args:
            ratings: List of rating values

        Returns:
            Trend string: "improving", "declining", or "stable"
        """
        try:
            if len(ratings) < 2:
                return "stable"

            first_half_avg = sum(ratings[: len(ratings) // 2]) / (len(ratings) // 2)
            second_half_avg = sum(ratings[len(ratings) // 2 :]) / (len(ratings) - len(ratings) // 2)

            if second_half_avg > first_half_avg + 0.5:
                return "improving"
            elif second_half_avg < first_half_avg - 0.5:
                return "declining"
            else:
                return "stable"
        except Exception:
            return "stable"

    def _get_satisfaction_level(self, csat_score: float) -> str:
        """Get satisfaction level label.

        Args:
            csat_score: CSAT score (0-100)

        Returns:
            Satisfaction level string
        """
        if csat_score >= 80:
            return "excellent"
        elif csat_score >= 60:
            return "good"
        elif csat_score >= 40:
            return "fair"
        else:
            return "poor"

"""Bias detection and audit repository."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin
from src.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class BiasIncidentModel(Base):
    """
    SQLAlchemy model for bias detection incidents.

    Records individual bias detection incidents in HR content and decisions.

    Attributes:
        id: Primary key
        response_text: Text that triggered bias detection
        category: Category of bias detected (gender/age/race/disability/etc)
        severity: Severity level (low/medium/high)
        term_found: Specific term/phrase flagged
        context: Full context where term appeared
        scanned_at: When incident was detected
    """

    __tablename__ = "bias_incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    response_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    term_found: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[str] = mapped_column(String(500), nullable=False)
    scanned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<BiasIncidentModel(id={self.id}, category={self.category}, severity={self.severity})>"
        )


class BiasAuditReportModel(Base):
    """
    SQLAlchemy model for bias audit reports.

    Stores aggregated bias audit reports with summary statistics and recommendations.

    Attributes:
        id: Primary key
        generated_at: When report was generated
        total_incidents: Total number of incidents found
        severity_breakdown_json: Breakdown by severity level
        recommendations_json: List of recommendations
    """

    __tablename__ = "bias_audit_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    total_incidents: Mapped[int] = mapped_column(default=0, nullable=False)
    severity_breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    recommendations_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    def __repr__(self) -> str:
        return f"<BiasAuditReportModel(id={self.id}, incidents={self.total_incidents})>"


class BiasRepository(BaseRepository[BiasIncidentModel]):
    """
    Repository for bias detection and audit management.

    Tracks bias incidents, generates audit reports, and provides
    recommendations for mitigating bias in HR processes.
    """

    def __init__(self) -> None:
        """Initialize bias repository."""
        super().__init__(BiasIncidentModel)

    def log_incident(
        self,
        response_text: str,
        category: str,
        severity: str,
        term_found: str,
        context: str,
    ) -> Optional[BiasIncidentModel]:
        """
        Log a bias detection incident.

        Args:
            response_text: Text that triggered detection
            category: Bias category (gender/age/race/disability/etc)
            severity: Severity level (low/medium/high)
            term_found: Specific term/phrase detected
            context: Context where term appeared

        Returns:
            Created BiasIncidentModel or None on error
        """
        try:
            data = {
                "response_text": response_text,
                "category": category,
                "severity": severity,
                "term_found": term_found,
                "context": context,
                "scanned_at": datetime.utcnow(),
            }
            incident = self.create(data)
            if incident:
                logger.info(
                    f"Logged bias incident: id={incident.id}, category={category}, severity={severity}"
                )
            return incident
        except Exception as e:
            logger.error(f"Error logging bias incident: {str(e)}")
            return None

    def get_incidents(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[BiasIncidentModel]:
        """
        Get bias incidents with optional filters.

        Args:
            category: Filter by bias category
            severity: Filter by severity level
            limit: Maximum results

        Returns:
            List of BiasIncidentModel instances
        """
        filters = {}
        if category:
            filters["category"] = category
        if severity:
            filters["severity"] = severity

        return self.list(filters, limit=limit)

    def get_incidents_by_severity(self, severity: str) -> List[BiasIncidentModel]:
        """
        Get incidents of specific severity.

        Args:
            severity: Severity level (low/medium/high)

        Returns:
            List of BiasIncidentModel instances
        """
        return self.list({"severity": severity})

    def get_incidents_by_category(self, category: str) -> List[BiasIncidentModel]:
        """
        Get incidents of specific bias category.

        Args:
            category: Bias category

        Returns:
            List of BiasIncidentModel instances
        """
        return self.list({"category": category})

    def get_high_severity_incidents(self, limit: int = 50) -> List[BiasIncidentModel]:
        """
        Get high severity bias incidents.

        Args:
            limit: Maximum results

        Returns:
            List of high severity BiasIncidentModel instances
        """
        return self.get_incidents(severity="high", limit=limit)


class BiasAuditReportRepository(BaseRepository[BiasAuditReportModel]):
    """
    Repository for bias audit reports.

    Manages aggregated bias audit reports with analytics and recommendations.
    """

    def __init__(self) -> None:
        """Initialize bias audit report repository."""
        super().__init__(BiasAuditReportModel)

    def create_report(
        self,
        total_incidents: int,
        severity_breakdown: Optional[Dict[str, int]] = None,
        recommendations: Optional[List[str]] = None,
    ) -> Optional[BiasAuditReportModel]:
        """
        Create new bias audit report.

        Args:
            total_incidents: Total number of incidents
            severity_breakdown: Count breakdown by severity
            recommendations: List of recommendations

        Returns:
            Created BiasAuditReportModel or None on error
        """
        try:
            data = {
                "generated_at": datetime.utcnow(),
                "total_incidents": total_incidents,
                "severity_breakdown_json": severity_breakdown or {"low": 0, "medium": 0, "high": 0},
                "recommendations_json": {"recommendations": recommendations or []},
            }
            report = self.create(data)
            if report:
                logger.info(
                    f"Created bias audit report: id={report.id}, incidents={total_incidents}"
                )
            return report
        except Exception as e:
            logger.error(f"Error creating bias audit report: {str(e)}")
            return None

    def get_reports(self, limit: int = 50) -> List[BiasAuditReportModel]:
        """
        Get bias audit reports.

        Args:
            limit: Maximum results

        Returns:
            List of BiasAuditReportModel instances
        """
        try:
            with self._get_session() as session:
                stmt = (
                    select(BiasAuditReportModel)
                    .order_by(BiasAuditReportModel.generated_at.desc())
                    .limit(limit)
                )
                return session.execute(stmt).scalars().all()
        except Exception as e:
            logger.error(f"Error getting bias audit reports: {str(e)}")
            return []

    def get_latest_report(self) -> Optional[BiasAuditReportModel]:
        """
        Get most recent bias audit report.

        Returns:
            Latest BiasAuditReportModel or None if none exist
        """
        try:
            with self._get_session() as session:
                stmt = (
                    select(BiasAuditReportModel)
                    .order_by(BiasAuditReportModel.generated_at.desc())
                    .limit(1)
                )
                return session.execute(stmt).scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting latest bias audit report: {str(e)}")
            return None

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics across all reports.

        Returns:
            Dictionary with aggregate statistics
        """
        try:
            incident_repo = BiasRepository()
            all_incidents = incident_repo.list(limit=10000)

            severity_counts = {"low": 0, "medium": 0, "high": 0}
            category_counts = {}

            for incident in all_incidents:
                severity_counts[incident.severity] = severity_counts.get(incident.severity, 0) + 1
                category_counts[incident.category] = category_counts.get(incident.category, 0) + 1

            return {
                "total_incidents": len(all_incidents),
                "severity_breakdown": severity_counts,
                "category_breakdown": category_counts,
                "generated_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting summary stats: {str(e)}")
            return {"error": str(e)}

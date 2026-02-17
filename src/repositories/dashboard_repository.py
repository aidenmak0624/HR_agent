"""Dashboard and metrics repository for analytics and reporting."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin
from src.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DashboardModel(Base, TimestampMixin):
    """
    SQLAlchemy model for customizable dashboards.

    Represents user dashboards with widgets and configuration.

    Attributes:
        id: Primary key
        name: Dashboard name
        owner_id: Employee ID of dashboard owner
        description: Dashboard description
        created_at: Creation timestamp
        updated_at: Last update timestamp
        widgets: Relationship to DashboardWidgetModel
    """

    __tablename__ = "dashboards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    widgets: Mapped[List["DashboardWidgetModel"]] = relationship(
        "DashboardWidgetModel",
        back_populates="dashboard",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DashboardModel(id={self.id}, name={self.name}, owner_id={self.owner_id})>"


class DashboardWidgetModel(Base):
    """
    SQLAlchemy model for dashboard widgets.

    Represents individual widgets within a dashboard.

    Attributes:
        id: Primary key
        dashboard_id: Foreign key to DashboardModel
        widget_type: Type of widget (chart/metric/table/etc)
        title: Widget title
        config_json: Widget configuration
        data_json: Widget data
        position: Position on dashboard
        dashboard: Relationship to DashboardModel
    """

    __tablename__ = "dashboard_widgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(ForeignKey("dashboards.id"), nullable=False)
    widget_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    position: Mapped[int] = mapped_column(default=0, nullable=False)

    dashboard: Mapped["DashboardModel"] = relationship("DashboardModel", back_populates="widgets")

    def __repr__(self) -> str:
        return f"<DashboardWidgetModel(id={self.id}, type={self.widget_type}, title={self.title})>"


class MetricSnapshotModel(Base):
    """
    SQLAlchemy model for metric snapshots.

    Records point-in-time metric values for analytics and trending.

    Attributes:
        id: Primary key
        metric_name: Name of metric
        metric_value: Metric value
        department: Department scope (optional)
        recorded_at: When metric was recorded
    """

    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric_value: Mapped[float] = mapped_column(nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<MetricSnapshotModel(id={self.id}, metric={self.metric_name}, value={self.metric_value})>"


class DashboardRepository(BaseRepository[DashboardModel]):
    """
    Repository for dashboard persistence and management.

    Handles creation and management of user dashboards with widgets.
    """

    def __init__(self) -> None:
        """Initialize dashboard repository."""
        super().__init__(DashboardModel)

    def create_dashboard(
        self,
        name: str,
        owner_id: int,
        description: str = "",
    ) -> Optional[DashboardModel]:
        """
        Create new dashboard.

        Args:
            name: Dashboard name
            owner_id: Owner employee ID
            description: Dashboard description

        Returns:
            Created DashboardModel or None on error
        """
        try:
            data = {
                "name": name,
                "owner_id": owner_id,
                "description": description,
            }
            dashboard = self.create(data)
            if dashboard:
                logger.info(f"Created dashboard: id={dashboard.id}, name={name}")
            return dashboard
        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")
            return None

    def get_dashboard(self, dashboard_id: int) -> Optional[DashboardModel]:
        """
        Get dashboard by ID with all widgets.

        Args:
            dashboard_id: Dashboard ID

        Returns:
            DashboardModel with populated widgets or None
        """
        return self.get(dashboard_id)

    def get_dashboards_for_owner(self, owner_id: int) -> List[DashboardModel]:
        """
        Get all dashboards owned by user.

        Args:
            owner_id: Owner employee ID

        Returns:
            List of DashboardModel instances
        """
        return self.list({"owner_id": owner_id})

    def update_dashboard(
        self,
        dashboard_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[DashboardModel]:
        """
        Update dashboard metadata.

        Args:
            dashboard_id: Dashboard ID
            name: New name (if changing)
            description: New description (if changing)

        Returns:
            Updated DashboardModel or None on error
        """
        try:
            data = {}
            if name:
                data["name"] = name
            if description:
                data["description"] = description

            dashboard = self.update(dashboard_id, data)
            if dashboard:
                logger.info(f"Updated dashboard {dashboard_id}")
            return dashboard
        except Exception as e:
            logger.error(f"Error updating dashboard: {str(e)}")
            return None


class DashboardWidgetRepository(BaseRepository[DashboardWidgetModel]):
    """
    Repository for dashboard widget management.

    Handles creation and updates of individual widgets.
    """

    def __init__(self) -> None:
        """Initialize dashboard widget repository."""
        super().__init__(DashboardWidgetModel)

    def add_widget(
        self,
        dashboard_id: int,
        widget_type: str,
        title: str,
        config: Optional[Dict[str, Any]] = None,
        position: int = 0,
    ) -> Optional[DashboardWidgetModel]:
        """
        Add widget to dashboard.

        Args:
            dashboard_id: Dashboard ID
            widget_type: Type of widget
            title: Widget title
            config: Widget configuration
            position: Position on dashboard

        Returns:
            Created DashboardWidgetModel or None on error
        """
        try:
            data = {
                "dashboard_id": dashboard_id,
                "widget_type": widget_type,
                "title": title,
                "config_json": config or {},
                "position": position,
            }
            widget = self.create(data)
            if widget:
                logger.info(f"Added widget to dashboard {dashboard_id}: {title}")
            return widget
        except Exception as e:
            logger.error(f"Error adding widget: {str(e)}")
            return None

    def update_widget_data(
        self,
        widget_id: int,
        data: Dict[str, Any],
    ) -> Optional[DashboardWidgetModel]:
        """
        Update widget data.

        Args:
            widget_id: Widget ID
            data: New widget data

        Returns:
            Updated DashboardWidgetModel or None on error
        """
        return self.update(widget_id, {"data_json": data})

    def get_widgets_for_dashboard(self, dashboard_id: int) -> List[DashboardWidgetModel]:
        """
        Get all widgets for dashboard.

        Args:
            dashboard_id: Dashboard ID

        Returns:
            List of DashboardWidgetModel instances
        """
        try:
            with self._get_session() as session:
                stmt = (
                    select(DashboardWidgetModel)
                    .where(DashboardWidgetModel.dashboard_id == dashboard_id)
                    .order_by(DashboardWidgetModel.position)
                )
                return session.execute(stmt).scalars().all()
        except Exception as e:
            logger.error(f"Error getting widgets for dashboard {dashboard_id}: {str(e)}")
            return []


class MetricSnapshotRepository(BaseRepository[MetricSnapshotModel]):
    """
    Repository for metric snapshots.

    Manages historical metric data for trending and analytics.
    """

    def __init__(self) -> None:
        """Initialize metric snapshot repository."""
        super().__init__(MetricSnapshotModel)

    def save_metric_snapshot(
        self,
        metric_name: str,
        metric_value: float,
        department: Optional[str] = None,
    ) -> Optional[MetricSnapshotModel]:
        """
        Record metric snapshot.

        Args:
            metric_name: Name of metric
            metric_value: Metric value
            department: Department scope

        Returns:
            Created MetricSnapshotModel or None on error
        """
        try:
            data = {
                "metric_name": metric_name,
                "metric_value": metric_value,
                "department": department,
                "recorded_at": datetime.utcnow(),
            }
            snapshot = self.create(data)
            if snapshot:
                logger.info(f"Saved metric snapshot: {metric_name}={metric_value}")
            return snapshot
        except Exception as e:
            logger.error(f"Error saving metric snapshot: {str(e)}")
            return None

    def get_metric_history(
        self,
        metric_name: str,
        department: Optional[str] = None,
        limit: int = 100,
    ) -> List[MetricSnapshotModel]:
        """
        Get historical values for metric.

        Args:
            metric_name: Name of metric
            department: Department filter (optional)
            limit: Maximum results

        Returns:
            List of MetricSnapshotModel instances in chronological order
        """
        try:
            with self._get_session() as session:
                stmt = select(MetricSnapshotModel).where(
                    MetricSnapshotModel.metric_name == metric_name
                )

                if department:
                    stmt = stmt.where(MetricSnapshotModel.department == department)

                stmt = (
                    stmt.order_by(MetricSnapshotModel.recorded_at.asc())
                    .limit(limit)
                )
                return session.execute(stmt).scalars().all()
        except Exception as e:
            logger.error(f"Error getting metric history: {str(e)}")
            return []

    def get_latest_metrics(
        self,
        department: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, float]:
        """
        Get latest value for each metric.

        Args:
            department: Department filter (optional)
            limit: Maximum metric types to retrieve

        Returns:
            Dictionary mapping metric_name to latest value
        """
        try:
            with self._get_session() as session:
                stmt = select(MetricSnapshotModel)

                if department:
                    stmt = stmt.where(MetricSnapshotModel.department == department)

                snapshots = session.execute(stmt).scalars().all()

                # Get latest value for each metric
                metrics = {}
                for snapshot in snapshots:
                    if snapshot.metric_name not in metrics:
                        metrics[snapshot.metric_name] = snapshot.metric_value
                    elif snapshot.recorded_at > datetime.utcnow():
                        metrics[snapshot.metric_name] = snapshot.metric_value

                return dict(list(metrics.items())[:limit])
        except Exception as e:
            logger.error(f"Error getting latest metrics: {str(e)}")
            return {}

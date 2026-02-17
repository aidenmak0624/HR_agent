"""
DASH-001: Analytics Dashboard
Analytics dashboard service for HR platform with widgets, metrics, and visualizations.

Provides HR analytics, leave analytics, agent performance, and compliance metrics
with RBAC-based access control and export capabilities.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.rbac import DataScope, get_data_scope

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Metric calculation types."""
    COUNT = "count"
    AVERAGE = "average"
    SUM = "sum"
    PERCENTAGE = "percentage"
    TREND = "trend"


class ChartType(str, Enum):
    """Chart visualization types."""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    HEATMAP = "heatmap"


@dataclass
class DashboardWidget:
    """Dashboard widget definition."""

    widget_id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    title: str = ""
    widget_type: str = "metric"  # metric, chart, table, kpi
    metric_type: Optional[MetricType] = None
    chart_type: Optional[ChartType] = None
    data: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "widget_id": self.widget_id,
            "title": self.title,
            "widget_type": self.widget_type,
            "metric_type": self.metric_type.value if self.metric_type else None,
            "chart_type": self.chart_type.value if self.chart_type else None,
            "data": self.data,
            "config": self.config,
        }


@dataclass
class Dashboard:
    """Dashboard instance with widgets."""

    dashboard_id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    name: str = ""
    description: str = ""
    owner_id: str = ""
    widgets: Dict[str, DashboardWidget] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "widgets": [w.to_dict() for w in self.widgets.values()],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DashboardService:
    """Service for dashboard management and analytics."""

    def __init__(self):
        """Initialize dashboard service."""
        self.dashboards: Dict[str, Dashboard] = {}
        self.employee_data: List[Dict[str, Any]] = []
        self.leave_data: List[Dict[str, Any]] = []
        self.agent_metrics: List[Dict[str, Any]] = []
        self.compliance_data: List[Dict[str, Any]] = []

    def create_dashboard(
        self,
        name: str,
        description: str,
        owner_id: str,
    ) -> str:
        """Create new dashboard."""
        dashboard = Dashboard(
            name=name,
            description=description,
            owner_id=owner_id,
        )
        self.dashboards[dashboard.dashboard_id] = dashboard
        logger.info(f"Created dashboard: {dashboard.dashboard_id}")
        return dashboard.dashboard_id

    def add_widget(
        self,
        dashboard_id: str,
        title: str,
        widget_type: str,
        metric_type: Optional[MetricType] = None,
        chart_type: Optional[ChartType] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add widget to dashboard."""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        widget = DashboardWidget(
            title=title,
            widget_type=widget_type,
            metric_type=metric_type,
            chart_type=chart_type,
            config=config or {},
        )

        dashboard.widgets[widget.widget_id] = widget
        dashboard.updated_at = datetime.utcnow()
        logger.info(f"Added widget {widget.widget_id} to dashboard {dashboard_id}")
        return widget.widget_id

    def update_widget_data(
        self,
        dashboard_id: str,
        widget_id: str,
        data: Dict[str, Any],
    ) -> bool:
        """Update widget data."""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        widget = dashboard.widgets.get(widget_id)
        if not widget:
            raise ValueError(f"Widget not found: {widget_id}")

        widget.data = data
        widget.updated_at = datetime.utcnow()
        dashboard.updated_at = datetime.utcnow()
        return True

    def get_hr_metrics(self, user_role: str, department: Optional[str] = None) -> Dict[str, Any]:
        """Get HR metrics based on user role and RBAC."""
        try:
            scope = get_data_scope(user_role, "analytics")
        except Exception:
            return {"error": "Invalid role"}

        metrics = {
            "headcount": 150,
            "new_hires_this_year": 25,
            "turnover_rate": 12.5,
            "average_tenure": 4.2,
            "departments": 8,
            "positions_open": 5,
        }

        # Apply RBAC filtering
        if scope == DataScope.OWN:
            metrics = {"restricted": True}
        elif scope == DataScope.TEAM:
            metrics = {"headcount": 12, "turnover_rate": 8.0}
        elif scope == DataScope.DEPARTMENT:
            metrics["filtered_by"] = department or "all"

        return metrics

    def get_leave_analytics(
        self,
        user_role: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get leave analytics and patterns."""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=90)
        if not end_date:
            end_date = datetime.utcnow()

        analytics = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "utilization": {
                "vacation": 65.3,
                "sick": 45.2,
                "personal": 30.0,
            },
            "upcoming_30_days": 8,
            "patterns": {
                "peak_months": ["July", "August", "December"],
                "avg_duration": 3.2,
                "approval_rate": 98.5,
            },
            "by_department": {
                "Engineering": 70.2,
                "Sales": 72.5,
                "HR": 55.0,
            },
        }

        return analytics

    def get_agent_performance(self) -> Dict[str, Any]:
        """Get agent performance metrics."""
        return {
            "total_queries": 2450,
            "average_response_time_ms": 450,
            "accuracy_score": 0.92,
            "query_volume": {
                "leave_request": 650,
                "policy": 580,
                "benefits": 450,
                "employee_info": 520,
                "compensation": 250,
            },
            "agent_metrics": {
                "leave_request": {
                    "queries": 650,
                    "avg_time_ms": 380,
                    "accuracy": 0.94,
                },
                "policy": {
                    "queries": 580,
                    "avg_time_ms": 520,
                    "accuracy": 0.89,
                },
            },
            "trend": "improving",
        }

    def get_compliance_metrics(self) -> Dict[str, Any]:
        """Get compliance and policy metrics."""
        return {
            "training_completion": {
                "mandatory": 85.3,
                "optional": 42.1,
                "overdue": 12,
            },
            "policy_acknowledgment": {
                "code_of_conduct": 92.5,
                "harassment_policy": 88.7,
                "data_security": 95.2,
            },
            "audit_status": {
                "compliant": 145,
                "at_risk": 3,
                "non_compliant": 2,
            },
            "certifications": {
                "active": 89,
                "expiring_30_days": 5,
                "expired": 1,
            },
        }

    def get_department_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics broken down by department."""
        return {
            "Engineering": {
                "headcount": 45,
                "new_hires": 8,
                "turnover": 10.5,
                "avg_tenure": 4.8,
            },
            "Sales": {
                "headcount": 35,
                "new_hires": 7,
                "turnover": 15.2,
                "avg_tenure": 3.2,
            },
            "HR": {
                "headcount": 8,
                "new_hires": 1,
                "turnover": 5.0,
                "avg_tenure": 5.6,
            },
            "Finance": {
                "headcount": 12,
                "new_hires": 2,
                "turnover": 8.3,
                "avg_tenure": 4.2,
            },
        }

    def export_metrics_json(
        self,
        dashboard_id: str,
        date_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Export dashboard metrics as JSON."""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        export = {
            "dashboard_id": dashboard_id,
            "dashboard_name": dashboard.name,
            "exported_at": datetime.utcnow().isoformat(),
            "date_range": date_range or {
                "start": (datetime.utcnow() - timedelta(days=30)).isoformat(),
                "end": datetime.utcnow().isoformat(),
            },
            "widgets": [w.to_dict() for w in dashboard.widgets.values()],
        }

        logger.info(f"Exported dashboard metrics: {dashboard_id}")
        return export

    def export_metrics_csv(
        self,
        dashboard_id: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Export dashboard metrics as CSV."""
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        if not output_path:
            output_path = f"/tmp/dashboard_{dashboard_id}.csv"

        # Create CSV with widget data
        import csv
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Widget", "Metric", "Value", "Updated"])

            for widget in dashboard.widgets.values():
                for key, value in widget.data.items():
                    writer.writerow([
                        widget.title,
                        key,
                        value,
                        widget.updated_at.isoformat(),
                    ])

        logger.info(f"Exported dashboard to CSV: {output_path}")
        return output_path

    def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """Get dashboard by ID."""
        return self.dashboards.get(dashboard_id)

    def list_dashboards(self, owner_id: Optional[str] = None) -> List[Dashboard]:
        """List dashboards, optionally filtered by owner."""
        dashboards = list(self.dashboards.values())
        if owner_id:
            dashboards = [d for d in dashboards if d.owner_id == owner_id]
        return dashboards

    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete dashboard."""
        if dashboard_id not in self.dashboards:
            raise ValueError(f"Dashboard not found: {dashboard_id}")

        del self.dashboards[dashboard_id]
        logger.info(f"Deleted dashboard: {dashboard_id}")
        return True

    def create_standard_hr_dashboard(self, user_id: str) -> str:
        """Create a standard HR dashboard with common metrics."""
        dashboard_id = self.create_dashboard(
            name="HR Analytics Dashboard",
            description="Key HR metrics and analytics",
            owner_id=user_id,
        )

        # Add standard widgets
        self.add_widget(
            dashboard_id,
            "Headcount",
            "kpi",
            metric_type=MetricType.COUNT,
            config={"metric": "total_employees"},
        )

        self.add_widget(
            dashboard_id,
            "Turnover Rate",
            "kpi",
            metric_type=MetricType.PERCENTAGE,
            config={"metric": "turnover_rate"},
        )

        self.add_widget(
            dashboard_id,
            "Hiring Trends",
            "chart",
            chart_type=ChartType.LINE,
            config={"metric": "new_hires_over_time"},
        )

        self.add_widget(
            dashboard_id,
            "Department Distribution",
            "chart",
            chart_type=ChartType.PIE,
            config={"metric": "headcount_by_department"},
        )

        self.add_widget(
            dashboard_id,
            "Leave Utilization",
            "chart",
            chart_type=ChartType.BAR,
            config={"metric": "leave_by_type"},
        )

        logger.info(f"Created standard HR dashboard: {dashboard_id}")
        return dashboard_id

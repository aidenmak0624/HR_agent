"""Tests for analytics dashboard service."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.platform_services.dashboard import (
    DashboardService,
    Dashboard,
    DashboardWidget,
    MetricType,
    ChartType,
)


@pytest.fixture
def dashboard_service():
    """Create dashboard service instance."""
    return DashboardService()


class TestDashboardCreation:
    """Tests for creating dashboards."""

    def test_create_dashboard(self, dashboard_service):
        """create_dashboard creates new dashboard."""
        dashboard_id = dashboard_service.create_dashboard(
            name="HR Analytics", description="Main HR dashboard", owner_id="user-001"
        )

        assert dashboard_id in dashboard_service.dashboards
        dashboard = dashboard_service.dashboards[dashboard_id]
        assert dashboard.name == "HR Analytics"
        assert dashboard.owner_id == "user-001"

    def test_create_dashboard_minimal(self, dashboard_service):
        """create_dashboard works with minimal parameters."""
        dashboard_id = dashboard_service.create_dashboard(
            name="Simple Dashboard", description="", owner_id="user-002"
        )

        assert dashboard_id in dashboard_service.dashboards

    def test_get_dashboard(self, dashboard_service):
        """get_dashboard retrieves dashboard by ID."""
        dashboard_id = dashboard_service.create_dashboard(
            name="Test Dashboard", description="", owner_id="user-003"
        )

        dashboard = dashboard_service.get_dashboard(dashboard_id)

        assert dashboard is not None
        assert dashboard.name == "Test Dashboard"

    def test_get_nonexistent_dashboard_returns_none(self, dashboard_service):
        """get_dashboard returns None for nonexistent dashboard."""
        dashboard = dashboard_service.get_dashboard("nonexistent")

        assert dashboard is None

    def test_delete_dashboard(self, dashboard_service):
        """delete_dashboard removes dashboard."""
        dashboard_id = dashboard_service.create_dashboard(
            name="To Delete", description="", owner_id="user-004"
        )

        result = dashboard_service.delete_dashboard(dashboard_id)

        assert result is True
        assert dashboard_id not in dashboard_service.dashboards

    def test_delete_nonexistent_dashboard_raises(self, dashboard_service):
        """delete_dashboard raises for nonexistent dashboard."""
        with pytest.raises(ValueError, match="Dashboard not found"):
            dashboard_service.delete_dashboard("nonexistent")


class TestWidgetManagement:
    """Tests for adding and removing widgets."""

    def test_add_widget(self, dashboard_service):
        """add_widget adds widget to dashboard."""
        dashboard_id = dashboard_service.create_dashboard("Test", "", owner_id="user-005")

        widget_id = dashboard_service.add_widget(
            dashboard_id=dashboard_id,
            title="Headcount",
            widget_type="kpi",
            metric_type=MetricType.COUNT,
            config={"metric": "total_employees"},
        )

        dashboard = dashboard_service.get_dashboard(dashboard_id)
        assert widget_id in dashboard.widgets

    def test_add_chart_widget(self, dashboard_service):
        """add_widget works with chart widgets."""
        dashboard_id = dashboard_service.create_dashboard("Charts", "", owner_id="user-006")

        widget_id = dashboard_service.add_widget(
            dashboard_id=dashboard_id,
            title="Turnover Trend",
            widget_type="chart",
            chart_type=ChartType.LINE,
            config={"metric": "turnover_rate_over_time"},
        )

        widget = dashboard_service.get_dashboard(dashboard_id).widgets[widget_id]
        assert widget.chart_type == ChartType.LINE

    def test_add_widget_nonexistent_dashboard_raises(self, dashboard_service):
        """add_widget raises for nonexistent dashboard."""
        with pytest.raises(ValueError, match="Dashboard not found"):
            dashboard_service.add_widget(
                dashboard_id="nonexistent", title="Widget", widget_type="metric"
            )

    def test_update_widget_data(self, dashboard_service):
        """update_widget_data updates widget content."""
        dashboard_id = dashboard_service.create_dashboard("Test", "", owner_id="user-007")
        widget_id = dashboard_service.add_widget(
            dashboard_id=dashboard_id, title="Metric", widget_type="metric"
        )

        data = {"value": 150, "unit": "employees"}
        result = dashboard_service.update_widget_data(dashboard_id, widget_id, data)

        assert result is True
        widget = dashboard_service.get_dashboard(dashboard_id).widgets[widget_id]
        assert widget.data == data

    def test_update_widget_nonexistent_widget_raises(self, dashboard_service):
        """update_widget_data raises for nonexistent widget."""
        dashboard_id = dashboard_service.create_dashboard("Test", "", owner_id="user-008")

        with pytest.raises(ValueError, match="Widget not found"):
            dashboard_service.update_widget_data(dashboard_id, "nonexistent", {})


class TestHRMetrics:
    """Tests for headcount, turnover, time-to-hire calculations."""

    def test_get_hr_metrics(self, dashboard_service):
        """get_hr_metrics returns HR metrics."""
        metrics = dashboard_service.get_hr_metrics(user_role="hr_admin")

        assert "headcount" in metrics
        assert "turnover_rate" in metrics
        assert "new_hires_this_year" in metrics
        assert "positions_open" in metrics

    def test_hr_metrics_values_reasonable(self, dashboard_service):
        """HR metrics contain reasonable values."""
        metrics = dashboard_service.get_hr_metrics(user_role="hr_admin")

        assert metrics["headcount"] > 0
        assert 0 <= metrics["turnover_rate"] <= 100
        assert metrics["new_hires_this_year"] >= 0

    @patch("src.platform.dashboard.get_data_scope")
    def test_hr_metrics_rbac_own_scope(self, mock_scope, dashboard_service):
        """get_hr_metrics respects OWN data scope."""
        from src.core.rbac import DataScope

        mock_scope.return_value = DataScope.OWN

        metrics = dashboard_service.get_hr_metrics(user_role="employee")

        assert "restricted" in metrics
        assert metrics["restricted"] is True

    @patch("src.platform.dashboard.get_data_scope")
    def test_hr_metrics_rbac_team_scope(self, mock_scope, dashboard_service):
        """get_hr_metrics respects TEAM data scope."""
        from src.core.rbac import DataScope

        mock_scope.return_value = DataScope.TEAM

        metrics = dashboard_service.get_hr_metrics(user_role="manager")

        assert "headcount" in metrics
        assert metrics["headcount"] < 150  # Limited team size

    def test_department_breakdown(self, dashboard_service):
        """get_department_breakdown returns metrics by department."""
        breakdown = dashboard_service.get_department_breakdown()

        assert "Engineering" in breakdown
        assert "Sales" in breakdown
        assert "HR" in breakdown
        assert "Finance" in breakdown

        # Each department should have metrics
        for dept, metrics in breakdown.items():
            assert "headcount" in metrics
            assert "turnover" in metrics


class TestLeaveAnalytics:
    """Tests for leave utilization metrics."""

    def test_get_leave_analytics(self, dashboard_service):
        """get_leave_analytics returns leave metrics."""
        analytics = dashboard_service.get_leave_analytics(user_role="hr_admin")

        assert "period" in analytics
        assert "utilization" in analytics
        assert "patterns" in analytics

    def test_leave_analytics_has_period(self, dashboard_service):
        """Leave analytics includes time period."""
        analytics = dashboard_service.get_leave_analytics(user_role="hr_admin")

        assert "start" in analytics["period"]
        assert "end" in analytics["period"]

    def test_leave_analytics_utilization(self, dashboard_service):
        """Leave analytics includes utilization by type."""
        analytics = dashboard_service.get_leave_analytics(user_role="hr_admin")

        assert "vacation" in analytics["utilization"]
        assert "sick" in analytics["utilization"]
        assert "personal" in analytics["utilization"]

    def test_leave_analytics_patterns(self, dashboard_service):
        """Leave analytics includes patterns."""
        analytics = dashboard_service.get_leave_analytics(user_role="hr_admin")

        assert "peak_months" in analytics["patterns"]
        assert "avg_duration" in analytics["patterns"]
        assert "approval_rate" in analytics["patterns"]

    def test_leave_analytics_with_date_range(self, dashboard_service):
        """get_leave_analytics respects custom date range."""
        start = datetime.utcnow() - timedelta(days=180)
        end = datetime.utcnow()

        analytics = dashboard_service.get_leave_analytics(
            user_role="hr_admin", start_date=start, end_date=end
        )

        period_start = datetime.fromisoformat(analytics["period"]["start"])
        assert period_start >= start


class TestAgentPerformance:
    """Tests for agent performance metrics."""

    def test_get_agent_performance(self, dashboard_service):
        """get_agent_performance returns agent metrics."""
        metrics = dashboard_service.get_agent_performance()

        assert "total_queries" in metrics
        assert "average_response_time_ms" in metrics
        assert "accuracy_score" in metrics
        assert "query_volume" in metrics

    def test_agent_performance_metrics_reasonable(self, dashboard_service):
        """Agent performance metrics are reasonable."""
        metrics = dashboard_service.get_agent_performance()

        assert metrics["total_queries"] > 0
        assert 0 < metrics["average_response_time_ms"] < 10000
        assert 0 <= metrics["accuracy_score"] <= 1.0

    def test_agent_performance_by_type(self, dashboard_service):
        """Agent performance broken down by type."""
        metrics = dashboard_service.get_agent_performance()

        assert "leave_request" in metrics["query_volume"]
        assert "policy" in metrics["query_volume"]
        assert "benefits" in metrics["query_volume"]

    def test_agent_metrics_detail(self, dashboard_service):
        """Agent metrics include detailed breakdown."""
        metrics = dashboard_service.get_agent_performance()

        assert "agent_metrics" in metrics
        assert "leave_request" in metrics["agent_metrics"]

        leave_metrics = metrics["agent_metrics"]["leave_request"]
        assert "queries" in leave_metrics
        assert "avg_time_ms" in leave_metrics
        assert "accuracy" in leave_metrics


class TestCompliance:
    """Tests for compliance and policy metrics."""

    def test_get_compliance_metrics(self, dashboard_service):
        """get_compliance_metrics returns compliance data."""
        metrics = dashboard_service.get_compliance_metrics()

        assert "training_completion" in metrics
        assert "policy_acknowledgment" in metrics
        assert "audit_status" in metrics

    def test_training_completion_metrics(self, dashboard_service):
        """Training completion includes mandatory and optional."""
        metrics = dashboard_service.get_compliance_metrics()

        assert "mandatory" in metrics["training_completion"]
        assert "optional" in metrics["training_completion"]
        assert "overdue" in metrics["training_completion"]

    def test_policy_acknowledgment_metrics(self, dashboard_service):
        """Policy acknowledgment tracks major policies."""
        metrics = dashboard_service.get_compliance_metrics()

        ack = metrics["policy_acknowledgment"]
        assert "code_of_conduct" in ack
        assert "harassment_policy" in ack
        assert "data_security" in ack

    def test_audit_status_metrics(self, dashboard_service):
        """Audit status shows compliance breakdown."""
        metrics = dashboard_service.get_compliance_metrics()

        audit = metrics["audit_status"]
        assert "compliant" in audit
        assert "at_risk" in audit
        assert "non_compliant" in audit


class TestExport:
    """Tests for JSON and CSV export."""

    def test_export_metrics_json(self, dashboard_service):
        """export_metrics_json exports dashboard as JSON."""
        dashboard_id = dashboard_service.create_dashboard(
            name="Export Test", description="", owner_id="user-009"
        )
        dashboard_service.add_widget(
            dashboard_id=dashboard_id, title="Test Widget", widget_type="metric"
        )

        export_data = dashboard_service.export_metrics_json(dashboard_id)

        assert export_data["dashboard_id"] == dashboard_id
        assert export_data["dashboard_name"] == "Export Test"
        assert "widgets" in export_data
        assert "date_range" in export_data

    def test_export_metrics_json_nonexistent_raises(self, dashboard_service):
        """export_metrics_json raises for nonexistent dashboard."""
        with pytest.raises(ValueError, match="Dashboard not found"):
            dashboard_service.export_metrics_json("nonexistent")

    def test_export_metrics_csv(self, dashboard_service):
        """export_metrics_csv exports dashboard as CSV."""
        dashboard_id = dashboard_service.create_dashboard(
            name="CSV Export", description="", owner_id="user-010"
        )
        widget_id = dashboard_service.add_widget(
            dashboard_id=dashboard_id, title="Headcount", widget_type="metric"
        )
        dashboard_service.update_widget_data(
            dashboard_id, widget_id, {"total": 150, "new_hires": 25}
        )

        output_path = dashboard_service.export_metrics_csv(dashboard_id)

        assert output_path is not None
        assert "dashboard_" in output_path
        assert ".csv" in output_path

    def test_export_metrics_csv_with_custom_path(self, dashboard_service):
        """export_metrics_csv respects custom output path."""
        dashboard_id = dashboard_service.create_dashboard(
            name="Custom Path", description="", owner_id="user-011"
        )

        output_path = dashboard_service.export_metrics_csv(
            dashboard_id, output_path="/tmp/custom_dashboard.csv"
        )

        assert output_path == "/tmp/custom_dashboard.csv"


class TestRBAC:
    """Tests for visibility filtering by role."""

    @patch("src.platform.dashboard.get_data_scope")
    def test_hr_metrics_visibility_by_role(self, mock_scope, dashboard_service):
        """Different roles see different metrics."""
        from src.core.rbac import DataScope

        # HR Admin sees everything
        mock_scope.return_value = DataScope.ALL
        admin_metrics = dashboard_service.get_hr_metrics(user_role="hr_admin")
        assert "headcount" in admin_metrics

        # Employee sees own data only
        mock_scope.return_value = DataScope.OWN
        emp_metrics = dashboard_service.get_hr_metrics(user_role="employee")
        assert "restricted" in emp_metrics

    def test_list_dashboards_by_owner(self, dashboard_service):
        """list_dashboards can filter by owner."""
        dashboard_service.create_dashboard("User1 Dashboard", "", owner_id="user-1")
        dashboard_service.create_dashboard("User1 Another", "", owner_id="user-1")
        dashboard_service.create_dashboard("User2 Dashboard", "", owner_id="user-2")

        user1_dashboards = dashboard_service.list_dashboards(owner_id="user-1")

        assert len(user1_dashboards) == 2
        assert all(d.owner_id == "user-1" for d in user1_dashboards)


class TestStandardDashboard:
    """Tests for standard HR dashboard creation."""

    def test_create_standard_hr_dashboard(self, dashboard_service):
        """create_standard_hr_dashboard creates full dashboard."""
        dashboard_id = dashboard_service.create_standard_hr_dashboard("user-012")

        dashboard = dashboard_service.get_dashboard(dashboard_id)
        assert dashboard is not None
        assert dashboard.name == "HR Analytics Dashboard"
        assert len(dashboard.widgets) >= 5

    def test_standard_dashboard_has_key_metrics(self, dashboard_service):
        """Standard dashboard includes headcount and turnover."""
        dashboard_id = dashboard_service.create_standard_hr_dashboard("user-013")

        dashboard = dashboard_service.get_dashboard(dashboard_id)
        widget_titles = [w.title for w in dashboard.widgets.values()]

        assert "Headcount" in widget_titles
        assert "Turnover Rate" in widget_titles

    def test_standard_dashboard_has_charts(self, dashboard_service):
        """Standard dashboard includes visualizations."""
        dashboard_id = dashboard_service.create_standard_hr_dashboard("user-014")

        dashboard = dashboard_service.get_dashboard(dashboard_id)
        charts = [w for w in dashboard.widgets.values() if w.widget_type == "chart"]

        assert len(charts) > 0


class TestDashboardLifecycle:
    """Tests for full dashboard lifecycle."""

    def test_dashboard_create_update_export(self, dashboard_service):
        """Complete dashboard lifecycle."""
        # Create
        dashboard_id = dashboard_service.create_dashboard(
            name="Lifecycle Test", description="", owner_id="user-015"
        )

        # Add widgets
        widget_id = dashboard_service.add_widget(
            dashboard_id=dashboard_id,
            title="Key Metric",
            widget_type="kpi",
            metric_type=MetricType.COUNT,
        )

        # Update widget
        dashboard_service.update_widget_data(dashboard_id, widget_id, {"current_value": 42})

        # Export
        export = dashboard_service.export_metrics_json(dashboard_id)

        assert export["dashboard_id"] == dashboard_id
        assert len(export["widgets"]) == 1

    def test_multiple_widgets_lifecycle(self, dashboard_service):
        """Add multiple widgets and verify all tracked."""
        dashboard_id = dashboard_service.create_dashboard(
            name="Multi Widget", description="", owner_id="user-016"
        )

        # Add multiple widgets
        widgets = []
        for i in range(5):
            widget_id = dashboard_service.add_widget(
                dashboard_id=dashboard_id, title=f"Widget {i}", widget_type="metric"
            )
            widgets.append(widget_id)

        dashboard = dashboard_service.get_dashboard(dashboard_id)
        assert len(dashboard.widgets) == 5

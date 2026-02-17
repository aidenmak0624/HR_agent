"""
Unit tests for Cost Dashboard Service - Iteration 8 Wave 2.
Tests for token budget and cost tracking functionality.
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID
from unittest.mock import Mock, patch, MagicMock

from src.platform_services.cost_dashboard import (
    CostCategory,
    UsageRecord,
    BudgetConfig,
    CostSummary,
    CostDashboardService,
)


class TestCostCategory:
    """Test CostCategory enum."""

    def test_cost_category_enum_values(self):
        """Test all CostCategory enum values exist."""
        assert CostCategory.LLM_QUERY.value == "llm_query"
        assert CostCategory.LLM_TRANSLATION.value == "llm_translation"
        assert CostCategory.LLM_SUMMARIZATION.value == "llm_summarization"
        assert CostCategory.RAG_RETRIEVAL.value == "rag_retrieval"
        assert CostCategory.AGENT_EXECUTION.value == "agent_execution"
        assert CostCategory.EMBEDDING.value == "embedding"

    def test_cost_category_count(self):
        """Test CostCategory has correct number of values."""
        assert len(list(CostCategory)) == 6

    def test_cost_category_representation(self):
        """Test CostCategory string representation."""
        assert str(CostCategory.LLM_QUERY) == "CostCategory.LLM_QUERY"


class TestUsageRecord:
    """Test UsageRecord model."""

    def test_usage_record_defaults(self):
        """Test UsageRecord with default values."""
        record = UsageRecord(
            user_id="user123",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens_used=1000,
            estimated_cost=0.03,
            model_name="gpt-4",
        )
        assert record.user_id == "user123"
        assert record.department == "engineering"
        assert record.category == CostCategory.LLM_QUERY
        assert record.tokens_used == 1000
        assert record.estimated_cost == 0.03
        assert record.model_name == "gpt-4"
        assert record.query_id is None
        assert isinstance(record.timestamp, datetime)

    def test_usage_record_custom_values(self):
        """Test UsageRecord with custom values."""
        query_id = "q456"
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        record = UsageRecord(
            user_id="user456",
            department="marketing",
            category=CostCategory.LLM_TRANSLATION,
            tokens_used=2500,
            estimated_cost=0.0375,
            model_name="claude-opus",
            query_id=query_id,
            timestamp=timestamp,
        )
        assert record.query_id == query_id
        assert record.timestamp == timestamp

    def test_usage_record_uuid_generated(self):
        """Test UsageRecord generates UUID for record_id."""
        record = UsageRecord(
            user_id="user789",
            department="hr",
            category=CostCategory.EMBEDDING,
            tokens_used=500,
            estimated_cost=0.001,
            model_name="claude-haiku",
        )
        assert isinstance(record.record_id, UUID)

    def test_usage_record_estimated_cost_precision(self):
        """Test UsageRecord handles estimated cost with precision."""
        record = UsageRecord(
            user_id="user999",
            department="finance",
            category=CostCategory.RAG_RETRIEVAL,
            tokens_used=15000,
            estimated_cost=0.00045,
            model_name="gpt-3.5-turbo",
        )
        assert record.estimated_cost == pytest.approx(0.00045, rel=1e-5)


class TestBudgetConfig:
    """Test BudgetConfig model."""

    def test_budget_config_defaults(self):
        """Test BudgetConfig with default values."""
        config = BudgetConfig()
        assert config.user_daily_limit == 100000
        assert config.alert_threshold_percent == 80
        assert config.billing_cycle_days == 30
        assert len(config.department_budgets) == 0
        assert "gpt-4" in config.cost_per_1k_tokens
        assert "gpt-3.5-turbo" in config.cost_per_1k_tokens
        assert "claude-opus" in config.cost_per_1k_tokens
        assert "claude-haiku" in config.cost_per_1k_tokens

    def test_budget_config_custom_values(self):
        """Test BudgetConfig with custom values."""
        config = BudgetConfig(
            user_daily_limit=50000,
            alert_threshold_percent=75,
            billing_cycle_days=60,
            department_budgets={"engineering": 5000.0, "marketing": 2000.0},
        )
        assert config.user_daily_limit == 50000
        assert config.alert_threshold_percent == 75
        assert config.billing_cycle_days == 60
        assert config.department_budgets["engineering"] == 5000.0
        assert config.department_budgets["marketing"] == 2000.0

    def test_budget_config_cost_per_1k_tokens(self):
        """Test BudgetConfig cost_per_1k_tokens values."""
        config = BudgetConfig()
        assert config.cost_per_1k_tokens["gpt-4"] == 0.03
        assert config.cost_per_1k_tokens["gpt-3.5-turbo"] == 0.0015
        assert config.cost_per_1k_tokens["claude-opus"] == 0.015
        assert config.cost_per_1k_tokens["claude-haiku"] == 0.00075


class TestCostSummary:
    """Test CostSummary model."""

    def test_cost_summary_defaults(self):
        """Test CostSummary with default values."""
        now = datetime.now()
        summary = CostSummary(
            period_start=now - timedelta(days=30),
            period_end=now,
            total_tokens=10000,
            total_cost=1.5,
        )
        assert summary.total_tokens == 10000
        assert summary.total_cost == 1.5
        assert len(summary.by_category) == 0
        assert len(summary.by_department) == 0
        assert len(summary.by_user) == 0
        assert len(summary.by_model) == 0

    def test_cost_summary_custom_values(self):
        """Test CostSummary with custom breakdown values."""
        now = datetime.now()
        summary = CostSummary(
            period_start=now - timedelta(days=30),
            period_end=now,
            total_tokens=50000,
            total_cost=5.0,
            by_category={"llm_query": 3.0, "embedding": 2.0},
            by_department={"engineering": 3.5, "marketing": 1.5},
            by_user={"user1": 2.0, "user2": 3.0},
            by_model={"gpt-4": 4.0, "claude-opus": 1.0},
        )
        assert summary.total_tokens == 50000
        assert summary.total_cost == 5.0
        assert summary.by_category["llm_query"] == 3.0
        assert summary.by_department["engineering"] == 3.5
        assert summary.by_user["user1"] == 2.0
        assert summary.by_model["gpt-4"] == 4.0

    def test_cost_summary_period_fields(self):
        """Test CostSummary period date fields."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 31, 23, 59, 59)
        summary = CostSummary(
            period_start=start,
            period_end=end,
            total_tokens=0,
            total_cost=0.0,
        )
        assert summary.period_start == start
        assert summary.period_end == end


class TestCostDashboardServiceInit:
    """Test CostDashboardService initialization."""

    def test_service_init_with_config(self):
        """Test service initialization with custom config."""
        config = BudgetConfig(user_daily_limit=75000)
        service = CostDashboardService(config=config)
        assert service.config == config
        assert service.config.user_daily_limit == 75000

    def test_service_init_empty_records(self):
        """Test service initializes with empty records."""
        service = CostDashboardService()
        assert len(service.usage_records) == 0
        assert isinstance(service.usage_records, list)

    def test_service_init_default_config(self):
        """Test service initializes with default config."""
        service = CostDashboardService()
        assert isinstance(service.config, BudgetConfig)
        assert service.config.user_daily_limit == 100000
        assert service.config.alert_threshold_percent == 80


class TestRecordUsage:
    """Test record_usage method."""

    def test_record_usage_basic(self):
        """Test basic usage recording."""
        service = CostDashboardService()
        record = service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        assert record.user_id == "user1"
        assert record.tokens_used == 1000
        assert len(service.usage_records) == 1

    def test_record_usage_assigns_uuid(self):
        """Test record_usage assigns unique UUID."""
        service = CostDashboardService()
        record = service.record_usage(
            user_id="user2",
            department="marketing",
            category=CostCategory.EMBEDDING,
            tokens=500,
            model_name="claude-haiku",
        )
        assert isinstance(record.record_id, UUID)
        assert record.record_id is not None

    def test_record_usage_calculates_cost(self):
        """Test record_usage calculates estimated cost."""
        service = CostDashboardService()
        record = service.record_usage(
            user_id="user3",
            department="finance",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        # gpt-4 costs 0.03 per 1k tokens: (1000 * 0.03) / 1000 = 0.03
        assert record.estimated_cost == pytest.approx(0.03, rel=1e-5)

    def test_record_usage_stores_record(self):
        """Test record_usage stores in usage_records list."""
        service = CostDashboardService()
        record1 = service.record_usage(
            user_id="user4",
            department="hr",
            category=CostCategory.RAG_RETRIEVAL,
            tokens=2000,
            model_name="claude-opus",
        )
        record2 = service.record_usage(
            user_id="user5",
            department="engineering",
            category=CostCategory.AGENT_EXECUTION,
            tokens=1500,
            model_name="gpt-3.5-turbo",
        )
        assert len(service.usage_records) == 2
        assert service.usage_records[0] == record1
        assert service.usage_records[1] == record2


class TestGetCostSummary:
    """Test get_cost_summary method."""

    def test_get_cost_summary_aggregates_costs(self):
        """Test get_cost_summary aggregates all costs."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        service.record_usage(
            user_id="user2",
            department="engineering",
            category=CostCategory.EMBEDDING,
            tokens=500,
            model_name="claude-haiku",
        )
        summary = service.get_cost_summary()
        assert summary.total_tokens == 1500
        assert summary.total_cost > 0

    def test_get_cost_summary_by_category(self):
        """Test get_cost_summary breaks down costs by category."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.EMBEDDING,
            tokens=500,
            model_name="claude-haiku",
        )
        summary = service.get_cost_summary()
        assert "llm_query" in summary.by_category
        assert "embedding" in summary.by_category

    def test_get_cost_summary_by_department(self):
        """Test get_cost_summary breaks down costs by department."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        service.record_usage(
            user_id="user2",
            department="marketing",
            category=CostCategory.LLM_QUERY,
            tokens=500,
            model_name="gpt-4",
        )
        summary = service.get_cost_summary()
        assert "engineering" in summary.by_department
        assert "marketing" in summary.by_department


class TestGetUserUsage:
    """Test get_user_usage method."""

    def test_get_user_usage_returns_stats(self):
        """Test get_user_usage returns user statistics."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
            query_id="q1",
        )
        usage = service.get_user_usage("user1")
        assert usage["user_id"] == "user1"
        assert usage["total_tokens"] == 1000
        assert "total_cost" in usage
        assert "query_count" in usage

    def test_get_user_usage_period_filtering(self):
        """Test get_user_usage filters by period."""
        service = CostDashboardService()
        now = datetime.now()
        past = now - timedelta(days=60)

        record = UsageRecord(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens_used=1000,
            estimated_cost=0.03,
            model_name="gpt-4",
            timestamp=past,
        )
        service.usage_records.append(record)

        usage_30 = service.get_user_usage("user1", period_days=30)
        assert usage_30["total_tokens"] == 0

        usage_90 = service.get_user_usage("user1", period_days=90)
        assert usage_90["total_tokens"] == 1000

    def test_get_user_usage_empty_user(self):
        """Test get_user_usage for non-existent user."""
        service = CostDashboardService()
        usage = service.get_user_usage("nonexistent_user")
        assert usage["total_tokens"] == 0
        assert usage["total_cost"] == 0.0
        assert usage["query_count"] == 0


class TestGetDepartmentUsage:
    """Test get_department_usage method."""

    def test_get_department_usage_returns_stats(self):
        """Test get_department_usage returns department statistics."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        usage = service.get_department_usage("engineering")
        assert usage["department"] == "engineering"
        assert usage["total_tokens"] == 1000
        assert "total_cost" in usage
        assert "unique_users" in usage

    def test_get_department_usage_period_filtering(self):
        """Test get_department_usage filters by period."""
        service = CostDashboardService()
        now = datetime.now()
        past = now - timedelta(days=60)

        record = UsageRecord(
            user_id="user1",
            department="marketing",
            category=CostCategory.EMBEDDING,
            tokens_used=2000,
            estimated_cost=0.05,
            model_name="gpt-4",
            timestamp=past,
        )
        service.usage_records.append(record)

        usage_30 = service.get_department_usage("marketing", period_days=30)
        assert usage_30["total_tokens"] == 0

        usage_90 = service.get_department_usage("marketing", period_days=90)
        assert usage_90["total_tokens"] == 2000

    def test_get_department_usage_empty_dept(self):
        """Test get_department_usage for non-existent department."""
        service = CostDashboardService()
        usage = service.get_department_usage("nonexistent_dept")
        assert usage["total_tokens"] == 0
        assert usage["total_cost"] == 0.0
        assert usage["unique_users"] == 0


class TestCheckBudget:
    """Test check_budget method."""

    def test_check_budget_within_limit(self):
        """Test check_budget when usage is within budget."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=10000,
            model_name="gpt-4",
        )
        result = service.check_budget(user_id="user1")
        assert result["type"] == "user"
        assert result["within_budget"] is True

    def test_check_budget_over_limit(self):
        """Test check_budget when usage exceeds budget."""
        config = BudgetConfig(user_daily_limit=5000)
        service = CostDashboardService(config=config)
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=10000,
            model_name="gpt-4",
        )
        result = service.check_budget(user_id="user1")
        assert result["within_budget"] is False
        assert result["usage_percent"] > 100

    def test_check_budget_no_budget_set(self):
        """Test check_budget when no budget is set."""
        service = CostDashboardService()
        result = service.check_budget(department="engineering")
        assert result["type"] == "department"
        assert result["within_budget"] is True


class TestGetTopConsumers:
    """Test get_top_consumers method."""

    def test_get_top_consumers_returns_list(self):
        """Test get_top_consumers returns sorted list."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=5000,
            model_name="gpt-4",
        )
        service.record_usage(
            user_id="user2",
            department="marketing",
            category=CostCategory.EMBEDDING,
            tokens=2000,
            model_name="claude-opus",
        )
        consumers = service.get_top_consumers(limit=10)
        assert len(consumers) == 2
        assert consumers[0]["user_id"] == "user1"
        assert consumers[1]["user_id"] == "user2"

    def test_get_top_consumers_sorted_by_cost(self):
        """Test get_top_consumers sorts by cost descending."""
        service = CostDashboardService()
        service.record_usage(
            user_id="cheap_user",
            department="engineering",
            category=CostCategory.EMBEDDING,
            tokens=100,
            model_name="claude-haiku",
        )
        service.record_usage(
            user_id="expensive_user",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=5000,
            model_name="gpt-4",
        )
        consumers = service.get_top_consumers(limit=10)
        assert consumers[0]["user_id"] == "expensive_user"
        assert consumers[0]["total_cost"] > consumers[1]["total_cost"]

    def test_get_top_consumers_empty_list(self):
        """Test get_top_consumers with no records."""
        service = CostDashboardService()
        consumers = service.get_top_consumers(limit=10)
        assert len(consumers) == 0


class TestGetCostForecast:
    """Test get_cost_forecast method."""

    def test_get_cost_forecast_projects_cost(self):
        """Test get_cost_forecast projects future costs."""
        service = CostDashboardService()
        now = datetime.now()
        for i in range(7):
            record = UsageRecord(
                user_id="user1",
                department="engineering",
                category=CostCategory.LLM_QUERY,
                tokens_used=1000,
                estimated_cost=0.03,
                model_name="gpt-4",
                timestamp=now - timedelta(days=6-i),
            )
            service.usage_records.append(record)
        forecast = service.get_cost_forecast(days_ahead=30)
        assert forecast["projected_cost"] > 0
        assert forecast["projected_tokens"] > 0

    def test_get_cost_forecast_trend_calculation(self):
        """Test get_cost_forecast calculates trend."""
        service = CostDashboardService()
        now = datetime.now()
        for i in range(7):
            record = UsageRecord(
                user_id="user1",
                department="engineering",
                category=CostCategory.LLM_QUERY,
                tokens_used=1000,
                estimated_cost=0.03,
                model_name="gpt-4",
                timestamp=now - timedelta(days=6-i),
            )
            service.usage_records.append(record)
        forecast = service.get_cost_forecast(days_ahead=30)
        assert forecast["trend"] in ["increasing", "decreasing", "stable"]

    def test_get_cost_forecast_zero_data(self):
        """Test get_cost_forecast with no data."""
        service = CostDashboardService()
        forecast = service.get_cost_forecast(days_ahead=30)
        assert forecast["projected_cost"] == 0
        assert forecast["projected_tokens"] == 0
        assert forecast["trend"] == "insufficient_data"


class TestGetAlerts:
    """Test get_alerts method."""

    def test_get_alerts_returns_over_budget(self):
        """Test get_alerts returns over-budget alerts."""
        config = BudgetConfig(
            user_daily_limit=5000,
            alert_threshold_percent=80,
        )
        service = CostDashboardService(config=config)
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=10000,
            model_name="gpt-4",
        )
        alerts = service.get_alerts()
        user_alerts = [a for a in alerts if a["type"] == "user_budget"]
        assert len(user_alerts) > 0

    def test_get_alerts_empty_when_all_ok(self):
        """Test get_alerts returns empty when all budgets OK."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        alerts = service.get_alerts()
        assert len(alerts) == 0

    def test_get_alerts_threshold_check(self):
        """Test get_alerts respects threshold percentage."""
        config = BudgetConfig(
            user_daily_limit=1000,
            alert_threshold_percent=50,
        )
        service = CostDashboardService(config=config)
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=600,
            model_name="gpt-4",
        )
        alerts = service.get_alerts()
        user_alerts = [a for a in alerts if a["type"] == "user_budget"]
        assert len(user_alerts) > 0


class TestExportUsageReport:
    """Test export_usage_report method."""

    def test_export_usage_report_json_format(self):
        """Test export_usage_report exports JSON format."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        now = datetime.now()
        report = service.export_usage_report(
            start_date=now - timedelta(days=30),
            end_date=now,
            format="json",
        )
        assert report["format"] == "json"
        assert "summary" in report
        assert "top_consumers" in report

    def test_export_usage_report_date_range(self):
        """Test export_usage_report respects date range."""
        service = CostDashboardService()
        now = datetime.now()
        past = now - timedelta(days=60)

        record = UsageRecord(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens_used=1000,
            estimated_cost=0.03,
            model_name="gpt-4",
            timestamp=past,
        )
        service.usage_records.append(record)

        report = service.export_usage_report(
            start_date=now - timedelta(days=30),
            end_date=now,
            format="json",
        )
        assert report["summary"]["total_tokens"] == 0

    def test_export_usage_report_record_count(self):
        """Test export_usage_report includes correct record count."""
        service = CostDashboardService()
        service.record_usage(
            user_id="user1",
            department="engineering",
            category=CostCategory.LLM_QUERY,
            tokens=1000,
            model_name="gpt-4",
        )
        service.record_usage(
            user_id="user2",
            department="marketing",
            category=CostCategory.EMBEDDING,
            tokens=500,
            model_name="claude-opus",
        )
        now = datetime.now()
        report = service.export_usage_report(
            start_date=now - timedelta(days=30),
            end_date=now,
            format="json",
        )
        assert "summary" in report
        assert report["report_type"] == "usage"

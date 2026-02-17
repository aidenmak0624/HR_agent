"""
Cost Dashboard Service for HR Multi-Agent Platform.
Token budget and cost tracking dashboard for LLM usage.
Iteration 8 - Wave 2
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4, UUID
from pydantic import BaseModel, ConfigDict, Field
from collections import defaultdict

logger = logging.getLogger(__name__)


class CostCategory(str, Enum):
    """Cost categories for usage tracking."""

    LLM_QUERY = "llm_query"
    LLM_TRANSLATION = "llm_translation"
    LLM_SUMMARIZATION = "llm_summarization"
    RAG_RETRIEVAL = "rag_retrieval"
    AGENT_EXECUTION = "agent_execution"
    EMBEDDING = "embedding"


class UsageRecord(BaseModel):
    """Usage record for cost tracking."""

    record_id: UUID = Field(
        default_factory=uuid4, description="Unique record identifier"
    )
    user_id: str = Field(description="User ID")
    department: str = Field(description="Department name")
    category: CostCategory = Field(description="Cost category")
    tokens_used: int = Field(description="Number of tokens used")
    estimated_cost: float = Field(description="Estimated cost in dollars")
    model_name: str = Field(description="LLM model name")
    query_id: Optional[str] = Field(default=None, description="Associated query ID")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Record timestamp"
    )

    model_config = ConfigDict(frozen=False)


class BudgetConfig(BaseModel):
    """Budget configuration for cost control."""

    department_budgets: Dict[str, float] = Field(
        default_factory=dict, description="Department budgets in dollars"
    )
    user_daily_limit: int = Field(
        default=100000, description="Daily token limit per user"
    )
    alert_threshold_percent: int = Field(
        default=80, description="Alert threshold percentage"
    )
    billing_cycle_days: int = Field(default=30, description="Billing cycle duration")
    cost_per_1k_tokens: Dict[str, float] = Field(
        default_factory=lambda: {
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.0015,
            "claude-opus": 0.015,
            "claude-haiku": 0.00075,
        },
        description="Cost per 1k tokens by model",
    )

    model_config = ConfigDict(frozen=False)


class CostSummary(BaseModel):
    """Summary of costs for a period."""

    period_start: datetime = Field(description="Period start date")
    period_end: datetime = Field(description="Period end date")
    total_tokens: int = Field(description="Total tokens used")
    total_cost: float = Field(description="Total cost in dollars")
    by_category: Dict[str, float] = Field(
        default_factory=dict, description="Cost breakdown by category"
    )
    by_department: Dict[str, float] = Field(
        default_factory=dict, description="Cost breakdown by department"
    )
    by_user: Dict[str, float] = Field(
        default_factory=dict, description="Cost breakdown by user"
    )
    by_model: Dict[str, float] = Field(
        default_factory=dict, description="Cost breakdown by model"
    )

    model_config = ConfigDict(frozen=False)


class CostDashboardService:
    """
    Cost Dashboard Service.
    Tracks LLM token usage and manages budgets for the HR platform.
    """

    def __init__(self, config: Optional[BudgetConfig] = None) -> None:
        """
        Initialize cost dashboard service.

        Args:
            config: Budget configuration (uses defaults if None)
        """
        self.config = config or BudgetConfig()
        self.usage_records: List[UsageRecord] = []
        self.user_budgets: Dict[str, float] = {}
        self.usage_alerts: List[Dict[str, Any]] = []

        logger.info(
            "Cost dashboard service initialized",
            extra={
                "departments": len(self.config.department_budgets),
                "user_daily_limit": self.config.user_daily_limit,
                "alert_threshold": self.config.alert_threshold_percent,
            },
        )

    def record_usage(
        self,
        user_id: str,
        department: str,
        category: CostCategory,
        tokens: int,
        model_name: str,
        query_id: Optional[str] = None,
    ) -> UsageRecord:
        """
        Record usage event for cost tracking.

        Args:
            user_id: User ID
            department: Department name
            category: Cost category
            tokens: Number of tokens used
            model_name: LLM model name
            query_id: Optional associated query ID

        Returns:
            Created UsageRecord
        """
        try:
            # Calculate cost
            cost_per_token = self.config.cost_per_1k_tokens.get(model_name, 0.001)
            estimated_cost = (tokens * cost_per_token) / 1000

            # Create record
            record = UsageRecord(
                user_id=user_id,
                department=department,
                category=category,
                tokens_used=tokens,
                estimated_cost=estimated_cost,
                model_name=model_name,
                query_id=query_id,
            )

            self.usage_records.append(record)

            # Check budget thresholds
            self._check_budget_threshold(user_id, department)

            logger.debug(
                "Usage recorded",
                extra={
                    "record_id": str(record.record_id),
                    "user_id": user_id,
                    "tokens": tokens,
                    "cost": estimated_cost,
                    "model": model_name,
                },
            )

            return record

        except Exception as e:
            logger.error(
                "Failed to record usage",
                extra={"user_id": user_id, "error": str(e)},
            )
            raise

    def get_cost_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> CostSummary:
        """
        Get cost summary for a period.

        Args:
            start_date: Period start (default: 30 days ago)
            end_date: Period end (default: now)

        Returns:
            CostSummary with aggregated data
        """
        try:
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                start_date = end_date - timedelta(
                    days=self.config.billing_cycle_days
                )

            # Filter records by date range
            filtered_records = [
                r
                for r in self.usage_records
                if start_date <= r.timestamp <= end_date
            ]

            # Aggregate data
            total_tokens = sum(r.tokens_used for r in filtered_records)
            total_cost = sum(r.estimated_cost for r in filtered_records)

            by_category = defaultdict(float)
            by_department = defaultdict(float)
            by_user = defaultdict(float)
            by_model = defaultdict(float)

            for record in filtered_records:
                by_category[record.category.value] += record.estimated_cost
                by_department[record.department] += record.estimated_cost
                by_user[record.user_id] += record.estimated_cost
                by_model[record.model_name] += record.estimated_cost

            return CostSummary(
                period_start=start_date,
                period_end=end_date,
                total_tokens=total_tokens,
                total_cost=total_cost,
                by_category=dict(by_category),
                by_department=dict(by_department),
                by_user=dict(by_user),
                by_model=dict(by_model),
            )

        except Exception as e:
            logger.error(
                "Failed to generate cost summary",
                extra={"error": str(e)},
            )
            raise

    def get_user_usage(
        self, user_id: str, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage details for a specific user.

        Args:
            user_id: User ID
            period_days: Period to analyze in days

        Returns:
            Dictionary with user usage details
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            user_records = [
                r
                for r in self.usage_records
                if r.user_id == user_id and start_date <= r.timestamp <= end_date
            ]

            total_tokens = sum(r.tokens_used for r in user_records)
            total_cost = sum(r.estimated_cost for r in user_records)
            query_count = len(set(r.query_id for r in user_records if r.query_id))

            by_category = defaultdict(float)
            for record in user_records:
                by_category[record.category.value] += record.estimated_cost

            return {
                "user_id": user_id,
                "period_days": period_days,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "query_count": query_count,
                "avg_cost_per_query": (
                    round(total_cost / query_count, 4) if query_count > 0 else 0
                ),
                "by_category": dict(by_category),
                "daily_average_tokens": round(total_tokens / period_days, 2),
            }

        except Exception as e:
            logger.error(
                "Failed to get user usage",
                extra={"user_id": user_id, "error": str(e)},
            )
            raise

    def get_department_usage(
        self, department: str, period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage details for a department.

        Args:
            department: Department name
            period_days: Period to analyze in days

        Returns:
            Dictionary with department usage details
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            dept_records = [
                r
                for r in self.usage_records
                if r.department == department
                and start_date <= r.timestamp <= end_date
            ]

            total_tokens = sum(r.tokens_used for r in dept_records)
            total_cost = sum(r.estimated_cost for r in dept_records)
            budget = self.config.department_budgets.get(department, 0)

            unique_users = len(set(r.user_id for r in dept_records))

            by_category = defaultdict(float)
            for record in dept_records:
                by_category[record.category.value] += record.estimated_cost

            return {
                "department": department,
                "period_days": period_days,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "budget": budget,
                "budget_used_percent": (
                    round((total_cost / budget * 100), 2) if budget > 0 else 0
                ),
                "unique_users": unique_users,
                "by_category": dict(by_category),
            }

        except Exception as e:
            logger.error(
                "Failed to get department usage",
                extra={"department": department, "error": str(e)},
            )
            raise

    def check_budget(
        self,
        user_id: Optional[str] = None,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Check budget status for user or department.

        Args:
            user_id: User ID (optional)
            department: Department name (optional)

        Returns:
            Dictionary with budget status
        """
        try:
            if user_id:
                user_usage = self.get_user_usage(user_id, period_days=1)
                daily_tokens = user_usage["total_tokens"]
                token_limit = self.config.user_daily_limit
                usage_percent = round(
                    (daily_tokens / token_limit * 100), 2) if token_limit > 0 else 0

                return {
                    "type": "user",
                    "identifier": user_id,
                    "within_budget": daily_tokens <= token_limit,
                    "usage_percent": usage_percent,
                    "tokens_used": daily_tokens,
                    "token_limit": token_limit,
                    "tokens_remaining": max(0, token_limit - daily_tokens),
                }

            elif department:
                dept_usage = self.get_department_usage(
                    department, period_days=self.config.billing_cycle_days
                )
                cost = dept_usage["total_cost"]
                budget = dept_usage["budget"]
                within_budget = cost <= budget if budget > 0 else True

                return {
                    "type": "department",
                    "identifier": department,
                    "within_budget": within_budget,
                    "usage_percent": dept_usage["budget_used_percent"],
                    "cost_used": round(cost, 4),
                    "budget": budget,
                    "cost_remaining": round(max(0, budget - cost), 4),
                }

            return {"error": "user_id or department must be specified"}

        except Exception as e:
            logger.error(
                "Failed to check budget",
                extra={"user_id": user_id, "department": department, "error": str(e)},
            )
            raise

    def get_top_consumers(
        self, limit: int = 10, period_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get top token consumers.

        Args:
            limit: Maximum number of consumers to return
            period_days: Period to analyze in days

        Returns:
            List of top consumers
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            filtered_records = [
                r
                for r in self.usage_records
                if start_date <= r.timestamp <= end_date
            ]

            user_costs = defaultdict(float)
            user_tokens = defaultdict(int)

            for record in filtered_records:
                user_costs[record.user_id] += record.estimated_cost
                user_tokens[record.user_id] += record.tokens_used

            consumers = [
                {
                    "user_id": user_id,
                    "total_cost": round(cost, 4),
                    "total_tokens": user_tokens[user_id],
                }
                for user_id, cost in sorted(
                    user_costs.items(), key=lambda x: x[1], reverse=True
                )[:limit]
            ]

            return consumers

        except Exception as e:
            logger.error(
                "Failed to get top consumers",
                extra={"error": str(e)},
            )
            raise

    def get_cost_forecast(
        self, days_ahead: int = 30
    ) -> Dict[str, Any]:
        """
        Forecast future costs based on recent trends.

        Args:
            days_ahead: Number of days to forecast

        Returns:
            Dictionary with cost forecast
        """
        try:
            # Use last 7 days as basis
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            recent_records = [
                r
                for r in self.usage_records
                if start_date <= r.timestamp <= end_date
            ]

            if not recent_records:
                return {
                    "projected_cost": 0,
                    "projected_tokens": 0,
                    "trend": "insufficient_data",
                }

            daily_cost = sum(r.estimated_cost for r in recent_records) / 7
            daily_tokens = sum(r.tokens_used for r in recent_records) / 7

            projected_cost = daily_cost * days_ahead
            projected_tokens = int(daily_tokens * days_ahead)

            # Determine trend
            if len(recent_records) > 1:
                recent_half = recent_records[len(recent_records) // 2 :]
                early_half = recent_records[: len(recent_records) // 2]
                recent_avg = (
                    sum(r.estimated_cost for r in recent_half) / len(recent_half)
                    if recent_half
                    else 0
                )
                early_avg = (
                    sum(r.estimated_cost for r in early_half) / len(early_half)
                    if early_half
                    else 0
                )
                trend = (
                    "increasing"
                    if recent_avg > early_avg
                    else "decreasing" if recent_avg < early_avg else "stable"
                )
            else:
                trend = "stable"

            return {
                "period_days": days_ahead,
                "projected_cost": round(projected_cost, 4),
                "projected_tokens": projected_tokens,
                "daily_average_cost": round(daily_cost, 4),
                "daily_average_tokens": int(daily_tokens),
                "trend": trend,
                "basis_days": 7,
            }

        except Exception as e:
            logger.error(
                "Failed to generate cost forecast",
                extra={"error": str(e)},
            )
            raise

    def set_department_budget(
        self, department: str, budget_amount: float
    ) -> Dict[str, Any]:
        """
        Set or update department budget.

        Args:
            department: Department name
            budget_amount: Budget amount in dollars

        Returns:
            Updated budget configuration
        """
        try:
            if budget_amount < 0:
                raise ValueError("Budget amount must be non-negative")

            self.config.department_budgets[department] = budget_amount

            logger.info(
                "Department budget updated",
                extra={
                    "department": department,
                    "budget": budget_amount,
                },
            )

            return {
                "department": department,
                "budget": budget_amount,
                "status": "updated",
            }

        except Exception as e:
            logger.error(
                "Failed to set department budget",
                extra={"department": department, "error": str(e)},
            )
            raise

    def get_alerts(self) -> List[Dict[str, Any]]:
        """
        Get budget alert list.

        Returns:
            List of active alerts
        """
        try:
            alerts = []

            # Check user budgets
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)

            user_daily_usage = defaultdict(int)
            for record in self.usage_records:
                if start_date <= record.timestamp <= end_date:
                    user_daily_usage[record.user_id] += record.tokens_used

            for user_id, tokens in user_daily_usage.items():
                percent = (tokens / self.config.user_daily_limit * 100) if self.config.user_daily_limit > 0 else 0
                if percent >= self.config.alert_threshold_percent:
                    alerts.append(
                        {
                            "type": "user_budget",
                            "user_id": user_id,
                            "severity": "critical" if percent >= 100 else "warning",
                            "usage_percent": round(percent, 2),
                            "timestamp": datetime.now(),
                        }
                    )

            # Check department budgets
            start_date = end_date - timedelta(
                days=self.config.billing_cycle_days
            )
            dept_costs = defaultdict(float)
            for record in self.usage_records:
                if start_date <= record.timestamp <= end_date:
                    dept_costs[record.department] += record.estimated_cost

            for dept, cost in dept_costs.items():
                budget = self.config.department_budgets.get(dept, 0)
                if budget > 0:
                    percent = (cost / budget * 100)
                    if percent >= self.config.alert_threshold_percent:
                        alerts.append(
                            {
                                "type": "department_budget",
                                "department": dept,
                                "severity": (
                                    "critical" if percent >= 100 else "warning"
                                ),
                                "usage_percent": round(percent, 2),
                                "timestamp": datetime.now(),
                            }
                        )

            return alerts

        except Exception as e:
            logger.error(
                "Failed to get alerts",
                extra={"error": str(e)},
            )
            raise

    def get_model_cost_comparison(self) -> Dict[str, Any]:
        """
        Get cost comparison across models.

        Returns:
            Dictionary with model cost analysis
        """
        try:
            model_costs = defaultdict(float)
            model_tokens = defaultdict(int)
            model_queries = defaultdict(int)

            for record in self.usage_records:
                model_costs[record.model_name] += record.estimated_cost
                model_tokens[record.model_name] += record.tokens_used
                model_queries[record.model_name] += 1

            comparison = {}
            for model in model_costs:
                comparison[model] = {
                    "total_cost": round(model_costs[model], 4),
                    "total_tokens": model_tokens[model],
                    "query_count": model_queries[model],
                    "avg_cost_per_query": round(
                        model_costs[model] / model_queries[model], 6
                    ),
                    "cost_per_1k_tokens": self.config.cost_per_1k_tokens.get(
                        model, 0.001
                    ),
                }

            return {
                "models": comparison,
                "most_expensive": max(
                    comparison.items(),
                    key=lambda x: x[1]["total_cost"],
                    default=(None, {}),
                )[0],
                "most_used": max(
                    comparison.items(),
                    key=lambda x: x[1]["total_tokens"],
                    default=(None, {}),
                )[0],
            }

        except Exception as e:
            logger.error(
                "Failed to get model cost comparison",
                extra={"error": str(e)},
            )
            raise

    def export_usage_report(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = "json",
    ) -> Dict[str, Any]:
        """
        Export detailed usage report.

        Args:
            start_date: Report start date
            end_date: Report end date
            format: Export format (json, csv, summary)

        Returns:
            Dictionary with report data
        """
        try:
            summary = self.get_cost_summary(start_date, end_date)
            model_comparison = self.get_model_cost_comparison()
            top_consumers = self.get_top_consumers(limit=20)

            report = {
                "report_type": "usage",
                "generated_at": datetime.now().isoformat(),
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "summary": {
                    "total_tokens": summary.total_tokens,
                    "total_cost": round(summary.total_cost, 4),
                    "by_category": {
                        k: round(v, 4) for k, v in summary.by_category.items()
                    },
                    "by_department": {
                        k: round(v, 4) for k, v in summary.by_department.items()
                    },
                },
                "top_consumers": top_consumers,
                "model_analysis": model_comparison,
                "format": format,
            }

            return report

        except Exception as e:
            logger.error(
                "Failed to export usage report",
                extra={"error": str(e)},
            )
            raise

    def _check_budget_threshold(self, user_id: str, department: str) -> None:
        """
        Check if budget threshold is exceeded.

        Args:
            user_id: User ID
            department: Department name
        """
        try:
            budget_check = self.check_budget(user_id=user_id)
            if not budget_check.get("within_budget", True):
                self.usage_alerts.append(
                    {
                        "type": "user_budget_exceeded",
                        "user_id": user_id,
                        "timestamp": datetime.now(),
                        "usage_percent": budget_check.get("usage_percent", 0),
                    }
                )

            dept_check = self.check_budget(department=department)
            if not dept_check.get("within_budget", True):
                self.usage_alerts.append(
                    {
                        "type": "department_budget_exceeded",
                        "department": department,
                        "timestamp": datetime.now(),
                        "usage_percent": dept_check.get("usage_percent", 0),
                    }
                )

        except Exception as e:
            logger.debug(
                "Error checking budget threshold",
                extra={"user_id": user_id, "error": str(e)},
            )

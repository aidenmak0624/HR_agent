"""
SLA Monitor Service for HR Multi-Agent Platform.
SLA monitoring and uptime tracking.
Iteration 8 - Wave 2
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4, UUID
from pydantic import BaseModel, ConfigDict, Field
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class SLAMetric(str, Enum):
    """SLA metrics to monitor."""

    UPTIME = "uptime"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    AVAILABILITY = "availability"


class SLATier(str, Enum):
    """SLA service tiers."""

    PLATINUM = "platinum"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"


class SLATarget(BaseModel):
    """SLA target specification."""

    metric: SLAMetric = Field(description="Metric type")
    target_value: float = Field(description="Target value")
    tier: SLATier = Field(description="Service tier")
    measurement_window_hours: int = Field(default=24, description="Measurement window in hours")
    breach_notification: bool = Field(default=True, description="Send notification on breach")

    model_config = ConfigDict(frozen=False)


class SLAMeasurement(BaseModel):
    """Individual SLA measurement."""

    measurement_id: UUID = Field(default_factory=uuid4, description="Unique measurement identifier")
    metric: SLAMetric = Field(description="Metric type")
    value: float = Field(description="Measured value")
    timestamp: datetime = Field(default_factory=datetime.now, description="Measurement timestamp")
    is_within_target: bool = Field(description="Within target threshold")
    target_value: float = Field(description="Target value")

    model_config = ConfigDict(frozen=False)


class SLAIncident(BaseModel):
    """SLA incident record."""

    incident_id: UUID = Field(default_factory=uuid4, description="Unique incident identifier")
    metric: SLAMetric = Field(description="Affected metric")
    severity: str = Field(description="Severity level (warning/critical)")
    started_at: datetime = Field(description="Incident start time")
    resolved_at: Optional[datetime] = Field(default=None, description="Incident resolution time")
    duration_seconds: Optional[int] = Field(default=None, description="Duration in seconds")
    impact_description: str = Field(description="Impact description")
    resolution_notes: Optional[str] = Field(default=None, description="Resolution notes")

    model_config = ConfigDict(frozen=False)


class SLAConfig(BaseModel):
    """SLA monitoring configuration."""

    targets: List[SLATarget] = Field(default_factory=list, description="SLA targets")
    measurement_interval_seconds: int = Field(
        default=60, description="Measurement interval in seconds"
    )
    incident_auto_resolve_minutes: int = Field(
        default=30, description="Auto-resolve incident after minutes"
    )
    report_generation_enabled: bool = Field(default=True, description="Enable report generation")

    model_config = ConfigDict(frozen=False)


class SLAMonitorService:
    """
    SLA Monitor Service.
    Tracks service level agreements and uptime metrics.
    """

    def __init__(self, config: Optional[SLAConfig] = None) -> None:
        """
        Initialize SLA monitor service.

        Args:
            config: SLA configuration (uses defaults if None)
        """
        self.config = config or SLAConfig()
        self.measurements: List[SLAMeasurement] = []
        self.incidents: List[SLAIncident] = []
        self.check_history: List[Dict[str, Any]] = []

        logger.info(
            "SLA monitor service initialized",
            extra={
                "targets": len(self.config.targets),
                "measurement_interval": self.config.measurement_interval_seconds,
            },
        )

    def record_measurement(self, metric: SLAMetric, value: float) -> SLAMeasurement:
        """
        Record an SLA measurement.

        Args:
            metric: Metric type
            value: Measured value

        Returns:
            Created SLAMeasurement
        """
        try:
            # Find target for this metric
            target = next(
                (t for t in self.config.targets if t.metric == metric),
                None,
            )

            is_within_target = True
            target_value = 0.0

            if target:
                target_value = target.target_value
                # Check if within target (logic depends on metric)
                if metric == SLAMetric.UPTIME or metric == SLAMetric.AVAILABILITY:
                    is_within_target = value >= target_value
                elif metric == SLAMetric.RESPONSE_TIME:
                    is_within_target = value <= target_value
                elif metric == SLAMetric.ERROR_RATE:
                    is_within_target = value <= target_value
                elif metric == SLAMetric.THROUGHPUT:
                    is_within_target = value >= target_value

                # Create incident if breached
                if not is_within_target and target.breach_notification:
                    self._create_breach_incident(metric, value, target_value)

            measurement = SLAMeasurement(
                metric=metric,
                value=value,
                is_within_target=is_within_target,
                target_value=target_value,
            )

            self.measurements.append(measurement)

            logger.debug(
                "SLA measurement recorded",
                extra={
                    "metric": metric.value,
                    "value": value,
                    "within_target": is_within_target,
                },
            )

            return measurement

        except Exception as e:
            logger.error(
                "Failed to record SLA measurement",
                extra={"metric": metric.value if metric else None, "error": str(e)},
            )
            raise

    def get_current_sla_status(self) -> Dict[str, Any]:
        """
        Get current SLA status for all metrics.

        Returns:
            Dictionary with current status per metric
        """
        try:
            status = {}

            for target in self.config.targets:
                metric = target.metric
                # Get recent measurements for this metric
                recent = [
                    m
                    for m in self.measurements
                    if m.metric == metric
                    and m.timestamp
                    >= datetime.now() - timedelta(hours=target.measurement_window_hours)
                ]

                if recent:
                    latest = recent[-1]
                    compliant = sum(1 for m in recent if m.is_within_target) / len(recent)

                    status[metric.value] = {
                        "current_value": latest.value,
                        "target_value": target.target_value,
                        "within_target": latest.is_within_target,
                        "compliance_percent": round(compliant * 100, 2),
                        "tier": target.tier.value,
                        "measurement_count": len(recent),
                    }
                else:
                    status[metric.value] = {
                        "current_value": None,
                        "target_value": target.target_value,
                        "within_target": None,
                        "compliance_percent": 0,
                        "tier": target.tier.value,
                        "measurement_count": 0,
                    }

            return status

        except Exception as e:
            logger.error(
                "Failed to get SLA status",
                extra={"error": str(e)},
            )
            raise

    def check_sla_compliance(self, metric: Optional[SLAMetric] = None) -> Dict[str, Any]:
        """
        Check SLA compliance.

        Args:
            metric: Specific metric to check (all if None)

        Returns:
            Dictionary with compliance details
        """
        try:
            status = self.get_current_sla_status()

            if metric:
                metric_status = status.get(metric.value, {})
                compliant = metric_status.get("within_target", False)
                return {
                    "compliant": compliant,
                    "metric": metric.value,
                    "details": metric_status,
                }

            # Check all metrics
            all_compliant = all(s.get("within_target", False) for s in status.values())

            return {
                "compliant": all_compliant,
                "metrics": status,
                "compliant_count": sum(1 for s in status.values() if s.get("within_target", False)),
                "total_count": len(status),
            }

        except Exception as e:
            logger.error(
                "Failed to check SLA compliance",
                extra={"metric": metric.value if metric else None, "error": str(e)},
            )
            raise

    def get_uptime(self, period_hours: int = 24) -> Dict[str, Any]:
        """
        Get uptime metrics for a period.

        Args:
            period_hours: Period to analyze in hours

        Returns:
            Dictionary with uptime data
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=period_hours)

            uptime_measurements = [
                m
                for m in self.measurements
                if m.metric == SLAMetric.UPTIME and start_date <= m.timestamp <= end_date
            ]

            if not uptime_measurements:
                return {
                    "uptime_percent": 0,
                    "total_checks": 0,
                    "failed_checks": 0,
                }

            uptime_values = [m.value for m in uptime_measurements]
            avg_uptime = statistics.mean(uptime_values)
            failed = sum(1 for m in uptime_measurements if not m.is_within_target)

            return {
                "uptime_percent": round(avg_uptime, 4),
                "total_checks": len(uptime_measurements),
                "failed_checks": failed,
                "min_uptime": round(min(uptime_values), 4),
                "max_uptime": round(max(uptime_values), 4),
                "period_hours": period_hours,
            }

        except Exception as e:
            logger.error(
                "Failed to get uptime metrics",
                extra={"error": str(e)},
            )
            raise

    def get_response_time_percentiles(self, period_hours: int = 24) -> Dict[str, Any]:
        """
        Get response time percentiles.

        Args:
            period_hours: Period to analyze in hours

        Returns:
            Dictionary with percentile data
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=period_hours)

            rt_measurements = [
                m
                for m in self.measurements
                if m.metric == SLAMetric.RESPONSE_TIME and start_date <= m.timestamp <= end_date
            ]

            if not rt_measurements:
                return {
                    "p50": 0,
                    "p95": 0,
                    "p99": 0,
                    "avg": 0,
                    "min": 0,
                    "max": 0,
                }

            values = sorted([m.value for m in rt_measurements])

            return {
                "p50": round(values[len(values) // 2], 4),
                "p95": round(values[int(len(values) * 0.95)], 4),
                "p99": round(values[int(len(values) * 0.99)], 4),
                "avg": round(statistics.mean(values), 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "measurement_count": len(rt_measurements),
                "period_hours": period_hours,
            }

        except Exception as e:
            logger.error(
                "Failed to get response time percentiles",
                extra={"error": str(e)},
            )
            raise

    def get_error_rate(self, period_hours: int = 24) -> Dict[str, Any]:
        """
        Get error rate metrics.

        Args:
            period_hours: Period to analyze in hours

        Returns:
            Dictionary with error rate data
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=period_hours)

            error_measurements = [
                m
                for m in self.measurements
                if m.metric == SLAMetric.ERROR_RATE and start_date <= m.timestamp <= end_date
            ]

            if not error_measurements:
                return {
                    "rate": 0,
                    "total_requests": 0,
                    "total_errors": 0,
                }

            # Assume value = error_rate percentage
            avg_error_rate = statistics.mean([m.value for m in error_measurements])
            error_count = sum(1 for m in error_measurements if not m.is_within_target)

            return {
                "rate": round(avg_error_rate, 4),
                "measurement_count": len(error_measurements),
                "breaches": error_count,
                "avg_rate": round(avg_error_rate, 4),
                "period_hours": period_hours,
            }

        except Exception as e:
            logger.error(
                "Failed to get error rate",
                extra={"error": str(e)},
            )
            raise

    def create_incident(
        self,
        metric: SLAMetric,
        severity: str,
        description: str,
    ) -> SLAIncident:
        """
        Create an SLA incident.

        Args:
            metric: Affected metric
            severity: Severity level (warning/critical)
            description: Impact description

        Returns:
            Created SLAIncident
        """
        try:
            incident = SLAIncident(
                metric=metric,
                severity=severity,
                started_at=datetime.now(),
                impact_description=description,
            )

            self.incidents.append(incident)

            logger.warning(
                "SLA incident created",
                extra={
                    "incident_id": str(incident.incident_id),
                    "metric": metric.value,
                    "severity": severity,
                },
            )

            return incident

        except Exception as e:
            logger.error(
                "Failed to create incident",
                extra={"metric": metric.value if metric else None, "error": str(e)},
            )
            raise

    def resolve_incident(
        self,
        incident_id: UUID,
        notes: Optional[str] = None,
    ) -> Optional[SLAIncident]:
        """
        Resolve an SLA incident.

        Args:
            incident_id: Incident ID
            notes: Resolution notes

        Returns:
            Resolved incident or None
        """
        try:
            for incident in self.incidents:
                if incident.incident_id == incident_id:
                    incident.resolved_at = datetime.now()
                    incident.duration_seconds = int(
                        (incident.resolved_at - incident.started_at).total_seconds()
                    )
                    incident.resolution_notes = notes

                    logger.info(
                        "SLA incident resolved",
                        extra={
                            "incident_id": str(incident_id),
                            "duration_seconds": incident.duration_seconds,
                        },
                    )

                    return incident

            return None

        except Exception as e:
            logger.error(
                "Failed to resolve incident",
                extra={"incident_id": str(incident_id), "error": str(e)},
            )
            raise

    def get_active_incidents(self) -> List[SLAIncident]:
        """
        Get active incidents.

        Returns:
            List of unresolved incidents
        """
        try:
            active = [i for i in self.incidents if i.resolved_at is None]
            return active

        except Exception as e:
            logger.error(
                "Failed to get active incidents",
                extra={"error": str(e)},
            )
            raise

    def get_incident_history(self, period_days: int = 30) -> List[SLAIncident]:
        """
        Get incident history for a period.

        Args:
            period_days: Period to retrieve in days

        Returns:
            List of incidents
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            history = [i for i in self.incidents if start_date <= i.started_at <= end_date]

            return sorted(history, key=lambda x: x.started_at, reverse=True)

        except Exception as e:
            logger.error(
                "Failed to get incident history",
                extra={"error": str(e)},
            )
            raise

    def generate_sla_report(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Generate comprehensive SLA report.

        Args:
            period_days: Period to report in days

        Returns:
            Dictionary with SLA report
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            # Get metrics for period
            period_measurements = [
                m for m in self.measurements if start_date <= m.timestamp <= end_date
            ]

            # Get incidents for period
            period_incidents = self.get_incident_history(period_days)

            # Calculate metrics
            status = self.get_current_sla_status()
            uptime = self.get_uptime(period_hours=period_days * 24)

            compliance_by_metric = defaultdict(list)
            for m in period_measurements:
                if m.is_within_target:
                    compliance_by_metric[m.metric.value].append(1)
                else:
                    compliance_by_metric[m.metric.value].append(0)

            metric_compliance = {
                k: round(sum(v) / len(v) * 100 if v else 0, 2)
                for k, v in compliance_by_metric.items()
            }

            critical_incidents = sum(1 for i in period_incidents if i.severity == "critical")
            warning_incidents = sum(1 for i in period_incidents if i.severity == "warning")

            return {
                "report_period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "days": period_days,
                },
                "generated_at": datetime.now().isoformat(),
                "overall_compliance": round(
                    statistics.mean(metric_compliance.values()) if metric_compliance else 0,
                    2,
                ),
                "metric_compliance": metric_compliance,
                "uptime": uptime["uptime_percent"],
                "incidents": {
                    "total": len(period_incidents),
                    "critical": critical_incidents,
                    "warning": warning_incidents,
                    "resolved": sum(1 for i in period_incidents if i.resolved_at is not None),
                },
                "current_status": status,
            }

        except Exception as e:
            logger.error(
                "Failed to generate SLA report",
                extra={"error": str(e)},
            )
            raise

    def get_sla_trends(self, metric: SLAMetric, period_days: int = 30) -> Dict[str, Any]:
        """
        Get SLA trends for a metric.

        Args:
            metric: Metric to analyze
            period_days: Period to analyze in days

        Returns:
            Dictionary with trend data
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)

            metric_measurements = [
                m
                for m in self.measurements
                if m.metric == metric and start_date <= m.timestamp <= end_date
            ]

            if not metric_measurements:
                return {
                    "metric": metric.value,
                    "trend": "insufficient_data",
                    "daily_averages": {},
                }

            # Group by day
            daily_data = defaultdict(list)
            for m in metric_measurements:
                day_key = m.timestamp.date().isoformat()
                daily_data[day_key].append(m.value)

            daily_averages = {
                day: round(statistics.mean(values), 4) for day, values in sorted(daily_data.items())
            }

            # Determine trend
            if len(daily_averages) > 1:
                values_list = list(daily_averages.values())
                first_half_avg = statistics.mean(values_list[: len(values_list) // 2])
                second_half_avg = statistics.mean(values_list[len(values_list) // 2 :])
                trend = (
                    "improving"
                    if second_half_avg > first_half_avg
                    else "degrading"
                    if second_half_avg < first_half_avg
                    else "stable"
                )
            else:
                trend = "insufficient_data"

            return {
                "metric": metric.value,
                "period_days": period_days,
                "daily_averages": daily_averages,
                "overall_average": round(statistics.mean(m.value for m in metric_measurements), 4),
                "trend": trend,
                "measurement_count": len(metric_measurements),
            }

        except Exception as e:
            logger.error(
                "Failed to get SLA trends",
                extra={"metric": metric.value if metric else None, "error": str(e)},
            )
            raise

    def _create_breach_incident(
        self,
        metric: SLAMetric,
        value: float,
        target: float,
    ) -> None:
        """
        Create incident for SLA breach.

        Args:
            metric: Breached metric
            value: Measured value
            target: Target value
        """
        try:
            severity = "critical" if abs(value - target) > target * 0.5 else "warning"

            description = f"{metric.value} breach: {value} vs target {target}"

            self.create_incident(
                metric=metric,
                severity=severity,
                description=description,
            )

        except Exception as e:
            logger.debug(
                "Error creating breach incident",
                extra={"metric": metric.value, "error": str(e)},
            )

"""
Unit tests for SLA Monitor Service - Iteration 8 Wave 2.
Tests for SLA monitoring and uptime tracking.
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID
from unittest.mock import Mock, patch

from src.platform_services.sla_monitor import (
    SLAMetric,
    SLATier,
    SLATarget,
    SLAMeasurement,
    SLAIncident,
    SLAConfig,
    SLAMonitorService,
)


class TestSLAMetric:
    """Test SLAMetric enum."""

    def test_sla_metric_enum_values(self):
        """Test all SLAMetric enum values exist."""
        assert SLAMetric.UPTIME.value == "uptime"
        assert SLAMetric.RESPONSE_TIME.value == "response_time"
        assert SLAMetric.ERROR_RATE.value == "error_rate"
        assert SLAMetric.THROUGHPUT.value == "throughput"
        assert SLAMetric.AVAILABILITY.value == "availability"

    def test_sla_metric_count(self):
        """Test SLAMetric has correct number of values."""
        assert len(list(SLAMetric)) == 5

    def test_sla_metric_representation(self):
        """Test SLAMetric string representation."""
        assert str(SLAMetric.UPTIME) == "SLAMetric.UPTIME"


class TestSLATier:
    """Test SLATier enum."""

    def test_sla_tier_enum_values(self):
        """Test all SLATier enum values exist."""
        assert SLATier.PLATINUM.value == "platinum"
        assert SLATier.GOLD.value == "gold"
        assert SLATier.SILVER.value == "silver"
        assert SLATier.BRONZE.value == "bronze"

    def test_sla_tier_count(self):
        """Test SLATier has correct number of values."""
        assert len(list(SLATier)) == 4

    def test_sla_tier_representation(self):
        """Test SLATier string representation."""
        assert str(SLATier.PLATINUM) == "SLATier.PLATINUM"


class TestSLATarget:
    """Test SLATarget model."""

    def test_sla_target_defaults(self):
        """Test SLATarget with default values."""
        target = SLATarget(
            metric=SLAMetric.UPTIME,
            target_value=99.9,
            tier=SLATier.GOLD,
        )
        assert target.metric == SLAMetric.UPTIME
        assert target.target_value == 99.9
        assert target.tier == SLATier.GOLD
        assert target.measurement_window_hours == 24
        assert target.breach_notification is True

    def test_sla_target_custom_values(self):
        """Test SLATarget with custom values."""
        target = SLATarget(
            metric=SLAMetric.RESPONSE_TIME,
            target_value=500.0,
            tier=SLATier.PLATINUM,
            measurement_window_hours=12,
            breach_notification=False,
        )
        assert target.metric == SLAMetric.RESPONSE_TIME
        assert target.target_value == 500.0
        assert target.measurement_window_hours == 12
        assert target.breach_notification is False

    def test_sla_target_value(self):
        """Test SLATarget target_value field."""
        target = SLATarget(
            metric=SLAMetric.ERROR_RATE,
            target_value=0.1,
            tier=SLATier.SILVER,
        )
        assert target.target_value == pytest.approx(0.1, rel=1e-5)


class TestSLAMeasurement:
    """Test SLAMeasurement model."""

    def test_sla_measurement_defaults(self):
        """Test SLAMeasurement with default values."""
        measurement = SLAMeasurement(
            metric=SLAMetric.UPTIME,
            value=99.95,
            is_within_target=True,
            target_value=99.9,
        )
        assert measurement.metric == SLAMetric.UPTIME
        assert measurement.value == 99.95
        assert measurement.is_within_target is True
        assert measurement.target_value == 99.9
        assert isinstance(measurement.timestamp, datetime)

    def test_sla_measurement_custom_values(self):
        """Test SLAMeasurement with custom values."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        measurement = SLAMeasurement(
            metric=SLAMetric.RESPONSE_TIME,
            value=450.5,
            is_within_target=False,
            target_value=500.0,
            timestamp=timestamp,
        )
        assert measurement.value == 450.5
        assert measurement.timestamp == timestamp
        assert measurement.is_within_target is False

    def test_sla_measurement_uuid_generated(self):
        """Test SLAMeasurement generates UUID for measurement_id."""
        measurement = SLAMeasurement(
            metric=SLAMetric.AVAILABILITY,
            value=99.9,
            is_within_target=True,
            target_value=99.5,
        )
        assert isinstance(measurement.measurement_id, UUID)


class TestSLAIncident:
    """Test SLAIncident model."""

    def test_sla_incident_defaults(self):
        """Test SLAIncident with default values."""
        incident = SLAIncident(
            metric=SLAMetric.UPTIME,
            severity="critical",
            started_at=datetime.now(),
            impact_description="System downtime",
        )
        assert incident.metric == SLAMetric.UPTIME
        assert incident.severity == "critical"
        assert incident.impact_description == "System downtime"
        assert incident.resolved_at is None
        assert incident.duration_seconds is None

    def test_sla_incident_custom_values(self):
        """Test SLAIncident with custom values."""
        started = datetime(2024, 1, 15, 10, 0, 0)
        resolved = datetime(2024, 1, 15, 11, 0, 0)
        incident = SLAIncident(
            metric=SLAMetric.RESPONSE_TIME,
            severity="warning",
            started_at=started,
            resolved_at=resolved,
            duration_seconds=3600,
            impact_description="Slow response times",
            resolution_notes="Optimized database queries",
        )
        assert incident.severity == "warning"
        assert incident.duration_seconds == 3600
        assert incident.resolution_notes == "Optimized database queries"

    def test_sla_incident_severity(self):
        """Test SLAIncident severity levels."""
        critical = SLAIncident(
            metric=SLAMetric.ERROR_RATE,
            severity="critical",
            started_at=datetime.now(),
            impact_description="High error rate",
        )
        warning = SLAIncident(
            metric=SLAMetric.ERROR_RATE,
            severity="warning",
            started_at=datetime.now(),
            impact_description="Elevated error rate",
        )
        assert critical.severity == "critical"
        assert warning.severity == "warning"


class TestSLAConfig:
    """Test SLAConfig model."""

    def test_sla_config_defaults(self):
        """Test SLAConfig with default values."""
        config = SLAConfig()
        assert len(config.targets) == 0
        assert config.measurement_interval_seconds == 60
        assert config.incident_auto_resolve_minutes == 30
        assert config.report_generation_enabled is True

    def test_sla_config_custom_values(self):
        """Test SLAConfig with custom values."""
        targets = [
            SLATarget(
                metric=SLAMetric.UPTIME,
                target_value=99.9,
                tier=SLATier.GOLD,
            ),
            SLATarget(
                metric=SLAMetric.RESPONSE_TIME,
                target_value=500.0,
                tier=SLATier.PLATINUM,
            ),
        ]
        config = SLAConfig(
            targets=targets,
            measurement_interval_seconds=30,
            incident_auto_resolve_minutes=15,
            report_generation_enabled=False,
        )
        assert len(config.targets) == 2
        assert config.measurement_interval_seconds == 30
        assert config.incident_auto_resolve_minutes == 15
        assert config.report_generation_enabled is False

    def test_sla_config_targets_list(self):
        """Test SLAConfig targets list."""
        config = SLAConfig()
        assert isinstance(config.targets, list)


class TestSLAMonitorServiceInit:
    """Test SLAMonitorService initialization."""

    def test_service_init_with_config(self):
        """Test service initialization with custom config."""
        config = SLAConfig(measurement_interval_seconds=30)
        service = SLAMonitorService(config=config)
        assert service.config == config
        assert service.config.measurement_interval_seconds == 30

    def test_service_init_empty_measurements(self):
        """Test service initializes with empty measurements."""
        service = SLAMonitorService()
        assert len(service.measurements) == 0
        assert isinstance(service.measurements, list)

    def test_service_init_empty_incidents(self):
        """Test service initializes with empty incidents."""
        service = SLAMonitorService()
        assert len(service.incidents) == 0
        assert isinstance(service.incidents, list)


class TestRecordMeasurement:
    """Test record_measurement method."""

    def test_record_measurement_records_value(self):
        """Test record_measurement records a value."""
        service = SLAMonitorService()
        measurement = service.record_measurement(
            metric=SLAMetric.UPTIME,
            value=99.95,
        )
        assert measurement.metric == SLAMetric.UPTIME
        assert measurement.value == 99.95
        assert len(service.measurements) == 1

    def test_record_measurement_assigns_uuid(self):
        """Test record_measurement assigns unique UUID."""
        service = SLAMonitorService()
        measurement = service.record_measurement(
            metric=SLAMetric.RESPONSE_TIME,
            value=450.0,
        )
        assert isinstance(measurement.measurement_id, UUID)

    def test_record_measurement_checks_target(self):
        """Test record_measurement checks against target."""
        target = SLATarget(
            metric=SLAMetric.UPTIME,
            target_value=99.9,
            tier=SLATier.GOLD,
        )
        config = SLAConfig(targets=[target])
        service = SLAMonitorService(config=config)
        measurement = service.record_measurement(
            metric=SLAMetric.UPTIME,
            value=99.95,
        )
        assert measurement.is_within_target is True

    def test_record_measurement_creates_incident_on_breach(self):
        """Test record_measurement creates incident on SLA breach."""
        target = SLATarget(
            metric=SLAMetric.RESPONSE_TIME,
            target_value=500.0,
            tier=SLATier.PLATINUM,
            breach_notification=True,
        )
        config = SLAConfig(targets=[target])
        service = SLAMonitorService(config=config)
        service.record_measurement(
            metric=SLAMetric.RESPONSE_TIME,
            value=600.0,
        )
        assert len(service.incidents) > 0


class TestGetCurrentSLAStatus:
    """Test get_current_sla_status method."""

    def test_get_current_sla_status_returns_per_metric(self):
        """Test get_current_sla_status returns status per metric."""
        target = SLATarget(
            metric=SLAMetric.UPTIME,
            target_value=99.9,
            tier=SLATier.GOLD,
        )
        config = SLAConfig(targets=[target])
        service = SLAMonitorService(config=config)
        service.record_measurement(metric=SLAMetric.UPTIME, value=99.95)
        status = service.get_current_sla_status()
        assert "uptime" in status
        assert "current_value" in status["uptime"]

    def test_get_current_sla_status_compliance_percent(self):
        """Test get_current_sla_status includes compliance percentage."""
        target = SLATarget(
            metric=SLAMetric.AVAILABILITY,
            target_value=99.0,
            tier=SLATier.SILVER,
        )
        config = SLAConfig(targets=[target])
        service = SLAMonitorService(config=config)
        service.record_measurement(metric=SLAMetric.AVAILABILITY, value=99.1)
        service.record_measurement(metric=SLAMetric.AVAILABILITY, value=98.9)
        status = service.get_current_sla_status()
        assert status["availability"]["compliance_percent"] > 0

    def test_get_current_sla_status_proper_structure(self):
        """Test get_current_sla_status has proper structure."""
        target = SLATarget(
            metric=SLAMetric.ERROR_RATE,
            target_value=0.1,
            tier=SLATier.BRONZE,
        )
        config = SLAConfig(targets=[target])
        service = SLAMonitorService(config=config)
        service.record_measurement(metric=SLAMetric.ERROR_RATE, value=0.05)
        status = service.get_current_sla_status()
        assert isinstance(status, dict)
        assert "error_rate" in status


class TestCheckSLACompliance:
    """Test check_sla_compliance method."""

    def test_check_sla_compliance_compliant(self):
        """Test check_sla_compliance when compliant."""
        target = SLATarget(
            metric=SLAMetric.UPTIME,
            target_value=99.0,
            tier=SLATier.GOLD,
        )
        config = SLAConfig(targets=[target])
        service = SLAMonitorService(config=config)
        service.record_measurement(metric=SLAMetric.UPTIME, value=99.5)
        result = service.check_sla_compliance()
        assert result["compliant"] is True

    def test_check_sla_compliance_non_compliant(self):
        """Test check_sla_compliance when non-compliant."""
        target = SLATarget(
            metric=SLAMetric.RESPONSE_TIME,
            target_value=500.0,
            tier=SLATier.PLATINUM,
        )
        config = SLAConfig(targets=[target])
        service = SLAMonitorService(config=config)
        service.record_measurement(metric=SLAMetric.RESPONSE_TIME, value=600.0)
        result = service.check_sla_compliance(metric=SLAMetric.RESPONSE_TIME)
        assert result["compliant"] is False

    def test_check_sla_compliance_partial(self):
        """Test check_sla_compliance with mixed compliance."""
        targets = [
            SLATarget(
                metric=SLAMetric.UPTIME,
                target_value=99.0,
                tier=SLATier.GOLD,
            ),
            SLATarget(
                metric=SLAMetric.ERROR_RATE,
                target_value=0.1,
                tier=SLATier.GOLD,
            ),
        ]
        config = SLAConfig(targets=targets)
        service = SLAMonitorService(config=config)
        service.record_measurement(metric=SLAMetric.UPTIME, value=99.5)
        service.record_measurement(metric=SLAMetric.ERROR_RATE, value=0.15)
        result = service.check_sla_compliance()
        assert result["compliant_count"] >= 1
        assert result["total_count"] == 2


class TestGetUptime:
    """Test get_uptime method."""

    def test_get_uptime_calculates_percent(self):
        """Test get_uptime calculates uptime percentage."""
        target = SLATarget(
            metric=SLAMetric.UPTIME,
            target_value=99.0,
            tier=SLATier.GOLD,
        )
        config = SLAConfig(targets=[target])
        service = SLAMonitorService(config=config)
        service.record_measurement(metric=SLAMetric.UPTIME, value=99.9)
        uptime = service.get_uptime()
        assert uptime["uptime_percent"] > 0
        assert "total_checks" in uptime

    def test_get_uptime_period_filtering(self):
        """Test get_uptime filters by period."""
        service = SLAMonitorService()
        now = datetime.now()
        past = now - timedelta(hours=24)

        measurement = SLAMeasurement(
            metric=SLAMetric.UPTIME,
            value=99.0,
            is_within_target=True,
            target_value=99.0,
            timestamp=past,
        )
        service.measurements.append(measurement)

        uptime_6 = service.get_uptime(period_hours=6)
        assert uptime_6["total_checks"] == 0

        uptime_48 = service.get_uptime(period_hours=48)
        assert uptime_48["total_checks"] == 1

    def test_get_uptime_all_healthy(self):
        """Test get_uptime when all checks are healthy."""
        service = SLAMonitorService()
        for i in range(5):
            service.record_measurement(
                metric=SLAMetric.UPTIME,
                value=99.9,
            )
        uptime = service.get_uptime()
        assert uptime["failed_checks"] == 0


class TestGetResponseTimePercentiles:
    """Test get_response_time_percentiles method."""

    def test_get_response_time_percentiles_p50_p95_p99(self):
        """Test get_response_time_percentiles returns p50/p95/p99."""
        service = SLAMonitorService()
        for i in range(100):
            service.record_measurement(
                metric=SLAMetric.RESPONSE_TIME,
                value=100 + i,
            )
        percentiles = service.get_response_time_percentiles()
        assert "p50" in percentiles
        assert "p95" in percentiles
        assert "p99" in percentiles
        assert percentiles["p50"] <= percentiles["p95"]
        assert percentiles["p95"] <= percentiles["p99"]

    def test_get_response_time_percentiles_empty_data(self):
        """Test get_response_time_percentiles with no data."""
        service = SLAMonitorService()
        percentiles = service.get_response_time_percentiles()
        assert percentiles["p50"] == 0
        assert percentiles["p95"] == 0
        assert percentiles["p99"] == 0

    def test_get_response_time_percentiles_single_data_point(self):
        """Test get_response_time_percentiles with single data point."""
        service = SLAMonitorService()
        service.record_measurement(
            metric=SLAMetric.RESPONSE_TIME,
            value=250.0,
        )
        percentiles = service.get_response_time_percentiles()
        assert percentiles["p50"] == pytest.approx(250.0, rel=1e-3)
        assert "avg" in percentiles
        assert "min" in percentiles
        assert "max" in percentiles


class TestCreateIncident:
    """Test create_incident method."""

    def test_create_incident_creates_incident(self):
        """Test create_incident creates new incident."""
        service = SLAMonitorService()
        incident = service.create_incident(
            metric=SLAMetric.UPTIME,
            severity="critical",
            description="Database down",
        )
        assert incident.metric == SLAMetric.UPTIME
        assert incident.severity == "critical"
        assert len(service.incidents) == 1

    def test_create_incident_assigns_uuid(self):
        """Test create_incident assigns unique UUID."""
        service = SLAMonitorService()
        incident = service.create_incident(
            metric=SLAMetric.RESPONSE_TIME,
            severity="warning",
            description="High response time",
        )
        assert isinstance(incident.incident_id, UUID)

    def test_create_incident_sets_severity(self):
        """Test create_incident sets severity levels."""
        service = SLAMonitorService()
        critical = service.create_incident(
            metric=SLAMetric.ERROR_RATE,
            severity="critical",
            description="High error rate",
        )
        warning = service.create_incident(
            metric=SLAMetric.ERROR_RATE,
            severity="warning",
            description="Elevated error rate",
        )
        assert critical.severity == "critical"
        assert warning.severity == "warning"


class TestResolveIncident:
    """Test resolve_incident method."""

    def test_resolve_incident_resolves(self):
        """Test resolve_incident resolves an incident."""
        service = SLAMonitorService()
        incident = service.create_incident(
            metric=SLAMetric.UPTIME,
            severity="critical",
            description="System down",
        )
        resolved = service.resolve_incident(incident.incident_id)
        assert resolved is not None
        assert resolved.resolved_at is not None

    def test_resolve_incident_sets_notes(self):
        """Test resolve_incident sets resolution notes."""
        service = SLAMonitorService()
        incident = service.create_incident(
            metric=SLAMetric.RESPONSE_TIME,
            severity="warning",
            description="Slow response",
        )
        resolved = service.resolve_incident(
            incident.incident_id,
            notes="Optimized query",
        )
        assert resolved.resolution_notes == "Optimized query"

    def test_resolve_incident_calculates_duration(self):
        """Test resolve_incident calculates duration."""
        service = SLAMonitorService()
        incident = service.create_incident(
            metric=SLAMetric.ERROR_RATE,
            severity="critical",
            description="High errors",
        )
        resolved = service.resolve_incident(incident.incident_id)
        assert resolved.duration_seconds is not None
        assert resolved.duration_seconds >= 0


class TestGenerateSLAReport:
    """Test generate_sla_report method."""

    def test_generate_sla_report_generates_report(self):
        """Test generate_sla_report generates report."""
        service = SLAMonitorService()
        report = service.generate_sla_report(period_days=30)
        assert "report_period" in report
        assert "overall_compliance" in report
        assert "metric_compliance" in report

    def test_generate_sla_report_includes_all_metrics(self):
        """Test generate_sla_report includes all metrics."""
        targets = [
            SLATarget(
                metric=SLAMetric.UPTIME,
                target_value=99.0,
                tier=SLATier.GOLD,
            ),
            SLATarget(
                metric=SLAMetric.RESPONSE_TIME,
                target_value=500.0,
                tier=SLATier.PLATINUM,
            ),
        ]
        config = SLAConfig(targets=targets)
        service = SLAMonitorService(config=config)
        service.record_measurement(metric=SLAMetric.UPTIME, value=99.5)
        service.record_measurement(metric=SLAMetric.RESPONSE_TIME, value=450.0)
        report = service.generate_sla_report(period_days=30)
        assert "incidents" in report
        assert "current_status" in report

    def test_generate_sla_report_period_filter(self):
        """Test generate_sla_report respects period."""
        service = SLAMonitorService()
        report = service.generate_sla_report(period_days=7)
        assert report["report_period"]["days"] == 7


class TestGetSLATrends:
    """Test get_sla_trends method."""

    def test_get_sla_trends_daily_averages(self):
        """Test get_sla_trends returns daily averages."""
        service = SLAMonitorService()
        now = datetime.now()
        for i in range(10):
            measurement = SLAMeasurement(
                metric=SLAMetric.UPTIME,
                value=99.0 + i,
                is_within_target=True,
                target_value=99.0,
                timestamp=now - timedelta(days=9-i),
            )
            service.measurements.append(measurement)
        trends = service.get_sla_trends(metric=SLAMetric.UPTIME, period_days=30)
        assert "daily_averages" in trends
        assert len(trends["daily_averages"]) > 0

    def test_get_sla_trends_trend_direction(self):
        """Test get_sla_trends calculates trend direction."""
        service = SLAMonitorService()
        now = datetime.now()
        for i in range(10):
            measurement = SLAMeasurement(
                metric=SLAMetric.RESPONSE_TIME,
                value=100 + i * 10,
                is_within_target=True,
                target_value=500.0,
                timestamp=now - timedelta(days=9-i),
            )
            service.measurements.append(measurement)
        trends = service.get_sla_trends(
            metric=SLAMetric.RESPONSE_TIME,
            period_days=30,
        )
        assert trends["trend"] in ["improving", "degrading", "stable"]

    def test_get_sla_trends_empty_data(self):
        """Test get_sla_trends with no data."""
        service = SLAMonitorService()
        trends = service.get_sla_trends(
            metric=SLAMetric.ERROR_RATE,
            period_days=30,
        )
        assert trends["trend"] == "insufficient_data"
        assert len(trends["daily_averages"]) == 0

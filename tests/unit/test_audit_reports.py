"""
Unit tests for Audit Report Service - Iteration 8 Wave 2.
Tests for audit report generation for compliance and security.
"""

import pytest
from datetime import datetime, timedelta
from uuid import UUID
from unittest.mock import Mock, patch

from src.platform_services.audit_reports import (
    ReportType,
    ReportFormat,
    ReportPeriod,
    AuditFinding,
    AuditReport,
    AuditReportConfig,
    AuditReportService,
)


class TestReportType:
    """Test ReportType enum."""

    def test_report_type_enum_values(self):
        """Test all ReportType enum values exist."""
        assert ReportType.COMPLIANCE.value == "compliance"
        assert ReportType.SECURITY.value == "security"
        assert ReportType.ACCESS.value == "access"
        assert ReportType.DATA_PROCESSING.value == "data_processing"
        assert ReportType.INCIDENT.value == "incident"
        assert ReportType.CUSTOM.value == "custom"

    def test_report_type_count(self):
        """Test ReportType has correct number of values."""
        assert len(list(ReportType)) == 6

    def test_report_type_representation(self):
        """Test ReportType string representation."""
        assert str(ReportType.COMPLIANCE) == "ReportType.COMPLIANCE"


class TestReportFormat:
    """Test ReportFormat enum."""

    def test_report_format_enum_values(self):
        """Test all ReportFormat enum values exist."""
        assert ReportFormat.JSON.value == "json"
        assert ReportFormat.CSV.value == "csv"
        assert ReportFormat.PDF_DATA.value == "pdf_data"
        assert ReportFormat.SUMMARY.value == "summary"

    def test_report_format_count(self):
        """Test ReportFormat has correct number of values."""
        assert len(list(ReportFormat)) == 4

    def test_report_format_representation(self):
        """Test ReportFormat string representation."""
        assert str(ReportFormat.JSON) == "ReportFormat.JSON"


class TestReportPeriod:
    """Test ReportPeriod model."""

    def test_report_period_defaults(self):
        """Test ReportPeriod with default values."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        period = ReportPeriod(
            start_date=start,
            end_date=end,
        )
        assert period.start_date == start
        assert period.end_date == end
        assert period.generated_by == "system"
        assert isinstance(period.generated_at, datetime)

    def test_report_period_custom_values(self):
        """Test ReportPeriod with custom values."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        generated = datetime(2024, 2, 1)
        period = ReportPeriod(
            start_date=start,
            end_date=end,
            generated_at=generated,
            generated_by="admin_user",
        )
        assert period.generated_by == "admin_user"
        assert period.generated_at == generated

    def test_report_period_date_fields(self):
        """Test ReportPeriod date fields."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 31, 23, 59, 59)
        period = ReportPeriod(start_date=start, end_date=end)
        assert period.start_date == start
        assert period.end_date == end


class TestAuditFinding:
    """Test AuditFinding model."""

    def test_audit_finding_defaults(self):
        """Test AuditFinding with default values."""
        finding = AuditFinding(
            severity="warning",
            category="authentication",
            description="MFA not enforced",
            recommendation="Enable MFA for all users",
        )
        assert finding.severity == "warning"
        assert finding.category == "authentication"
        assert finding.status == "open"
        assert len(finding.evidence) == 0

    def test_audit_finding_custom_values(self):
        """Test AuditFinding with custom values."""
        finding = AuditFinding(
            severity="critical",
            category="encryption",
            description="TLS version outdated",
            evidence=["TLS 1.0 detected", "Weak cipher suites"],
            recommendation="Upgrade to TLS 1.3",
            status="acknowledged",
        )
        assert finding.severity == "critical"
        assert len(finding.evidence) == 2
        assert finding.status == "acknowledged"

    def test_audit_finding_uuid_generated(self):
        """Test AuditFinding generates UUID for finding_id."""
        finding = AuditFinding(
            severity="info",
            category="audit_log",
            description="Audit logs enabled",
            recommendation="Monitor logs regularly",
        )
        assert isinstance(finding.finding_id, UUID)

    def test_audit_finding_severity_levels(self):
        """Test AuditFinding supports different severity levels."""
        critical = AuditFinding(
            severity="critical",
            category="security",
            description="Critical issue",
            recommendation="Fix immediately",
        )
        warning = AuditFinding(
            severity="warning",
            category="security",
            description="Warning issue",
            recommendation="Address soon",
        )
        info = AuditFinding(
            severity="info",
            category="security",
            description="Informational",
            recommendation="For awareness",
        )
        assert critical.severity == "critical"
        assert warning.severity == "warning"
        assert info.severity == "info"


class TestAuditReport:
    """Test AuditReport model."""

    def test_audit_report_defaults(self):
        """Test AuditReport with default values."""
        period = ReportPeriod(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        report = AuditReport(
            report_type=ReportType.COMPLIANCE,
            title="Compliance Report",
            period=period,
        )
        assert report.report_type == ReportType.COMPLIANCE
        assert report.title == "Compliance Report"
        assert len(report.findings) == 0
        assert report.format == ReportFormat.JSON

    def test_audit_report_custom_values(self):
        """Test AuditReport with custom values."""
        period = ReportPeriod(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        finding = AuditFinding(
            severity="warning",
            category="access",
            description="Inactive accounts",
            recommendation="Deactivate accounts",
        )
        report = AuditReport(
            report_type=ReportType.ACCESS,
            title="Access Audit Report",
            period=period,
            findings=[finding],
            format=ReportFormat.CSV,
        )
        assert len(report.findings) == 1
        assert report.format == ReportFormat.CSV

    def test_audit_report_uuid_generated(self):
        """Test AuditReport generates UUID for report_id."""
        period = ReportPeriod(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        report = AuditReport(
            report_type=ReportType.SECURITY,
            title="Security Report",
            period=period,
        )
        assert isinstance(report.report_id, UUID)

    def test_audit_report_findings_list(self):
        """Test AuditReport findings list."""
        period = ReportPeriod(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        report = AuditReport(
            report_type=ReportType.INCIDENT,
            title="Incident Report",
            period=period,
        )
        assert isinstance(report.findings, list)


class TestAuditReportConfig:
    """Test AuditReportConfig model."""

    def test_audit_report_config_defaults(self):
        """Test AuditReportConfig with default values."""
        config = AuditReportConfig()
        assert config.auto_generate is False
        assert config.schedule_cron is None
        assert config.retention_days == 730
        assert config.include_pii is False
        assert config.max_findings_per_report == 1000

    def test_audit_report_config_custom_values(self):
        """Test AuditReportConfig with custom values."""
        config = AuditReportConfig(
            auto_generate=True,
            schedule_cron="0 2 * * *",
            retention_days=365,
            include_pii=True,
            max_findings_per_report=500,
        )
        assert config.auto_generate is True
        assert config.schedule_cron == "0 2 * * *"
        assert config.retention_days == 365
        assert config.include_pii is True
        assert config.max_findings_per_report == 500

    def test_audit_report_config_retention_days(self):
        """Test AuditReportConfig retention_days field."""
        config = AuditReportConfig(retention_days=180)
        assert config.retention_days == 180


class TestAuditReportServiceInit:
    """Test AuditReportService initialization."""

    def test_service_init_creates_with_config(self):
        """Test service initialization with custom config."""
        config = AuditReportConfig(retention_days=365)
        service = AuditReportService(config=config)
        assert service.config == config
        assert service.config.retention_days == 365

    def test_service_init_empty_reports(self):
        """Test service initializes with empty reports."""
        service = AuditReportService()
        assert len(service.reports) == 0
        assert isinstance(service.reports, list)

    def test_service_init_stats(self):
        """Test service initializes with empty stats."""
        service = AuditReportService()
        assert len(service.findings_log) == 0
        assert len(service.scheduled_reports) == 0


class TestGenerateComplianceReport:
    """Test generate_compliance_report method."""

    def test_generate_compliance_report_generates(self):
        """Test generate_compliance_report generates report."""
        service = AuditReportService()
        report = service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert report.report_type == ReportType.COMPLIANCE
        assert len(service.reports) == 1

    def test_generate_compliance_report_includes_findings(self):
        """Test generate_compliance_report includes findings."""
        service = AuditReportService()
        report = service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert len(report.findings) > 0

    def test_generate_compliance_report_period(self):
        """Test generate_compliance_report respects period."""
        service = AuditReportService()
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        report = service.generate_compliance_report(
            start_date=start,
            end_date=end,
        )
        assert report.period.start_date == start
        assert report.period.end_date == end


class TestGenerateSecurityReport:
    """Test generate_security_report method."""

    def test_generate_security_report_generates(self):
        """Test generate_security_report generates report."""
        service = AuditReportService()
        report = service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert report.report_type == ReportType.SECURITY
        assert len(service.reports) == 1

    def test_generate_security_report_includes_findings(self):
        """Test generate_security_report includes findings."""
        service = AuditReportService()
        report = service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert len(report.findings) > 0
        assert any(f.severity == "critical" for f in report.findings)

    def test_generate_security_report_proper_type(self):
        """Test generate_security_report has proper type."""
        service = AuditReportService()
        report = service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert report.report_type == ReportType.SECURITY


class TestGenerateAccessReport:
    """Test generate_access_report method."""

    def test_generate_access_report_generates(self):
        """Test generate_access_report generates report."""
        service = AuditReportService()
        report = service.generate_access_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert report.report_type == ReportType.ACCESS
        assert len(service.reports) == 1

    def test_generate_access_report_includes_findings(self):
        """Test generate_access_report includes findings."""
        service = AuditReportService()
        report = service.generate_access_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert len(report.findings) > 0

    def test_generate_access_report_proper_type(self):
        """Test generate_access_report has proper type."""
        service = AuditReportService()
        report = service.generate_access_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert report.report_type == ReportType.ACCESS


class TestGetReport:
    """Test get_report method."""

    def test_get_report_returns_report(self):
        """Test get_report returns correct report."""
        service = AuditReportService()
        report = service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        retrieved = service.get_report(report.report_id)
        assert retrieved is not None
        assert retrieved.report_id == report.report_id

    def test_get_report_missing_raises(self):
        """Test get_report returns None for missing report."""
        service = AuditReportService()
        from uuid import uuid4

        result = service.get_report(uuid4())
        assert result is None

    def test_get_report_after_create(self):
        """Test get_report works after report creation."""
        service = AuditReportService()
        report1 = service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        report2 = service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        retrieved = service.get_report(report2.report_id)
        assert retrieved.report_id == report2.report_id


class TestListReports:
    """Test list_reports method."""

    def test_list_reports_returns_all(self):
        """Test list_reports returns all reports."""
        service = AuditReportService()
        service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        reports = service.list_reports()
        assert len(reports) == 2

    def test_list_reports_filters_by_type(self):
        """Test list_reports filters by type."""
        service = AuditReportService()
        service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        reports = service.list_reports(report_type=ReportType.COMPLIANCE)
        assert len(reports) == 1
        assert reports[0].report_type == ReportType.COMPLIANCE

    def test_list_reports_limit(self):
        """Test list_reports respects limit."""
        service = AuditReportService()
        for i in range(5):
            service.generate_compliance_report(
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
            )
        reports = service.list_reports(limit=3)
        assert len(reports) <= 3


class TestExportReport:
    """Test export_report method."""

    def test_export_report_exports_json(self):
        """Test export_report exports JSON format."""
        service = AuditReportService()
        report = service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        exported = service.export_report(
            report_id=report.report_id,
            format=ReportFormat.JSON,
        )
        assert exported["format"] == "json"
        assert "data" in exported

    def test_export_report_exports_csv(self):
        """Test export_report exports CSV format."""
        service = AuditReportService()
        report = service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        exported = service.export_report(
            report_id=report.report_id,
            format=ReportFormat.CSV,
        )
        assert exported["format"] == "csv"
        assert "data" in exported

    def test_export_report_exports_summary(self):
        """Test export_report exports SUMMARY format."""
        service = AuditReportService()
        report = service.generate_access_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        exported = service.export_report(
            report_id=report.report_id,
            format=ReportFormat.SUMMARY,
        )
        assert exported["format"] == "summary"
        assert "data" in exported


class TestAddFinding:
    """Test add_finding method."""

    def test_add_finding_adds_to_report(self):
        """Test add_finding adds finding to report."""
        service = AuditReportService()
        report = service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        initial_count = len(report.findings)
        finding = AuditFinding(
            severity="info",
            category="test",
            description="Test finding",
            recommendation="Test recommendation",
        )
        added = service.add_finding(report.report_id, finding)
        assert added is not None
        assert len(service.get_report(report.report_id).findings) == initial_count + 1

    def test_add_finding_increments_count(self):
        """Test add_finding increments finding count."""
        service = AuditReportService()
        report = service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        initial_count = len(report.findings)
        for i in range(3):
            service.add_finding(
                report.report_id,
                AuditFinding(
                    severity="info",
                    category="test",
                    description=f"Finding {i}",
                    recommendation="Fix it",
                ),
            )
        updated_report = service.get_report(report.report_id)
        assert len(updated_report.findings) == initial_count + 3

    def test_add_finding_validates(self):
        """Test add_finding validates input."""
        service = AuditReportService()
        from uuid import uuid4

        finding = AuditFinding(
            severity="info",
            category="test",
            description="Test",
            recommendation="Fix",
        )
        with pytest.raises(ValueError):
            service.add_finding(uuid4(), finding)


class TestUpdateFindingStatus:
    """Test update_finding_status method."""

    def test_update_finding_status_updates_status(self):
        """Test update_finding_status updates status."""
        service = AuditReportService()
        report = service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        finding = report.findings[0]
        updated = service.update_finding_status(
            report.report_id,
            finding.finding_id,
            "resolved",
        )
        assert updated.status == "resolved"

    def test_update_finding_status_adds_notes(self):
        """Test update_finding_status adds notes."""
        service = AuditReportService()
        report = service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        finding = report.findings[0]
        updated = service.update_finding_status(
            report.report_id,
            finding.finding_id,
            "acknowledged",
            notes="In progress",
        )
        assert updated is not None
        assert len(service.findings_log) > 0

    def test_update_finding_status_missing_finding(self):
        """Test update_finding_status with missing finding."""
        service = AuditReportService()
        report = service.generate_security_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        from uuid import uuid4

        result = service.update_finding_status(
            report.report_id,
            uuid4(),
            "resolved",
        )
        assert result is None


class TestGetComplianceSummary:
    """Test get_compliance_summary method."""

    def test_get_compliance_summary_returns_summary(self):
        """Test get_compliance_summary returns summary."""
        service = AuditReportService()
        service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        summary = service.get_compliance_summary(period_days=90)
        assert "total_reports" in summary
        assert "total_findings" in summary
        assert "compliance_score" in summary

    def test_get_compliance_summary_score_calculation(self):
        """Test get_compliance_summary calculates score."""
        service = AuditReportService()
        service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        summary = service.get_compliance_summary(period_days=90)
        assert 0 <= summary["compliance_score"] <= 100
        assert "status" in summary

    def test_get_compliance_summary_period_filter(self):
        """Test get_compliance_summary respects period."""
        service = AuditReportService()
        service.generate_compliance_report(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        summary = service.get_compliance_summary(period_days=7)
        assert summary["period_days"] == 7

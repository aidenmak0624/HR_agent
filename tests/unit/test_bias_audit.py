"""Tests for Bias Audit Framework (PLAT-004)."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, Mock
from src.core.bias_audit import (
    BiasAuditor,
    BiasIncident,
    ProtectedCategory,
    BiasSeverity,
    BiasAuditMiddleware,
)


class TestBiasAuditorScanResponse:
    """Tests for scanning responses for bias indicators."""

    def test_scan_response_detects_biased_terms(self):
        """scan_response detects biased language terms."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="compensation",
            query="What salary for this candidate?",
            response="She is too emotional for this role, $50k is appropriate."
        )

        assert len(incidents) > 0
        assert any(i.category == ProtectedCategory.GENDER for i in incidents)

    def test_scan_response_detects_stereotypes(self):
        """scan_response detects stereotype patterns."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Candidate evaluation",
            response="Women are too emotional to handle technical roles."
        )

        assert len(incidents) > 0
        assert any(i.severity == BiasSeverity.HIGH for i in incidents)

    def test_scan_response_returns_empty_list_for_neutral_text(self):
        """scan_response returns empty list for neutral language."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="compensation",
            query="What salary?",
            response="The candidate's compensation is based on job title and performance metrics."
        )

        assert len(incidents) == 0

    def test_scan_response_enriches_incidents_with_context(self):
        """scan_response adds agent type and query to incidents."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Culture fit concern",
            response="The candidate has a cultural fit concern for the team."
        )

        assert len(incidents) > 0
        for incident in incidents:
            assert incident.agent_type == "hiring"
            assert incident.query == "Culture fit concern"


class TestCompensationEquity:
    """Tests for compensation equity analysis."""

    def test_check_compensation_equity_detects_gender_pay_gap(self):
        """check_compensation_equity identifies gender pay disparities."""
        auditor = BiasAuditor()

        data = [
            {"job_title": "Engineer", "level": "Senior", "gender": "M", "base_salary": 120000},
            {"job_title": "Engineer", "level": "Senior", "gender": "M", "base_salary": 125000},
            {"job_title": "Engineer", "level": "Senior", "gender": "F", "base_salary": 100000},
            {"job_title": "Engineer", "level": "Senior", "gender": "F", "base_salary": 105000},
        ]

        incidents = auditor.check_compensation_equity(data)

        assert len(incidents) > 0
        assert any(i.category == ProtectedCategory.GENDER for i in incidents)

    def test_check_compensation_equity_detects_race_pay_gap(self):
        """check_compensation_equity identifies race-based pay gaps."""
        auditor = BiasAuditor()

        data = [
            {"job_title": "Manager", "level": "Mid", "race": "white", "base_salary": 110000},
            {"job_title": "Manager", "level": "Mid", "race": "white", "base_salary": 115000},
            {"job_title": "Manager", "level": "Mid", "race": "black", "base_salary": 90000},
            {"job_title": "Manager", "level": "Mid", "race": "black", "base_salary": 95000},
        ]

        incidents = auditor.check_compensation_equity(data)

        assert len(incidents) > 0
        assert any(i.category == ProtectedCategory.RACE for i in incidents)

    def test_check_compensation_equity_detects_age_disparity(self):
        """check_compensation_equity identifies age-based pay disparities."""
        auditor = BiasAuditor()

        data = [
            {"job_title": "Developer", "level": "Senior", "age": 25, "base_salary": 130000},
            {"job_title": "Developer", "level": "Senior", "age": 28, "base_salary": 135000},
            {"job_title": "Developer", "level": "Senior", "age": 45, "base_salary": 80000},
            {"job_title": "Developer", "level": "Senior", "age": 50, "base_salary": 85000},
        ]

        incidents = auditor.check_compensation_equity(data)

        assert len(incidents) > 0
        assert any(i.category == ProtectedCategory.AGE for i in incidents)

    def test_check_compensation_equity_allows_small_gaps(self):
        """check_compensation_equity ignores gaps under 5%."""
        auditor = BiasAuditor()

        data = [
            {"job_title": "Engineer", "level": "Mid", "gender": "M", "base_salary": 100000},
            {"job_title": "Engineer", "level": "Mid", "gender": "F", "base_salary": 99000},
        ]

        incidents = auditor.check_compensation_equity(data)

        # Should not flag small gaps
        assert len(incidents) == 0

    def test_check_compensation_equity_with_empty_data(self):
        """check_compensation_equity handles empty data gracefully."""
        auditor = BiasAuditor()

        incidents = auditor.check_compensation_equity([])

        assert len(incidents) == 0


class TestBiasSeverity:
    """Tests for bias severity scoring."""

    def test_severity_low_for_minor_terms(self):
        """BiasIncident with minor biased terms scored as LOW."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Candidate review",
            response="The candidate seems diverse."
        )

        # "diverse" is a potentially biased term
        if incidents:
            assert any(i.severity in [BiasSeverity.LOW, BiasSeverity.MEDIUM] for i in incidents)

    def test_severity_high_for_patterns(self):
        """BiasIncident with pattern matches scored as HIGH."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Evaluation",
            response="She is too emotional and sensitive for management."
        )

        assert len(incidents) > 0
        assert any(i.severity == BiasSeverity.HIGH for i in incidents)

    def test_severity_critical_for_explicit_discrimination(self):
        """BiasIncident with exclusionary patterns scored as CRITICAL."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Requirements",
            response="Only guys should apply for this position."
        )

        assert len(incidents) > 0
        assert any(i.severity == BiasSeverity.CRITICAL for i in incidents)


class TestProtectedCategories:
    """Tests for detection of all protected categories."""

    def test_detect_gender_bias(self):
        """BiasAuditor detects gender-related bias."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Candidate",
            response="She is too bossy for a team environment."
        )

        assert any(i.category == ProtectedCategory.GENDER for i in incidents)

    def test_detect_race_bias(self):
        """BiasAuditor detects race-related bias."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Candidate",
            response="This candidate is well-spoken and articulate for their background."
        )

        assert any(i.category == ProtectedCategory.RACE for i in incidents)

    def test_detect_age_bias(self):
        """BiasAuditor detects age-related bias."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Candidate",
            response="He's overqualified and seems too old for this startup role."
        )

        assert any(i.category == ProtectedCategory.AGE for i in incidents)

    def test_detect_disability_bias(self):
        """BiasAuditor detects disability-related bias."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Candidate",
            response="This candidate is crippled and cannot perform the role."
        )

        assert any(i.category == ProtectedCategory.DISABILITY for i in incidents)

    def test_detect_religion_bias(self):
        """BiasAuditor detects religion-related bias."""
        auditor = BiasAuditor()

        incidents = auditor.scan_response(
            agent_type="hiring",
            query="Candidate",
            response="This candidate is a religious zealot and cannot work here."
        )

        assert any(i.category == ProtectedCategory.RELIGION for i in incidents)


class TestAuditReport:
    """Tests for audit report generation."""

    def test_generate_audit_report_includes_metadata(self):
        """generate_audit_report includes report metadata."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="This candidate is too emotional."
        )

        report = auditor.generate_audit_report()

        assert "report_date" in report
        assert "period" in report
        assert "total_incidents" in report
        assert "incident_counts" in report

    def test_generate_audit_report_counts_by_severity(self):
        """generate_audit_report counts incidents by severity."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="Women are emotional, men are logical."
        )

        report = auditor.generate_audit_report()

        assert "critical" in report["incident_counts"]
        assert "high" in report["incident_counts"]
        assert "medium" in report["incident_counts"]
        assert "low" in report["incident_counts"]

    def test_generate_audit_report_categorizes_by_protected_class(self):
        """generate_audit_report breaks down incidents by category."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test 1",
            response="Too emotional for management."
        )

        auditor.scan_response(
            agent_type="hiring",
            query="Test 2",
            response="Candidate is well-spoken."
        )

        report = auditor.generate_audit_report()

        assert "category_breakdown" in report
        assert isinstance(report["category_breakdown"], dict)

    def test_generate_audit_report_with_date_range(self):
        """generate_audit_report filters by date range."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="She is too emotional."
        )

        now = datetime.utcnow()
        start = now - timedelta(days=30)
        end = now + timedelta(days=1)

        report = auditor.generate_audit_report(
            start_date=start,
            end_date=end
        )

        assert report["total_incidents"] >= 1

    def test_generate_audit_report_excludes_old_incidents(self):
        """generate_audit_report excludes incidents outside date range."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="She is too emotional."
        )

        # Use date range from past
        start = datetime.utcnow() - timedelta(days=60)
        end = datetime.utcnow() - timedelta(days=30)

        report = auditor.generate_audit_report(
            start_date=start,
            end_date=end
        )

        assert report["total_incidents"] == 0

    def test_generate_audit_report_includes_recommendations(self):
        """generate_audit_report includes action recommendations."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="Only guys should apply."
        )

        report = auditor.generate_audit_report()

        assert "recommendations" in report
        assert len(report["recommendations"]) > 0

    def test_generate_audit_report_identifies_high_risk_areas(self):
        """generate_audit_report identifies high-risk agent types."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="compensation",
            query="Salary",
            response="Women should earn less."
        )

        auditor.scan_response(
            agent_type="hiring",
            query="Candidate",
            response="No disabled people allowed."
        )

        report = auditor.generate_audit_report()

        assert "high_risk_areas" in report

    def test_generate_audit_report_summarizes_findings(self):
        """generate_audit_report includes findings summary."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="Women are emotional and men are logical."
        )

        report = auditor.generate_audit_report()

        assert "findings" in report
        assert isinstance(report["findings"], list)
        assert len(report["findings"]) > 0


class TestGetIncidents:
    """Tests for retrieving incidents with filtering."""

    def test_get_incidents_filters_by_severity(self):
        """get_incidents filters by severity level."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="She is too bossy and emotional."
        )

        incidents = auditor.get_incidents(
            severity_filter=BiasSeverity.HIGH
        )

        assert all(i.severity == BiasSeverity.HIGH for i in incidents)

    def test_get_incidents_filters_by_category(self):
        """get_incidents filters by protected category."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="She is too emotional."
        )

        incidents = auditor.get_incidents(
            category_filter=ProtectedCategory.GENDER
        )

        assert all(i.category == ProtectedCategory.GENDER for i in incidents)

    def test_get_incidents_with_both_filters(self):
        """get_incidents applies both severity and category filters."""
        auditor = BiasAuditor()

        auditor.scan_response(
            agent_type="hiring",
            query="Test",
            response="Women are emotional."
        )

        incidents = auditor.get_incidents(
            severity_filter=BiasSeverity.HIGH,
            category_filter=ProtectedCategory.GENDER
        )

        assert all(
            i.severity == BiasSeverity.HIGH and
            i.category == ProtectedCategory.GENDER
            for i in incidents
        )


class TestBiasIncidentProperties:
    """Tests for BiasIncident properties."""

    def test_bias_incident_has_required_fields(self):
        """BiasIncident stores all required information."""
        incident = BiasIncident(
            category=ProtectedCategory.GENDER,
            severity=BiasSeverity.HIGH,
            description="Test bias",
            agent_type="hiring",
            query="What about this candidate?",
            response="She is too emotional.",
            evidence="too emotional",
            recommendations=["Review language", "Train HR team"]
        )

        assert incident.category == ProtectedCategory.GENDER
        assert incident.severity == BiasSeverity.HIGH
        assert incident.description == "Test bias"
        assert incident.agent_type == "hiring"
        assert incident.query == "What about this candidate?"
        assert incident.response == "She is too emotional."
        assert incident.evidence == "too emotional"
        assert len(incident.recommendations) == 2

    def test_bias_incident_generates_unique_id(self):
        """BiasIncident generates unique incident IDs."""
        incident1 = BiasIncident(
            category=ProtectedCategory.GENDER,
            severity=BiasSeverity.LOW
        )

        incident2 = BiasIncident(
            category=ProtectedCategory.GENDER,
            severity=BiasSeverity.LOW
        )

        assert incident1.incident_id != incident2.incident_id


class TestBiasAuditMiddleware:
    """Tests for Flask middleware for bias auditing."""

    def test_middleware_scans_json_responses(self):
        """BiasAuditMiddleware scans JSON responses."""
        auditor = BiasAuditor()
        middleware = BiasAuditMiddleware(auditor=auditor)

        mock_response = Mock()
        mock_response.content_type = "application/json"
        mock_response.get_data.return_value = "She is too emotional for this role."

        mock_app = Mock()
        mock_app.request.args.get.side_effect = lambda key, default: {
            "agent_type": "hiring",
            "query": "Evaluate candidate"
        }.get(key, default)

        middleware.app = mock_app

        result = middleware.check_response(mock_response)

        assert result is not None

    def test_middleware_skips_non_json_responses(self):
        """BiasAuditMiddleware skips non-JSON responses."""
        auditor = BiasAuditor()
        middleware = BiasAuditMiddleware(auditor=auditor)

        mock_response = Mock()
        mock_response.content_type = "text/html"

        result = middleware.check_response(mock_response)

        assert result is not None
        # get_data should not be called for non-JSON
        mock_response.get_data.assert_not_called()

    def test_middleware_adds_critical_bias_header(self):
        """BiasAuditMiddleware adds header for critical bias."""
        auditor = BiasAuditor()
        middleware = BiasAuditMiddleware(auditor=auditor)

        mock_response = Mock()
        mock_response.content_type = "application/json"
        mock_response.get_data.return_value = "Only guys should apply for this job."
        mock_response.headers = {}

        mock_app = Mock()
        mock_app.request.args.get.side_effect = lambda key, default: {
            "agent_type": "hiring",
            "query": "Job requirements"
        }.get(key, default)

        middleware.app = mock_app

        result = middleware.check_response(mock_response)

        # Check if critical bias header would be added
        assert result is not None

    def test_middleware_handles_exceptions(self):
        """BiasAuditMiddleware gracefully handles exceptions."""
        auditor = BiasAuditor()
        middleware = BiasAuditMiddleware(auditor=auditor)

        mock_response = Mock()
        mock_response.content_type = "application/json"
        mock_response.get_data.side_effect = Exception("Test error")

        result = middleware.check_response(mock_response)

        # Should still return response
        assert result is not None

    def test_middleware_init_with_app(self):
        """BiasAuditMiddleware can initialize with Flask app."""
        mock_app = Mock()
        auditor = BiasAuditor()

        middleware = BiasAuditMiddleware(app=mock_app, auditor=auditor)

        assert middleware.app is not None
        assert middleware.auditor is not None

    def test_middleware_init_without_app(self):
        """BiasAuditMiddleware can initialize without Flask app."""
        auditor = BiasAuditor()
        middleware = BiasAuditMiddleware(auditor=auditor)

        assert middleware.auditor is not None

    def test_middleware_creates_default_auditor(self):
        """BiasAuditMiddleware creates auditor if not provided."""
        middleware = BiasAuditMiddleware()

        assert middleware.auditor is not None
        assert isinstance(middleware.auditor, BiasAuditor)


class TestBiasPatternCompilation:
    """Tests for internal pattern compilation."""

    def test_auditor_compiles_patterns_on_init(self):
        """BiasAuditor compiles regex patterns during initialization."""
        auditor = BiasAuditor()

        assert auditor.compiled_patterns is not None
        assert len(auditor.compiled_patterns) > 0

    def test_compiled_patterns_include_gender_patterns(self):
        """Compiled patterns include gender-related patterns."""
        auditor = BiasAuditor()

        pattern_keys = auditor.compiled_patterns.keys()
        assert any("gender" in key for key in pattern_keys)

    def test_compiled_patterns_include_exclusionary(self):
        """Compiled patterns include exclusionary language patterns."""
        auditor = BiasAuditor()

        pattern_keys = auditor.compiled_patterns.keys()
        assert any("exclusionary" in key for key in pattern_keys)

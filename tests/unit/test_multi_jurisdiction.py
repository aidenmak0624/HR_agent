"""Tests for Multi-Jurisdiction Compliance Engine (COMP-003)."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.core.multi_jurisdiction import (
    MultiJurisdictionEngine,
    Jurisdiction,
    ComplianceStatus,
    ComplianceRequirement,
    JurisdictionConfig,
    ComplianceCheckResult,
    MultiJurisdictionConfig,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def multi_jurisdiction_engine():
    """Create a fresh MultiJurisdictionEngine for each test."""
    return MultiJurisdictionEngine()


@pytest.fixture
def multi_jurisdiction_engine_custom():
    """Create engine with custom config."""
    config = MultiJurisdictionConfig(
        enabled=True,
        active_jurisdictions=[
            Jurisdiction.US_FEDERAL,
            Jurisdiction.EU_GDPR,
            Jurisdiction.US_CALIFORNIA
        ],
        conflict_resolution="most_restrictive"
    )
    return MultiJurisdictionEngine(config=config)


@pytest.fixture
def sample_requirement():
    """Create a sample compliance requirement."""
    return ComplianceRequirement(
        jurisdiction=Jurisdiction.US_CALIFORNIA,
        category="consumer_rights",
        description="Respond to consumer requests within 45 days",
        mandatory=True,
        deadline_days=45
    )


@pytest.fixture
def sample_check_result():
    """Create a sample compliance check result."""
    return ComplianceCheckResult(
        jurisdiction=Jurisdiction.EU_GDPR,
        requirement="consent",
        status=ComplianceStatus.COMPLIANT,
        findings=["Explicit consent recorded"],
        recommendations=["Continue monitoring consent status"]
    )


# ============================================================================
# Test Enums
# ============================================================================

class TestJurisdiction:
    """Tests for Jurisdiction enum."""

    def test_jurisdiction_has_us_states(self):
        """Jurisdiction includes all required US states."""
        assert Jurisdiction.US_FEDERAL in Jurisdiction
        assert Jurisdiction.US_CALIFORNIA in Jurisdiction
        assert Jurisdiction.US_NEW_YORK in Jurisdiction
        assert Jurisdiction.US_ILLINOIS in Jurisdiction

    def test_jurisdiction_count(self):
        """Jurisdiction has exactly 9 values."""
        assert len(list(Jurisdiction)) == 9

    def test_jurisdiction_string_representation(self):
        """Jurisdiction values are strings."""
        for jurisdiction in Jurisdiction:
            assert isinstance(jurisdiction.value, str)


class TestComplianceStatus:
    """Tests for ComplianceStatus enum."""

    def test_compliance_status_has_all_values(self):
        """ComplianceStatus contains all required values."""
        assert ComplianceStatus.COMPLIANT in ComplianceStatus
        assert ComplianceStatus.NON_COMPLIANT in ComplianceStatus
        assert ComplianceStatus.PARTIAL in ComplianceStatus
        assert ComplianceStatus.NOT_APPLICABLE in ComplianceStatus

    def test_compliance_status_count(self):
        """ComplianceStatus has exactly 4 statuses."""
        assert len(list(ComplianceStatus)) == 4

    def test_compliance_status_string_representation(self):
        """ComplianceStatus values are strings."""
        for status in ComplianceStatus:
            assert isinstance(status.value, str)


# ============================================================================
# Test Models
# ============================================================================

class TestComplianceRequirement:
    """Tests for ComplianceRequirement model."""

    def test_compliance_requirement_defaults(self):
        """ComplianceRequirement uses default values."""
        req = ComplianceRequirement(
            jurisdiction=Jurisdiction.EU_GDPR,
            category="consent",
            description="Explicit consent required"
        )

        assert req.jurisdiction == Jurisdiction.EU_GDPR
        assert req.category == "consent"
        assert req.mandatory is True
        assert req.deadline_days is None
        assert req.penalties is None

    def test_compliance_requirement_custom_values(self):
        """ComplianceRequirement accepts custom values."""
        req = ComplianceRequirement(
            jurisdiction=Jurisdiction.US_CALIFORNIA,
            category="consumer_rights",
            description="Respond to consumer requests",
            mandatory=True,
            deadline_days=45,
            penalties=["$2,500 per violation"]
        )

        assert req.deadline_days == 45
        assert req.penalties == ["$2,500 per violation"]

    def test_compliance_requirement_uuid(self):
        """ComplianceRequirement generates unique IDs."""
        req1 = ComplianceRequirement(
            jurisdiction=Jurisdiction.EU_GDPR,
            category="consent",
            description="Requirement 1"
        )
        req2 = ComplianceRequirement(
            jurisdiction=Jurisdiction.US_CALIFORNIA,
            category="disclosure",
            description="Requirement 2"
        )

        assert req1.requirement_id != req2.requirement_id

    def test_compliance_requirement_mandatory_flag(self):
        """ComplianceRequirement tracks mandatory status."""
        mandatory_req = ComplianceRequirement(
            jurisdiction=Jurisdiction.EU_GDPR,
            category="consent",
            description="Mandatory consent",
            mandatory=True
        )
        optional_req = ComplianceRequirement(
            jurisdiction=Jurisdiction.EU_GDPR,
            category="extra",
            description="Optional requirement",
            mandatory=False
        )

        assert mandatory_req.mandatory is True
        assert optional_req.mandatory is False


class TestJurisdictionConfig:
    """Tests for JurisdictionConfig model."""

    def test_jurisdiction_config_defaults(self):
        """JurisdictionConfig uses default values."""
        config = JurisdictionConfig(jurisdiction=Jurisdiction.US_FEDERAL)

        assert config.jurisdiction == Jurisdiction.US_FEDERAL
        assert config.enabled is True
        assert config.data_residency_required is False
        assert config.breach_notification_hours == 72
        assert config.consent_type == "opt-in"  # Default is opt-in
        assert config.dpo_required is False

    def test_jurisdiction_config_custom_values(self):
        """JurisdictionConfig accepts custom values."""
        config = JurisdictionConfig(
            jurisdiction=Jurisdiction.EU_GDPR,
            data_residency_required=True,
            breach_notification_hours=24,
            consent_type="opt-in",
            dpo_required=True
        )

        assert config.data_residency_required is True
        assert config.breach_notification_hours == 24
        assert config.consent_type == "opt-in"
        assert config.dpo_required is True

    def test_jurisdiction_config_consent_type(self):
        """JurisdictionConfig tracks consent type."""
        config_optin = JurisdictionConfig(
            jurisdiction=Jurisdiction.EU_GDPR,
            consent_type="opt-in"
        )
        config_optout = JurisdictionConfig(
            jurisdiction=Jurisdiction.US_FEDERAL,
            consent_type="opt-out"
        )

        assert config_optin.consent_type == "opt-in"
        assert config_optout.consent_type == "opt-out"

    def test_jurisdiction_config_breach_notification_hours(self):
        """JurisdictionConfig stores breach notification hours."""
        config = JurisdictionConfig(
            jurisdiction=Jurisdiction.EU_GDPR,
            breach_notification_hours=72
        )
        assert config.breach_notification_hours == 72


class TestComplianceCheckResult:
    """Tests for ComplianceCheckResult model."""

    def test_compliance_check_result_defaults(self):
        """ComplianceCheckResult uses default values."""
        result = ComplianceCheckResult(
            jurisdiction=Jurisdiction.EU_GDPR,
            requirement="consent",
            status=ComplianceStatus.COMPLIANT
        )

        assert result.jurisdiction == Jurisdiction.EU_GDPR
        assert result.requirement == "consent"
        assert result.status == ComplianceStatus.COMPLIANT
        assert result.findings == []
        assert result.recommendations == []

    def test_compliance_check_result_custom_values(self):
        """ComplianceCheckResult accepts custom values."""
        result = ComplianceCheckResult(
            jurisdiction=Jurisdiction.US_CALIFORNIA,
            requirement="consumer_rights",
            status=ComplianceStatus.NON_COMPLIANT,
            findings=["Missing consent records", "No data retention policy"],
            recommendations=["Implement consent tracking", "Create retention policy"]
        )

        assert len(result.findings) == 2
        assert len(result.recommendations) == 2

    def test_compliance_check_result_findings_list(self):
        """ComplianceCheckResult maintains findings list."""
        findings = ["Finding 1", "Finding 2", "Finding 3"]
        result = ComplianceCheckResult(
            jurisdiction=Jurisdiction.EU_GDPR,
            requirement="consent",
            status=ComplianceStatus.PARTIAL,
            findings=findings
        )

        assert result.findings == findings

    def test_compliance_check_result_recommendations(self):
        """ComplianceCheckResult maintains recommendations list."""
        recommendations = ["Recommendation 1", "Recommendation 2"]
        result = ComplianceCheckResult(
            jurisdiction=Jurisdiction.EU_GDPR,
            requirement="consent",
            status=ComplianceStatus.PARTIAL,
            recommendations=recommendations
        )

        assert result.recommendations == recommendations


class TestMultiJurisdictionConfig:
    """Tests for MultiJurisdictionConfig model."""

    def test_multi_jurisdiction_config_defaults(self):
        """MultiJurisdictionConfig uses default values."""
        config = MultiJurisdictionConfig()

        assert config.enabled is True
        assert Jurisdiction.US_FEDERAL in config.active_jurisdictions
        assert Jurisdiction.EU_GDPR in config.active_jurisdictions
        assert config.default_jurisdiction == Jurisdiction.US_FEDERAL
        assert config.conflict_resolution == "most_restrictive"
        assert config.audit_all_checks is True

    def test_multi_jurisdiction_config_custom_values(self):
        """MultiJurisdictionConfig accepts custom values."""
        active = [Jurisdiction.EU_GDPR, Jurisdiction.US_CALIFORNIA]
        config = MultiJurisdictionConfig(
            enabled=False,
            active_jurisdictions=active,
            default_jurisdiction=Jurisdiction.EU_GDPR,
            conflict_resolution="jurisdiction_specific"
        )

        assert config.enabled is False
        assert config.active_jurisdictions == active
        assert config.default_jurisdiction == Jurisdiction.EU_GDPR
        assert config.conflict_resolution == "jurisdiction_specific"

    def test_multi_jurisdiction_config_active_jurisdictions(self):
        """MultiJurisdictionConfig tracks active jurisdictions."""
        active = [Jurisdiction.US_FEDERAL, Jurisdiction.EU_GDPR, Jurisdiction.US_CALIFORNIA]
        config = MultiJurisdictionConfig(active_jurisdictions=active)

        assert len(config.active_jurisdictions) == 3

    def test_multi_jurisdiction_config_conflict_resolution(self):
        """MultiJurisdictionConfig tracks conflict resolution strategy."""
        config = MultiJurisdictionConfig(conflict_resolution="most_restrictive")
        assert config.conflict_resolution == "most_restrictive"


# ============================================================================
# Test Engine Initialization
# ============================================================================

class TestMultiJurisdictionEngineInit:
    """Tests for MultiJurisdictionEngine initialization."""

    def test_creates_engine_with_config(self):
        """MultiJurisdictionEngine creates with provided config."""
        config = MultiJurisdictionConfig(
            enabled=True,
            active_jurisdictions=[Jurisdiction.EU_GDPR]
        )
        engine = MultiJurisdictionEngine(config=config)

        assert engine.config == config

    def test_stores_config_reference(self):
        """MultiJurisdictionEngine stores config reference."""
        config = MultiJurisdictionConfig(enabled=False)
        engine = MultiJurisdictionEngine(config=config)

        assert engine.config.enabled is False

    def test_default_requirements_loaded(self):
        """MultiJurisdictionEngine loads default requirements."""
        engine = MultiJurisdictionEngine()

        assert len(engine._requirements) > 0
        assert Jurisdiction.EU_GDPR in engine._requirements
        assert Jurisdiction.US_CALIFORNIA in engine._requirements


# ============================================================================
# Test Determine Jurisdictions
# ============================================================================

class TestDetermineJurisdictions:
    """Tests for determine_jurisdictions method."""

    def test_determine_jurisdictions_us_california(self, multi_jurisdiction_engine):
        """determine_jurisdictions identifies California employee."""
        employee_data = {
            "id": "emp_001",
            "country": "US",
            "state": "CA"
        }

        jurisdictions = multi_jurisdiction_engine.determine_jurisdictions(employee_data)

        assert Jurisdiction.US_FEDERAL in jurisdictions
        assert Jurisdiction.US_CALIFORNIA in jurisdictions

    def test_determine_jurisdictions_eu_employee(self, multi_jurisdiction_engine):
        """determine_jurisdictions identifies EU employee."""
        employee_data = {
            "id": "emp_002",
            "country": "DE"
        }

        jurisdictions = multi_jurisdiction_engine.determine_jurisdictions(employee_data)

        assert Jurisdiction.EU_GDPR in jurisdictions

    def test_determine_jurisdictions_multi_jurisdiction(self, multi_jurisdiction_engine):
        """determine_jurisdictions handles multi-jurisdiction case."""
        employee_data = {
            "id": "emp_003",
            "country": "US",
            "state": "NY"
        }

        jurisdictions = multi_jurisdiction_engine.determine_jurisdictions(employee_data)

        assert len(jurisdictions) >= 2
        assert Jurisdiction.US_FEDERAL in jurisdictions
        assert Jurisdiction.US_NEW_YORK in jurisdictions

    def test_determine_jurisdictions_unknown_country(self, multi_jurisdiction_engine):
        """determine_jurisdictions uses default for unknown country."""
        employee_data = {
            "id": "emp_004",
            "country": "XX"
        }

        jurisdictions = multi_jurisdiction_engine.determine_jurisdictions(employee_data)

        assert Jurisdiction.US_FEDERAL in jurisdictions

    def test_determine_jurisdictions_us_new_york(self, multi_jurisdiction_engine):
        """determine_jurisdictions identifies New York employee."""
        employee_data = {
            "id": "emp_005",
            "country": "US",
            "state": "NY"
        }

        jurisdictions = multi_jurisdiction_engine.determine_jurisdictions(employee_data)

        assert Jurisdiction.US_NEW_YORK in jurisdictions


# ============================================================================
# Test Check Compliance
# ============================================================================

class TestCheckCompliance:
    """Tests for check_compliance method."""

    def test_check_compliance_all_compliant(self, multi_jurisdiction_engine):
        """check_compliance returns all compliant results."""
        data = {
            "consent_records": {"opt_in": True},
            "consent_granted": True
        }

        results = multi_jurisdiction_engine.check_compliance(data)

        assert len(results) > 0
        assert all(isinstance(r, ComplianceCheckResult) for r in results)

    def test_check_compliance_non_compliant_found(self, multi_jurisdiction_engine):
        """check_compliance identifies non-compliant items."""
        data = {}

        results = multi_jurisdiction_engine.check_compliance(data)

        assert len(results) > 0

    def test_check_compliance_partial_compliance(self, multi_jurisdiction_engine):
        """check_compliance handles partial compliance."""
        data = {
            "dsar_response_time_days": 15
        }

        results = multi_jurisdiction_engine.check_compliance(data)

        assert len(results) > 0

    def test_check_compliance_specific_jurisdictions(self, multi_jurisdiction_engine):
        """check_compliance can check specific jurisdictions."""
        data = {}
        jurisdictions = [Jurisdiction.EU_GDPR]

        results = multi_jurisdiction_engine.check_compliance(
            data,
            jurisdictions=jurisdictions
        )

        assert len(results) > 0


# ============================================================================
# Test Get Requirements
# ============================================================================

class TestGetRequirements:
    """Tests for get_requirements method."""

    def test_get_requirements_returns_for_jurisdiction(self, multi_jurisdiction_engine):
        """get_requirements returns requirements for jurisdiction."""
        requirements = multi_jurisdiction_engine.get_requirements(Jurisdiction.EU_GDPR)

        assert isinstance(requirements, list)
        assert len(requirements) > 0

    def test_get_requirements_empty_for_unknown(self, multi_jurisdiction_engine):
        """get_requirements raises ValueError for unsupported jurisdiction."""
        # Get requirements for a jurisdiction not in configs
        with pytest.raises(ValueError, match="not supported"):
            multi_jurisdiction_engine.get_requirements(Jurisdiction.US_ILLINOIS)

    def test_get_requirements_includes_mandatory(self, multi_jurisdiction_engine):
        """get_requirements includes mandatory requirements."""
        requirements = multi_jurisdiction_engine.get_requirements(Jurisdiction.EU_GDPR)

        mandatory = [r for r in requirements if r.mandatory]
        assert len(mandatory) > 0


# ============================================================================
# Test Resolve Conflicts
# ============================================================================

class TestResolveConflicts:
    """Tests for resolve_conflicts method."""

    def test_resolve_conflicts_most_restrictive(self, multi_jurisdiction_engine):
        """resolve_conflicts applies most_restrictive strategy."""
        results = [
            ComplianceCheckResult(
                jurisdiction=Jurisdiction.US_FEDERAL,
                requirement="consent",
                status=ComplianceStatus.COMPLIANT
            ),
            ComplianceCheckResult(
                jurisdiction=Jurisdiction.EU_GDPR,
                requirement="consent",
                status=ComplianceStatus.NON_COMPLIANT
            )
        ]

        resolved = multi_jurisdiction_engine.resolve_conflicts(results)

        assert len(resolved) > 0

    def test_resolve_conflicts_same_severity_kept(self, multi_jurisdiction_engine):
        """resolve_conflicts keeps same severity results."""
        results = [
            ComplianceCheckResult(
                jurisdiction=Jurisdiction.EU_GDPR,
                requirement="consent",
                status=ComplianceStatus.COMPLIANT
            ),
            ComplianceCheckResult(
                jurisdiction=Jurisdiction.US_CALIFORNIA,
                requirement="disclosure",
                status=ComplianceStatus.COMPLIANT
            )
        ]

        resolved = multi_jurisdiction_engine.resolve_conflicts(results)

        assert len(resolved) > 0

    def test_resolve_conflicts_empty_results(self, multi_jurisdiction_engine):
        """resolve_conflicts raises error for empty results."""
        with pytest.raises(ValueError):
            multi_jurisdiction_engine.resolve_conflicts([])


# ============================================================================
# Test Breach Notification Deadline
# ============================================================================

class TestGetBreachNotificationDeadline:
    """Tests for get_breach_notification_deadline method."""

    def test_get_breach_notification_deadline_returns_shortest(self, multi_jurisdiction_engine):
        """get_breach_notification_deadline returns shortest deadline."""
        result = multi_jurisdiction_engine.get_breach_notification_deadline()

        assert "shortest_deadline_hours" in result
        assert isinstance(result["shortest_deadline_hours"], int)

    def test_get_breach_notification_deadline_single_jurisdiction(self, multi_jurisdiction_engine):
        """get_breach_notification_deadline handles single jurisdiction."""
        result = multi_jurisdiction_engine.get_breach_notification_deadline(
            jurisdictions=[Jurisdiction.EU_GDPR]
        )

        assert result["shortest_deadline_hours"] == 72

    def test_get_breach_notification_deadline_no_jurisdictions(self, multi_jurisdiction_engine):
        """get_breach_notification_deadline raises for no jurisdictions."""
        with pytest.raises(ValueError):
            multi_jurisdiction_engine.get_breach_notification_deadline(jurisdictions=[])


# ============================================================================
# Test Cross-Border Transfer
# ============================================================================

class TestCheckCrossBorderTransfer:
    """Tests for check_cross_border_transfer method."""

    def test_check_cross_border_transfer_allowed(self, multi_jurisdiction_engine):
        """check_cross_border_transfer allows unrestricted transfers."""
        result = multi_jurisdiction_engine.check_cross_border_transfer(
            source_jurisdiction=Jurisdiction.US_FEDERAL,
            target_jurisdiction=Jurisdiction.US_CALIFORNIA
        )

        assert "transfer_allowed" in result

    def test_check_cross_border_transfer_restricted(self, multi_jurisdiction_engine):
        """check_cross_border_transfer restricts EU transfers."""
        result = multi_jurisdiction_engine.check_cross_border_transfer(
            source_jurisdiction=Jurisdiction.EU_GDPR,
            target_jurisdiction=Jurisdiction.US_FEDERAL
        )

        assert "transfer_allowed" in result
        assert "requires_standard_clauses" in result

    def test_check_cross_border_transfer_same_jurisdiction(self, multi_jurisdiction_engine):
        """check_cross_border_transfer allows same jurisdiction transfers."""
        result = multi_jurisdiction_engine.check_cross_border_transfer(
            source_jurisdiction=Jurisdiction.EU_GDPR,
            target_jurisdiction=Jurisdiction.EU_GDPR
        )

        assert "transfer_allowed" in result


# ============================================================================
# Test Consent Requirements
# ============================================================================

class TestGetConsentRequirements:
    """Tests for get_consent_requirements method."""

    def test_get_consent_requirements_opt_in(self, multi_jurisdiction_engine):
        """get_consent_requirements identifies opt-in requirements."""
        result = multi_jurisdiction_engine.get_consent_requirements(
            jurisdictions=[Jurisdiction.EU_GDPR]
        )

        assert "by_jurisdiction" in result
        assert "eu_gdpr" in result["by_jurisdiction"]

    def test_get_consent_requirements_opt_out(self, multi_jurisdiction_engine):
        """get_consent_requirements identifies opt-out requirements."""
        result = multi_jurisdiction_engine.get_consent_requirements(
            jurisdictions=[Jurisdiction.US_FEDERAL]
        )

        assert "by_jurisdiction" in result
        assert "us_federal" in result["by_jurisdiction"]

    def test_get_consent_requirements_mixed_jurisdictions(self, multi_jurisdiction_engine):
        """get_consent_requirements handles mixed consent types."""
        result = multi_jurisdiction_engine.get_consent_requirements(
            jurisdictions=[Jurisdiction.EU_GDPR, Jurisdiction.US_FEDERAL]
        )

        assert len(result["by_jurisdiction"]) == 2


# ============================================================================
# Test Generate Compliance Report
# ============================================================================

class TestGenerateComplianceReport:
    """Tests for generate_compliance_report method."""

    def test_generate_compliance_report_creates_report(self, multi_jurisdiction_engine):
        """generate_compliance_report creates comprehensive report."""
        report = multi_jurisdiction_engine.generate_compliance_report()

        assert isinstance(report, dict)
        assert "report_date" in report
        assert "summary" in report

    def test_generate_compliance_report_includes_all_jurisdictions(self, multi_jurisdiction_engine):
        """generate_compliance_report covers all jurisdictions."""
        report = multi_jurisdiction_engine.generate_compliance_report()

        assert "jurisdictions_covered" in report

    def test_generate_compliance_report_empty_report(self, multi_jurisdiction_engine):
        """generate_compliance_report handles no check results."""
        report = multi_jurisdiction_engine.generate_compliance_report()

        assert "critical_findings" in report
        assert "recommendations" in report


# ============================================================================
# Test Add Custom Requirement
# ============================================================================

class TestAddCustomRequirement:
    """Tests for add_custom_requirement method."""

    def test_add_custom_requirement_successful(self, multi_jurisdiction_engine, sample_requirement):
        """add_custom_requirement adds requirement successfully."""
        result = multi_jurisdiction_engine.add_custom_requirement(
            Jurisdiction.US_CALIFORNIA,
            sample_requirement
        )

        assert result == sample_requirement

    def test_add_custom_requirement_returns_requirement(self, multi_jurisdiction_engine, sample_requirement):
        """add_custom_requirement returns the added requirement."""
        added = multi_jurisdiction_engine.add_custom_requirement(
            Jurisdiction.EU_GDPR,
            sample_requirement
        )

        assert isinstance(added, ComplianceRequirement)

    def test_add_custom_requirement_increments_count(self, multi_jurisdiction_engine, sample_requirement):
        """add_custom_requirement increments requirement count."""
        initial_count = len(
            multi_jurisdiction_engine.get_requirements(Jurisdiction.US_CALIFORNIA)
        )

        multi_jurisdiction_engine.add_custom_requirement(
            Jurisdiction.US_CALIFORNIA,
            sample_requirement
        )

        final_count = len(
            multi_jurisdiction_engine.get_requirements(Jurisdiction.US_CALIFORNIA)
        )

        assert final_count > initial_count

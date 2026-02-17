"""
COMP-003: Multi-Jurisdiction Compliance Engine.

Provides multi-jurisdiction compliance management for GDPR, CCPA, PIPEDA, LGPD,
and other regulatory frameworks with conflict resolution and integrated checking.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class Jurisdiction(str, Enum):
    """Supported jurisdictions for compliance."""

    US_FEDERAL = "us_federal"
    US_CALIFORNIA = "us_california"
    US_NEW_YORK = "us_new_york"
    US_ILLINOIS = "us_illinois"
    EU_GDPR = "eu_gdpr"
    UK_GDPR = "uk_gdpr"
    CANADA_PIPEDA = "canada_pipeda"
    AUSTRALIA_APPS = "australia_apps"
    BRAZIL_LGPD = "brazil_lgpd"


class ComplianceStatus(str, Enum):
    """Status of compliance check."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


# ============================================================================
# Pydantic Models
# ============================================================================


class ComplianceRequirement(BaseModel):
    """Specific compliance requirement for a jurisdiction."""

    requirement_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique requirement ID"
    )
    jurisdiction: Jurisdiction = Field(..., description="Jurisdiction this applies to")
    category: str = Field(..., description="Category of requirement")
    description: str = Field(..., description="Description of requirement")
    mandatory: bool = Field(default=True, description="Whether requirement is mandatory")
    deadline_days: Optional[int] = Field(None, description="Deadline in days if applicable")
    penalties: Optional[List[str]] = Field(
        None, description="Potential penalties for non-compliance"
    )

    model_config = ConfigDict(use_enum_values=False)


class JurisdictionConfig(BaseModel):
    """Configuration for a jurisdiction."""

    jurisdiction: Jurisdiction = Field(..., description="Jurisdiction")
    enabled: bool = Field(default=True, description="Whether compliance checks are enabled")
    data_residency_required: bool = Field(
        default=False, description="Whether data must reside in jurisdiction"
    )
    breach_notification_hours: int = Field(default=72, description="Hours to notify of breach")
    consent_type: str = Field(default="opt-in", description="Consent model: opt-in or opt-out")
    dpo_required: bool = Field(
        default=False, description="Whether Data Protection Officer required"
    )
    cross_border_transfer_mechanism: str = Field(
        default="standard_contractual_clauses", description="Mechanism for cross-border transfers"
    )

    model_config = ConfigDict(use_enum_values=False)


class ComplianceCheckResult(BaseModel):
    """Result of a compliance check."""

    check_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique check ID")
    jurisdiction: Jurisdiction = Field(..., description="Jurisdiction checked")
    requirement: str = Field(..., description="Requirement checked")
    status: ComplianceStatus = Field(..., description="Compliance status")
    findings: List[str] = Field(default_factory=list, description="Specific findings")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")
    checked_at: datetime = Field(
        default_factory=datetime.utcnow, description="When check was performed"
    )

    model_config = ConfigDict(use_enum_values=False)


class MultiJurisdictionConfig(BaseModel):
    """Configuration for multi-jurisdiction engine."""

    enabled: bool = Field(default=True, description="Whether multi-jurisdiction checking enabled")
    active_jurisdictions: List[Jurisdiction] = Field(
        default_factory=lambda: [Jurisdiction.US_FEDERAL, Jurisdiction.EU_GDPR],
        description="Active jurisdictions to check",
    )
    default_jurisdiction: Jurisdiction = Field(
        default=Jurisdiction.US_FEDERAL, description="Default jurisdiction"
    )
    conflict_resolution: str = Field(
        default="most_restrictive",
        description="Strategy: most_restrictive or jurisdiction_specific",
    )
    audit_all_checks: bool = Field(
        default=True, description="Whether to audit all compliance checks"
    )

    model_config = ConfigDict(use_enum_values=False)


# ============================================================================
# Multi-Jurisdiction Compliance Engine
# ============================================================================


class MultiJurisdictionEngine:
    """
    Multi-jurisdiction compliance engine for managing requirements across
    multiple regulatory frameworks including GDPR, CCPA, PIPEDA, LGPD, and others.

    Handles jurisdiction determination, compliance checking, conflict resolution,
    and integrated reporting across multiple jurisdictions.
    """

    def __init__(
        self,
        config: Optional[MultiJurisdictionConfig] = None,
        gdpr_service: Optional[Any] = None,
        ccpa_service: Optional[Any] = None,
        audit_logger: Optional[Any] = None,
    ):
        """
        Initialize multi-jurisdiction compliance engine.

        Args:
            config: MultiJurisdictionConfig object
            gdpr_service: Optional GDPR compliance service
            ccpa_service: Optional CCPA compliance service
            audit_logger: Optional audit logger
        """
        self.config = config or MultiJurisdictionConfig()
        self.gdpr_service = gdpr_service
        self.ccpa_service = ccpa_service
        self.audit_logger = audit_logger

        # In-memory storage
        self._jurisdiction_configs: Dict[Jurisdiction, JurisdictionConfig] = {}
        self._requirements: Dict[Jurisdiction, List[ComplianceRequirement]] = {}
        self._check_results: Dict[str, ComplianceCheckResult] = {}
        self._audit_trail: List[Dict[str, Any]] = []
        self._custom_requirements: Dict[Jurisdiction, List[ComplianceRequirement]] = {}

        # Initialize default jurisdiction configs
        self._init_default_configs()

        logger.info(
            "MultiJurisdictionEngine initialized with %d active jurisdictions",
            len(self.config.active_jurisdictions),
        )

    def _init_default_configs(self) -> None:
        """Initialize default jurisdiction configurations."""
        try:
            defaults = {
                Jurisdiction.US_FEDERAL: JurisdictionConfig(
                    jurisdiction=Jurisdiction.US_FEDERAL,
                    breach_notification_hours=72,
                    consent_type="opt-out",
                ),
                Jurisdiction.US_CALIFORNIA: JurisdictionConfig(
                    jurisdiction=Jurisdiction.US_CALIFORNIA,
                    breach_notification_hours=48,
                    consent_type="opt-out",
                ),
                Jurisdiction.EU_GDPR: JurisdictionConfig(
                    jurisdiction=Jurisdiction.EU_GDPR,
                    data_residency_required=True,
                    breach_notification_hours=72,
                    consent_type="opt-in",
                    dpo_required=True,
                    cross_border_transfer_mechanism="standard_contractual_clauses",
                ),
                Jurisdiction.UK_GDPR: JurisdictionConfig(
                    jurisdiction=Jurisdiction.UK_GDPR,
                    data_residency_required=False,
                    breach_notification_hours=72,
                    consent_type="opt-in",
                    dpo_required=True,
                ),
                Jurisdiction.CANADA_PIPEDA: JurisdictionConfig(
                    jurisdiction=Jurisdiction.CANADA_PIPEDA,
                    breach_notification_hours=168,
                    consent_type="opt-in",
                ),
                Jurisdiction.AUSTRALIA_APPS: JurisdictionConfig(
                    jurisdiction=Jurisdiction.AUSTRALIA_APPS,
                    breach_notification_hours=168,
                    consent_type="opt-in",
                ),
                Jurisdiction.BRAZIL_LGPD: JurisdictionConfig(
                    jurisdiction=Jurisdiction.BRAZIL_LGPD,
                    breach_notification_hours=72,
                    consent_type="opt-in",
                ),
            }

            self._jurisdiction_configs = defaults
            self._init_default_requirements()
        except Exception as e:
            logger.error("Failed to initialize default configs: %s", str(e))
            raise

    def _init_default_requirements(self) -> None:
        """Initialize default compliance requirements by jurisdiction."""
        try:
            # EU GDPR requirements
            self._requirements[Jurisdiction.EU_GDPR] = [
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.EU_GDPR,
                    category="consent",
                    description="Explicit informed consent required for data processing",
                    mandatory=True,
                    deadline_days=None,
                    penalties=["Up to 4% of annual revenue"],
                ),
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.EU_GDPR,
                    category="dsar",
                    description="Data Subject Access Request response within 30 days",
                    mandatory=True,
                    deadline_days=30,
                    penalties=["Up to 4% of annual revenue"],
                ),
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.EU_GDPR,
                    category="breach_notification",
                    description="Breach notification within 72 hours",
                    mandatory=True,
                    deadline_days=0,
                    penalties=["Up to 4% of annual revenue"],
                ),
            ]

            # US CCPA requirements
            self._requirements[Jurisdiction.US_CALIFORNIA] = [
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.US_CALIFORNIA,
                    category="disclosure",
                    description="Disclosure of data collection practices",
                    mandatory=True,
                    deadline_days=None,
                    penalties=["$2,500 per violation, $7,500 per intentional violation"],
                ),
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.US_CALIFORNIA,
                    category="consumer_rights",
                    description="Respond to consumer requests within 45 days",
                    mandatory=True,
                    deadline_days=45,
                    penalties=["$2,500 per violation"],
                ),
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.US_CALIFORNIA,
                    category="opt_out",
                    description="Honor opt-out of sale of personal information",
                    mandatory=True,
                    deadline_days=None,
                    penalties=["$2,500 per violation"],
                ),
            ]

            # Canada PIPEDA requirements
            self._requirements[Jurisdiction.CANADA_PIPEDA] = [
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.CANADA_PIPEDA,
                    category="consent",
                    description="Meaningful consent for collection and use",
                    mandatory=True,
                    deadline_days=None,
                    penalties=["Compliance order, damages to affected individuals"],
                ),
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.CANADA_PIPEDA,
                    category="access",
                    description="Provide access within 30 days upon request",
                    mandatory=True,
                    deadline_days=30,
                    penalties=["Compliance order"],
                ),
            ]

            # Brazil LGPD requirements
            self._requirements[Jurisdiction.BRAZIL_LGPD] = [
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.BRAZIL_LGPD,
                    category="consent",
                    description="Free and informed consent for processing",
                    mandatory=True,
                    deadline_days=None,
                    penalties=["Up to 2% of revenue (capped at R$50 million per violation)"],
                ),
                ComplianceRequirement(
                    jurisdiction=Jurisdiction.BRAZIL_LGPD,
                    category="right_of_access",
                    description="Grant access to personal data",
                    mandatory=True,
                    deadline_days=None,
                    penalties=["Up to 2% of revenue"],
                ),
            ]

            logger.info(
                "Default requirements initialized for %d jurisdictions", len(self._requirements)
            )
        except Exception as e:
            logger.error("Failed to initialize default requirements: %s", str(e))
            raise

    def _log_audit_trail(
        self,
        action: str,
        jurisdiction: Optional[Jurisdiction] = None,
        details: Optional[Dict[str, Any]] = None,
        legal_basis: Optional[str] = None,
    ) -> None:
        """
        Log an action to audit trail.

        Args:
            action: Type of action
            jurisdiction: Jurisdiction involved (optional)
            details: Additional details
            legal_basis: Legal basis for action
        """
        try:
            entry = {
                "timestamp": datetime.utcnow(),
                "action": action,
                "jurisdiction": jurisdiction.value if jurisdiction else None,
                "details": details or {},
                "legal_basis": legal_basis,
            }
            self._audit_trail.append(entry)
            logger.info(
                "Multi-jurisdiction audit: %s for %s",
                action,
                jurisdiction.value if jurisdiction else "all",
            )
        except Exception as e:
            logger.error("Failed to log audit trail: %s", str(e))

    def determine_jurisdictions(self, employee_data: Dict[str, Any]) -> List[Jurisdiction]:
        """
        Determine applicable jurisdictions based on employee data.

        Args:
            employee_data: Employee data including country, state, residence

        Returns:
            List of applicable Jurisdiction enums

        Raises:
            ValueError: If employee_data is invalid
        """
        try:
            if not isinstance(employee_data, dict):
                raise ValueError("employee_data must be a dictionary")

            applicable = []

            # Check country
            country = employee_data.get("country", "").upper()
            state = employee_data.get("state", "").upper()
            residence = employee_data.get("residence_country", "").upper()

            # EU countries
            if country in ["DE", "FR", "IT", "ES", "NL", "BE", "AT", "PL"]:
                applicable.append(Jurisdiction.EU_GDPR)

            # UK
            if country == "GB":
                applicable.append(Jurisdiction.UK_GDPR)

            # Canada
            if country == "CA":
                applicable.append(Jurisdiction.CANADA_PIPEDA)

            # Australia
            if country == "AU":
                applicable.append(Jurisdiction.AUSTRALIA_APPS)

            # Brazil
            if country == "BR":
                applicable.append(Jurisdiction.BRAZIL_LGPD)

            # US states
            if country == "US":
                applicable.append(Jurisdiction.US_FEDERAL)
                if state == "CA":
                    applicable.append(Jurisdiction.US_CALIFORNIA)
                elif state == "NY":
                    applicable.append(Jurisdiction.US_NEW_YORK)
                elif state == "IL":
                    applicable.append(Jurisdiction.US_ILLINOIS)

            # If no specific jurisdiction found, use default
            if not applicable:
                applicable.append(self.config.default_jurisdiction)

            # Remove duplicates
            applicable = list(set(applicable))

            self._log_audit_trail(
                action="jurisdictions_determined",
                details={
                    "employee_id": employee_data.get("id"),
                    "jurisdictions": [j.value for j in applicable],
                },
                legal_basis="Multi-Jurisdiction Analysis",
            )

            logger.info("Determined %d jurisdictions for employee", len(applicable))
            return applicable
        except Exception as e:
            logger.error("Failed to determine jurisdictions: %s", str(e))
            raise

    def check_compliance(
        self, data: Dict[str, Any], jurisdictions: Optional[List[Jurisdiction]] = None
    ) -> List[ComplianceCheckResult]:
        """
        Check compliance across jurisdictions.

        Args:
            data: Employee/data dictionary to check
            jurisdictions: Optional list of jurisdictions to check (uses active if not provided)

        Returns:
            List of ComplianceCheckResult objects

        Raises:
            ValueError: If data is invalid
        """
        try:
            if not isinstance(data, dict):
                raise ValueError("data must be a dictionary")

            if jurisdictions is None:
                jurisdictions = self.config.active_jurisdictions

            results = []

            for jurisdiction in jurisdictions:
                if jurisdiction not in self._requirements:
                    continue

                requirements = self._requirements[jurisdiction]

                for requirement in requirements:
                    result = ComplianceCheckResult(
                        jurisdiction=jurisdiction,
                        requirement=requirement.category,
                        status=self._check_requirement(data, requirement),
                        findings=self._get_findings(data, requirement),
                        recommendations=self._get_recommendations(requirement),
                    )

                    results.append(result)
                    self._check_results[result.check_id] = result

                    if self.config.audit_all_checks:
                        self._log_audit_trail(
                            action="compliance_check_performed",
                            jurisdiction=jurisdiction,
                            details={
                                "requirement": requirement.category,
                                "status": result.status.value,
                            },
                            legal_basis="Compliance Verification",
                        )

            logger.info(
                "Compliance check completed: %d results across %d jurisdictions",
                len(results),
                len(jurisdictions),
            )
            return results
        except Exception as e:
            logger.error("Failed to check compliance: %s", str(e))
            raise

    def _check_requirement(
        self, data: Dict[str, Any], requirement: ComplianceRequirement
    ) -> ComplianceStatus:
        """
        Check a single requirement for compliance.

        Args:
            data: Data to check
            requirement: Requirement to check

        Returns:
            ComplianceStatus
        """
        try:
            # Simulate compliance checking based on requirement category
            if requirement.category == "consent":
                if "consent_records" in data or data.get("consent_granted", False):
                    return ComplianceStatus.COMPLIANT
                return ComplianceStatus.NON_COMPLIANT

            elif requirement.category == "dsar":
                if "dsar_response_time_days" in data:
                    response_time = data["dsar_response_time_days"]
                    if response_time <= (requirement.deadline_days or 30):
                        return ComplianceStatus.COMPLIANT
                return ComplianceStatus.PARTIAL

            elif requirement.category == "breach_notification":
                if "breach_notified_hours" in data:
                    if data["breach_notified_hours"] <= 72:
                        return ComplianceStatus.COMPLIANT
                return ComplianceStatus.NON_COMPLIANT

            elif requirement.category == "opt_out":
                if "opt_out_requested" in data:
                    return ComplianceStatus.COMPLIANT
                return ComplianceStatus.PARTIAL

            elif requirement.category == "disclosure":
                if "privacy_notice_provided" in data:
                    return ComplianceStatus.COMPLIANT
                return ComplianceStatus.NON_COMPLIANT

            return ComplianceStatus.NOT_APPLICABLE
        except Exception as e:
            logger.error("Failed to check requirement: %s", str(e))
            return ComplianceStatus.NON_COMPLIANT

    def _get_findings(self, data: Dict[str, Any], requirement: ComplianceRequirement) -> List[str]:
        """Get specific findings for a requirement."""
        findings = []

        if requirement.mandatory and requirement.category not in data:
            findings.append(f"Required {requirement.category} not found in data")

        if requirement.deadline_days and f"{requirement.category}_days" in data:
            if data[f"{requirement.category}_days"] > requirement.deadline_days:
                findings.append(
                    f"Deadline exceeded: {data[f'{requirement.category}_days']} > "
                    f"{requirement.deadline_days} days"
                )

        return findings

    def _get_recommendations(self, requirement: ComplianceRequirement) -> List[str]:
        """Get recommendations for a requirement."""
        recommendations = []

        if requirement.mandatory:
            recommendations.append(f"Implement {requirement.category} controls")

        if requirement.deadline_days:
            recommendations.append(
                f"Establish process to meet {requirement.deadline_days}-day deadline"
            )

        if requirement.penalties:
            recommendations.append(f"Understand penalties: {requirement.penalties[0]}")

        return recommendations

    def get_requirements(self, jurisdiction: Jurisdiction) -> List[ComplianceRequirement]:
        """
        Get requirements for a jurisdiction.

        Args:
            jurisdiction: Jurisdiction to get requirements for

        Returns:
            List of ComplianceRequirement objects

        Raises:
            ValueError: If jurisdiction not supported
        """
        try:
            if jurisdiction not in self._jurisdiction_configs:
                raise ValueError(f"Jurisdiction {jurisdiction.value} not supported")

            requirements = self._requirements.get(jurisdiction, [])
            custom = self._custom_requirements.get(jurisdiction, [])

            logger.info(
                "Retrieved %d requirements for %s",
                len(requirements) + len(custom),
                jurisdiction.value,
            )
            return requirements + custom
        except Exception as e:
            logger.error("Failed to get requirements: %s", str(e))
            raise

    def resolve_conflicts(
        self, results: List[ComplianceCheckResult]
    ) -> List[ComplianceCheckResult]:
        """
        Resolve conflicts across jurisdictions.

        Args:
            results: Compliance check results from multiple jurisdictions

        Returns:
            Resolved results based on conflict resolution strategy

        Raises:
            ValueError: If results invalid
        """
        try:
            if not isinstance(results, list) or not results:
                raise ValueError("Results must be non-empty list")

            if self.config.conflict_resolution == "most_restrictive":
                # Most restrictive requirement wins
                by_category = {}
                for result in results:
                    cat = result.requirement
                    if cat not in by_category:
                        by_category[cat] = result
                    else:
                        # Higher status value = more restrictive
                        if self._status_priority(result.status) > self._status_priority(
                            by_category[cat].status
                        ):
                            by_category[cat] = result

                resolved = list(by_category.values())
            else:
                # jurisdiction_specific: keep all by jurisdiction
                resolved = results

            self._log_audit_trail(
                action="conflicts_resolved",
                details={"strategy": self.config.conflict_resolution, "count": len(resolved)},
                legal_basis="Conflict Resolution",
            )

            logger.info(
                "Resolved %d conflicts using %s strategy",
                len(results) - len(resolved),
                self.config.conflict_resolution,
            )
            return resolved
        except Exception as e:
            logger.error("Failed to resolve conflicts: %s", str(e))
            raise

    def _status_priority(self, status: ComplianceStatus) -> int:
        """Get priority value for status (higher = more restrictive)."""
        priority_map = {
            ComplianceStatus.COMPLIANT: 1,
            ComplianceStatus.NOT_APPLICABLE: 2,
            ComplianceStatus.PARTIAL: 3,
            ComplianceStatus.NON_COMPLIANT: 4,
        }
        return priority_map.get(status, 0)

    def get_breach_notification_deadline(
        self, jurisdictions: Optional[List[Jurisdiction]] = None
    ) -> Dict[str, Any]:
        """
        Get shortest breach notification deadline across jurisdictions.

        Args:
            jurisdictions: Jurisdictions to check (uses active if not provided)

        Returns:
            Dictionary with shortest deadline and details

        Raises:
            ValueError: If jurisdictions invalid
        """
        try:
            if jurisdictions is None:
                jurisdictions = self.config.active_jurisdictions

            if not jurisdictions:
                raise ValueError("No jurisdictions to check")

            min_hours = float("inf")
            min_jurisdiction = None

            for jurisdiction in jurisdictions:
                if jurisdiction in self._jurisdiction_configs:
                    config = self._jurisdiction_configs[jurisdiction]
                    if config.breach_notification_hours < min_hours:
                        min_hours = config.breach_notification_hours
                        min_jurisdiction = jurisdiction

            result = {
                "shortest_deadline_hours": min_hours if min_hours != float("inf") else 72,
                "shortest_deadline_jurisdiction": (
                    min_jurisdiction.value if min_jurisdiction else None
                ),
                "by_jurisdiction": {
                    j.value: self._jurisdiction_configs[j].breach_notification_hours
                    for j in jurisdictions
                    if j in self._jurisdiction_configs
                },
            }

            logger.info("Breach notification deadline: %d hours", result["shortest_deadline_hours"])
            return result
        except Exception as e:
            logger.error("Failed to get breach notification deadline: %s", str(e))
            raise

    def check_cross_border_transfer(
        self,
        source_jurisdiction: Jurisdiction,
        target_jurisdiction: Jurisdiction,
        data_categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Check cross-border data transfer compliance.

        Args:
            source_jurisdiction: Source jurisdiction
            target_jurisdiction: Target jurisdiction
            data_categories: Data categories being transferred (optional)

        Returns:
            Dictionary with transfer compliance status

        Raises:
            ValueError: If jurisdictions invalid
        """
        try:
            if source_jurisdiction not in self._jurisdiction_configs:
                raise ValueError(f"Source jurisdiction {source_jurisdiction.value} not supported")

            if target_jurisdiction not in self._jurisdiction_configs:
                raise ValueError(f"Target jurisdiction {target_jurisdiction.value} not supported")

            source_config = self._jurisdiction_configs[source_jurisdiction]
            target_config = self._jurisdiction_configs[target_jurisdiction]

            # Check if transfer is restricted
            is_restricted = (
                source_config.data_residency_required and source_jurisdiction != target_jurisdiction
            )

            result = {
                "source_jurisdiction": source_jurisdiction.value,
                "target_jurisdiction": target_jurisdiction.value,
                "transfer_allowed": not is_restricted,
                "mechanism": source_config.cross_border_transfer_mechanism,
                "requires_standard_clauses": source_jurisdiction == Jurisdiction.EU_GDPR,
                "requires_privacy_shield": False,  # Invalidated, use SCCs
                "data_categories": data_categories or [],
            }

            self._log_audit_trail(
                action="cross_border_transfer_checked",
                details=result,
                legal_basis="Cross-Border Transfer Compliance",
            )

            logger.info(
                "Cross-border transfer check: %s → %s (allowed: %s)",
                source_jurisdiction.value,
                target_jurisdiction.value,
                result["transfer_allowed"],
            )
            return result
        except Exception as e:
            logger.error("Failed to check cross-border transfer: %s", str(e))
            raise

    def get_consent_requirements(
        self, jurisdictions: Optional[List[Jurisdiction]] = None
    ) -> Dict[str, Any]:
        """
        Get consent requirements across jurisdictions.

        Args:
            jurisdictions: Jurisdictions to check (uses active if not provided)

        Returns:
            Dictionary with consent requirements

        Raises:
            ValueError: If jurisdictions invalid
        """
        try:
            if jurisdictions is None:
                jurisdictions = self.config.active_jurisdictions

            if not jurisdictions:
                raise ValueError("No jurisdictions to check")

            consent_reqs = {}

            for jurisdiction in jurisdictions:
                if jurisdiction in self._jurisdiction_configs:
                    config = self._jurisdiction_configs[jurisdiction]
                    consent_reqs[jurisdiction.value] = {
                        "type": config.consent_type,
                        "explicit_required": config.consent_type == "opt-in",
                        "prior_to_processing": config.consent_type == "opt-in",
                    }

            result = {
                "by_jurisdiction": consent_reqs,
                "most_restrictive": "opt-in",  # Most jurisdictions require opt-in
                "requires_explicit_consent": any(
                    c.get("explicit_required") for c in consent_reqs.values()
                ),
            }

            logger.info("Consent requirements retrieved for %d jurisdictions", len(jurisdictions))
            return result
        except Exception as e:
            logger.error("Failed to get consent requirements: %s", str(e))
            raise

    def generate_compliance_report(
        self, jurisdictions: Optional[List[Jurisdiction]] = None
    ) -> Dict[str, Any]:
        """
        Generate multi-jurisdiction compliance report.

        Args:
            jurisdictions: Jurisdictions to include (uses active if not provided)

        Returns:
            Compliance report dictionary

        Raises:
            ValueError: If jurisdictions invalid
        """
        try:
            if jurisdictions is None:
                jurisdictions = self.config.active_jurisdictions

            report = {
                "report_date": datetime.utcnow().isoformat(),
                "jurisdictions_covered": [j.value for j in jurisdictions],
                "summary": {},
                "by_jurisdiction": {},
                "critical_findings": [],
                "recommendations": [],
            }

            # Analyze results
            total_checks = 0
            compliant_count = 0
            non_compliant_count = 0

            for jurisdiction in jurisdictions:
                j_results = [
                    r for r in self._check_results.values() if r.jurisdiction == jurisdiction
                ]

                if j_results:
                    compliant = sum(1 for r in j_results if r.status == ComplianceStatus.COMPLIANT)
                    non_compliant = sum(
                        1 for r in j_results if r.status == ComplianceStatus.NON_COMPLIANT
                    )

                    report["by_jurisdiction"][jurisdiction.value] = {
                        "total_checks": len(j_results),
                        "compliant": compliant,
                        "non_compliant": non_compliant,
                        "partial": sum(
                            1 for r in j_results if r.status == ComplianceStatus.PARTIAL
                        ),
                        "not_applicable": sum(
                            1 for r in j_results if r.status == ComplianceStatus.NOT_APPLICABLE
                        ),
                    }

                    total_checks += len(j_results)
                    compliant_count += compliant
                    non_compliant_count += non_compliant

                    # Add critical findings
                    for result in j_results:
                        if result.status == ComplianceStatus.NON_COMPLIANT:
                            report["critical_findings"].append(
                                {
                                    "jurisdiction": jurisdiction.value,
                                    "requirement": result.requirement,
                                    "findings": result.findings,
                                }
                            )

            report["summary"] = {
                "total_checks": total_checks,
                "compliant": compliant_count,
                "non_compliant": non_compliant_count,
                "compliance_rate": (
                    round(compliant_count / total_checks * 100, 1) if total_checks > 0 else 0
                ),
            }

            self._log_audit_trail(
                action="compliance_report_generated",
                details=report["summary"],
                legal_basis="Compliance Reporting",
            )

            logger.info(
                "Compliance report generated: %d%% compliance rate",
                report["summary"]["compliance_rate"],
            )
            return report
        except Exception as e:
            logger.error("Failed to generate compliance report: %s", str(e))
            raise

    def add_custom_requirement(
        self, jurisdiction: Jurisdiction, requirement: ComplianceRequirement
    ) -> ComplianceRequirement:
        """
        Add a custom compliance requirement for a jurisdiction.

        Args:
            jurisdiction: Jurisdiction to add requirement for
            requirement: ComplianceRequirement object

        Returns:
            The added requirement

        Raises:
            ValueError: If jurisdiction not supported
        """
        try:
            if jurisdiction not in self._jurisdiction_configs:
                raise ValueError(f"Jurisdiction {jurisdiction.value} not supported")

            if jurisdiction not in self._custom_requirements:
                self._custom_requirements[jurisdiction] = []

            self._custom_requirements[jurisdiction].append(requirement)

            self._log_audit_trail(
                action="custom_requirement_added",
                jurisdiction=jurisdiction,
                details={"category": requirement.category, "mandatory": requirement.mandatory},
                legal_basis="Custom Requirement",
            )

            logger.info(
                "Custom requirement added for %s: %s", jurisdiction.value, requirement.category
            )
            return requirement
        except Exception as e:
            logger.error("Failed to add custom requirement: %s", str(e))
            raise

    def get_jurisdiction_config(self, jurisdiction: Jurisdiction) -> JurisdictionConfig:
        """
        Get configuration for a jurisdiction.

        Args:
            jurisdiction: Jurisdiction to get config for

        Returns:
            JurisdictionConfig object

        Raises:
            ValueError: If jurisdiction not supported
        """
        try:
            if jurisdiction not in self._jurisdiction_configs:
                raise ValueError(f"Jurisdiction {jurisdiction.value} not supported")

            config = self._jurisdiction_configs[jurisdiction]
            logger.info("Jurisdiction config retrieved: %s", jurisdiction.value)
            return config
        except Exception as e:
            logger.error("Failed to get jurisdiction config: %s", str(e))
            raise

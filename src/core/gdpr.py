"""
COMP-001: GDPR Data Privacy Compliance Module.

Provides GDPR compliance functionality including consent management,
Data Subject Access Requests (DSAR), data retention policies, and audit trails.
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

class DataCategory(str, Enum):
    """Classification of personal data types."""
    PERSONAL = "personal"
    SENSITIVE = "sensitive"
    FINANCIAL = "financial"
    HEALTH = "health"
    BIOMETRIC = "biometric"


class ConsentPurpose(str, Enum):
    """Purposes for which consent is requested."""
    HR_PROCESSING = "hr_processing"
    BENEFITS_ADMIN = "benefits_admin"
    PERFORMANCE_REVIEW = "performance_review"
    ANALYTICS = "analytics"
    MARKETING = "marketing"


class DSARType(str, Enum):
    """Types of Data Subject Access Requests."""
    ACCESS = "access"
    ERASURE = "erasure"
    RECTIFICATION = "rectification"
    PORTABILITY = "portability"


class DSARStatus(str, Enum):
    """Status of a DSAR."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"


class RetentionAction(str, Enum):
    """Action to take on expired retention period."""
    ARCHIVE = "archive"
    DELETE = "delete"


# ============================================================================
# Pydantic Models
# ============================================================================

class ConsentRecord(BaseModel):
    """Record of employee consent for data processing."""
    consent_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique consent ID")
    employee_id: str = Field(..., description="Employee ID")
    purpose: ConsentPurpose = Field(..., description="Purpose of processing")
    granted: bool = Field(..., description="Whether consent was granted")
    granted_at: datetime = Field(..., description="When consent was granted/revoked")
    revoked_at: Optional[datetime] = Field(None, description="When consent was revoked")

    model_config = ConfigDict(use_enum_values=False)


class DSARRequest(BaseModel):
    """Data Subject Access Request."""
    request_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique request ID")
    employee_id: str = Field(..., description="Employee ID")
    type: DSARType = Field(..., description="Type of DSAR")
    status: DSARStatus = Field(default=DSARStatus.PENDING, description="Request status")
    submitted_at: datetime = Field(default_factory=datetime.utcnow, description="Submission timestamp")
    due_date: datetime = Field(..., description="Legal deadline (30 days from submission)")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    data_export_path: Optional[str] = Field(None, description="Path to exported data file")

    model_config = ConfigDict(use_enum_values=False)


class RetentionPolicy(BaseModel):
    """Data retention policy."""
    policy_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique policy ID")
    data_category: DataCategory = Field(..., description="Data category this policy applies to")
    retention_days: int = Field(..., description="Days to retain data")
    action: RetentionAction = Field(..., description="Action when retention period expires")

    model_config = ConfigDict(use_enum_values=False)


# ============================================================================
# GDPR Compliance Service
# ============================================================================

class GDPRComplianceService:
    """
    GDPR compliance service for managing data privacy and subject rights.

    Handles consent management, data subject access requests, data retention,
    and audit trail logging for GDPR compliance.
    """

    def __init__(self):
        """Initialize GDPR compliance service."""
        # In-memory storage
        self._consents: Dict[str, List[ConsentRecord]] = {}
        self._dsars: Dict[str, DSARRequest] = {}
        self._retention_policies: Dict[str, RetentionPolicy] = {}
        self._audit_trail: List[Dict[str, Any]] = []

        # Data classification map: "table.field" -> DataCategory
        self._data_classification = self._init_data_classification()

        logger.info("GDPRComplianceService initialized")

    def _init_data_classification(self) -> Dict[str, DataCategory]:
        """
        Initialize default data field classification mapping.

        Returns:
            Dictionary mapping table.field strings to DataCategory
        """
        return {
            # Employee personal data
            "employees.first_name": DataCategory.PERSONAL,
            "employees.last_name": DataCategory.PERSONAL,
            "employees.email": DataCategory.PERSONAL,
            "employees.phone": DataCategory.PERSONAL,
            "employees.hire_date": DataCategory.PERSONAL,
            "employees.location": DataCategory.PERSONAL,

            # Sensitive employee data
            "employees.ssn": DataCategory.SENSITIVE,
            "employees.government_id": DataCategory.SENSITIVE,
            "employees.birth_date": DataCategory.SENSITIVE,
            "employees.marital_status": DataCategory.SENSITIVE,
            "employees.emergency_contact": DataCategory.SENSITIVE,

            # Financial data
            "compensation.salary": DataCategory.FINANCIAL,
            "compensation.bonus": DataCategory.FINANCIAL,
            "compensation.bank_account": DataCategory.FINANCIAL,
            "compensation.tax_id": DataCategory.FINANCIAL,

            # Health data
            "benefits.health_plan": DataCategory.HEALTH,
            "benefits.medical_history": DataCategory.HEALTH,
            "benefits.disabilities": DataCategory.HEALTH,

            # Biometric data
            "employees.fingerprint": DataCategory.BIOMETRIC,
            "employees.facial_recognition": DataCategory.BIOMETRIC,
        }

    def _log_audit_trail(
        self,
        action: str,
        employee_id: str,
        details: Optional[Dict[str, Any]] = None,
        legal_basis: Optional[str] = None
    ) -> None:
        """
        Log an action to audit trail for compliance tracking.

        Args:
            action: Type of action performed
            employee_id: Employee ID involved
            details: Additional details about the action
            legal_basis: Legal basis for the action
        """
        entry = {
            "timestamp": datetime.utcnow(),
            "action": action,
            "employee_id": employee_id,
            "details": details or {},
            "legal_basis": legal_basis,
        }
        self._audit_trail.append(entry)
        logger.info(f"Audit trail: {action} for employee {employee_id} (basis: {legal_basis})")

    def record_consent(
        self,
        employee_id: str,
        purpose: ConsentPurpose,
        granted: bool
    ) -> ConsentRecord:
        """
        Record employee consent for data processing.

        Args:
            employee_id: Employee ID
            purpose: Purpose of processing
            granted: Whether consent was granted

        Returns:
            ConsentRecord object
        """
        record = ConsentRecord(
            employee_id=employee_id,
            purpose=purpose,
            granted=granted,
            granted_at=datetime.utcnow(),
        )

        if employee_id not in self._consents:
            self._consents[employee_id] = []

        self._consents[employee_id].append(record)

        self._log_audit_trail(
            action="consent_recorded",
            employee_id=employee_id,
            details={"purpose": purpose.value, "granted": granted},
            legal_basis="Consent Management"
        )

        logger.info(f"Consent recorded for {employee_id}: {purpose.value} = {granted}")
        return record

    def revoke_consent(
        self,
        employee_id: str,
        purpose: ConsentPurpose
    ) -> ConsentRecord:
        """
        Revoke employee consent for a specific purpose.

        Args:
            employee_id: Employee ID
            purpose: Purpose to revoke consent for

        Returns:
            Updated ConsentRecord

        Raises:
            ValueError: If no active consent found
        """
        if employee_id not in self._consents:
            raise ValueError(f"No consent records for employee {employee_id}")

        # Find active consent for this purpose
        for record in reversed(self._consents[employee_id]):
            if record.purpose == purpose and record.revoked_at is None:
                record.revoked_at = datetime.utcnow()

                self._log_audit_trail(
                    action="consent_revoked",
                    employee_id=employee_id,
                    details={"purpose": purpose.value},
                    legal_basis="Consent Withdrawal"
                )

                logger.info(f"Consent revoked for {employee_id}: {purpose.value}")
                return record

        raise ValueError(f"No active consent found for {employee_id} with purpose {purpose.value}")

    def check_consent(self, employee_id: str, purpose: ConsentPurpose) -> bool:
        """
        Check if employee has active consent for a purpose.

        Args:
            employee_id: Employee ID
            purpose: Purpose to check consent for

        Returns:
            True if active consent exists, False otherwise
        """
        if employee_id not in self._consents:
            return False

        for record in reversed(self._consents[employee_id]):
            if record.purpose == purpose and record.revoked_at is None:
                return record.granted

        return False

    def get_consent_history(self, employee_id: str) -> List[ConsentRecord]:
        """
        Get complete consent history for an employee.

        Args:
            employee_id: Employee ID

        Returns:
            List of ConsentRecord objects
        """
        self._log_audit_trail(
            action="consent_history_accessed",
            employee_id=employee_id,
            legal_basis="Data Subject Access Right"
        )

        return self._consents.get(employee_id, [])

    def process_dsar(self, request: DSARRequest) -> Dict[str, Any]:
        """
        Process a Data Subject Access Request.

        Args:
            request: DSARRequest object

        Returns:
            Dictionary with status and result information

        Raises:
            ValueError: If request type is invalid
        """
        request.status = DSARStatus.PROCESSING
        self._dsars[request.request_id] = request

        self._log_audit_trail(
            action=f"dsar_{request.type.value}_submitted",
            employee_id=request.employee_id,
            details={"request_id": request.request_id, "due_date": request.due_date.isoformat()},
            legal_basis=f"GDPR Article 15-20 ({request.type.value})"
        )

        logger.info(f"Processing DSAR: {request.request_id} ({request.type.value})")

        result = {
            "request_id": request.request_id,
            "employee_id": request.employee_id,
            "type": request.type.value,
            "status": request.status.value,
            "due_date": request.due_date.isoformat(),
            "submitted_at": request.submitted_at.isoformat(),
        }

        if request.type == DSARType.ACCESS:
            result["data"] = self.data_subject_access(request.employee_id)
        elif request.type == DSARType.ERASURE:
            result["erasure_result"] = self.right_to_erasure(request.employee_id)
        elif request.type == DSARType.RECTIFICATION:
            result["message"] = "Rectification process initiated. Employee should verify data."
        elif request.type == DSARType.PORTABILITY:
            result["data_export"] = self.data_subject_access(request.employee_id)
            result["export_format"] = "JSON"

        request.status = DSARStatus.COMPLETED
        request.completed_at = datetime.utcnow()

        self._log_audit_trail(
            action=f"dsar_{request.type.value}_completed",
            employee_id=request.employee_id,
            details={"request_id": request.request_id},
            legal_basis=f"GDPR Article 15-20 ({request.type.value})"
        )

        return result

    def data_subject_access(self, employee_id: str) -> Dict[str, Any]:
        """
        Compile all personal data collected about an employee.

        Args:
            employee_id: Employee ID

        Returns:
            Dictionary with all personal data
        """
        self._log_audit_trail(
            action="data_subject_access",
            employee_id=employee_id,
            legal_basis="GDPR Article 15 (Right of Access)"
        )

        # In a real system, this would query a database
        # For now, return structured placeholder data
        return {
            "employee_id": employee_id,
            "personal_data": {
                "name": "John Doe",
                "email": "john.doe@company.com",
                "phone": "+1-555-0123",
                "hire_date": "2020-01-15",
                "department": "Engineering",
            },
            "employment_records": {
                "job_title": "Software Engineer",
                "salary_level": "Senior",
                "performance_reviews": "3 reviews on file",
                "leave_history": "15 days PTO used in 2024",
            },
            "benefits_data": {
                "health_plan": "Premium PPO",
                "dental_plan": "Standard",
                "vision_plan": "Standard",
                "401k_enrollment": "Enrolled, 5% contribution",
            },
            "data_sources": [
                "HRIS System",
                "Payroll System",
                "Benefits Administration",
                "Performance Management System",
            ],
            "legal_basis": "Consent, Employment Contract, Legal Obligation",
            "retention_schedule": "See retention policy document",
        }

    def right_to_erasure(self, employee_id: str) -> Dict[str, Any]:
        """
        Execute right to erasure (right to be forgotten).

        Args:
            employee_id: Employee ID

        Returns:
            Dictionary with anonymization results
        """
        self._log_audit_trail(
            action="right_to_erasure_exercised",
            employee_id=employee_id,
            legal_basis="GDPR Article 17 (Right to Erasure)"
        )

        # Simulate anonymization of personal data
        result = {
            "employee_id": employee_id,
            "action": "anonymized",
            "timestamp": datetime.utcnow().isoformat(),
            "anonymized_fields": [
                "first_name",
                "last_name",
                "email",
                "phone",
                "ssn",
                "government_id",
                "birth_date",
            ],
            "retained_fields": [
                "employment_dates",  # Legal requirement for tax/benefits
                "salary_records",    # Legal requirement for audits
                "performance_ratings", # Legitimate business interest
            ],
            "excluded_from_deletion": [
                "Historical payroll records (7 years)",
                "Tax compliance records (10 years)",
                "Contractual records (statute of limitations)",
            ],
        }

        logger.info(f"Right to erasure executed for {employee_id}")
        return result

    def classify_data_field(self, table_name: str, field_name: str) -> DataCategory:
        """
        Classify a data field by table and field name.

        Args:
            table_name: Database table name
            field_name: Field name in the table

        Returns:
            DataCategory classification

        Raises:
            ValueError: If field classification is unknown
        """
        key = f"{table_name}.{field_name}"

        if key in self._data_classification:
            return self._data_classification[key]

        # Default classification based on field name patterns
        if any(term in field_name.lower() for term in ["ssn", "tax_id", "id_number"]):
            return DataCategory.SENSITIVE
        elif any(term in field_name.lower() for term in ["salary", "bonus", "bank", "credit"]):
            return DataCategory.FINANCIAL
        elif any(term in field_name.lower() for term in ["health", "medical", "disability"]):
            return DataCategory.HEALTH
        elif any(term in field_name.lower() for term in ["fingerprint", "facial", "biometric"]):
            return DataCategory.BIOMETRIC
        else:
            return DataCategory.PERSONAL

    def enforce_retention_policies(self) -> Dict[str, Any]:
        """
        Enforce data retention policies by archiving/deleting expired data.

        Returns:
            Dictionary with action counts
        """
        result = {
            "archived_count": 0,
            "deleted_count": 0,
            "policies_enforced": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        for policy_id, policy in self._retention_policies.items():
            # Simulate enforcement
            enforcement_result = {
                "policy_id": policy_id,
                "data_category": policy.data_category.value,
                "retention_days": policy.retention_days,
                "action": policy.action.value,
                "affected_records": 0,  # Would be actual count in real system
            }

            if policy.action == RetentionAction.ARCHIVE:
                result["archived_count"] += 1
            else:
                result["deleted_count"] += 1

            result["policies_enforced"].append(enforcement_result)

            self._log_audit_trail(
                action=f"retention_policy_enforced",
                employee_id="SYSTEM",
                details={"policy_id": policy_id, "action": policy.action.value},
                legal_basis="Data Retention Policy"
            )

        logger.info(f"Retention policies enforced: {result['archived_count']} archived, {result['deleted_count']} deleted")
        return result

    def add_retention_policy(
        self,
        data_category: DataCategory,
        retention_days: int,
        action: RetentionAction
    ) -> RetentionPolicy:
        """
        Add a data retention policy.

        Args:
            data_category: Category of data to apply policy to
            retention_days: Number of days to retain
            action: Action to take when retention expires

        Returns:
            RetentionPolicy object
        """
        policy = RetentionPolicy(
            data_category=data_category,
            retention_days=retention_days,
            action=action,
        )

        self._retention_policies[policy.policy_id] = policy

        logger.info(
            f"Retention policy added: {data_category.value} -> "
            f"{retention_days} days -> {action.value}"
        )

        return policy

    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate GDPR compliance report for a date range.

        Args:
            start_date: Report start date
            end_date: Report end date

        Returns:
            Compliance report dictionary
        """
        # Filter audit trail to date range
        period_entries = [
            entry for entry in self._audit_trail
            if start_date <= entry["timestamp"] <= end_date
        ]

        # Count actions by type
        actions_by_type = {}
        for entry in period_entries:
            action = entry["action"]
            actions_by_type[action] = actions_by_type.get(action, 0) + 1

        # Count by legal basis
        actions_by_basis = {}
        for entry in period_entries:
            basis = entry.get("legal_basis", "Unknown")
            actions_by_basis[basis] = actions_by_basis.get(basis, 0) + 1

        report = {
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_audit_entries": len(period_entries),
                "unique_employees": len(set(e["employee_id"] for e in period_entries)),
            },
            "actions_by_type": actions_by_type,
            "actions_by_legal_basis": actions_by_basis,
            "dsar_summary": {
                "total_requests": len(self._dsars),
                "completed": sum(1 for r in self._dsars.values() if r.status == DSARStatus.COMPLETED),
                "pending": sum(1 for r in self._dsars.values() if r.status == DSARStatus.PENDING),
                "average_resolution_time_days": self._calculate_avg_dsar_resolution(),
            },
            "consent_summary": {
                "total_consents": len(self._consents),
                "active_purposes": self._count_active_consents(),
            },
            "retention_policies": len(self._retention_policies),
            "generated_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"Compliance report generated for {start_date.date()} to {end_date.date()}")
        return report

    def _calculate_avg_dsar_resolution(self) -> float:
        """
        Calculate average DSAR resolution time in days.

        Returns:
            Average resolution time or 0 if no completed requests
        """
        completed = [r for r in self._dsars.values() if r.completed_at]
        if not completed:
            return 0.0

        total_days = sum(
            (r.completed_at - r.submitted_at).days for r in completed
        )
        return total_days / len(completed)

    def _count_active_consents(self) -> Dict[str, int]:
        """
        Count active consents by purpose.

        Returns:
            Dictionary of purpose -> count
        """
        counts = {}
        for consents in self._consents.values():
            for record in consents:
                if record.revoked_at is None and record.granted:
                    purpose = record.purpose.value
                    counts[purpose] = counts.get(purpose, 0) + 1

        return counts

    def get_audit_trail(
        self,
        employee_id: Optional[str] = None,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve filtered audit trail entries.

        Args:
            employee_id: Optional filter by employee
            action_type: Optional filter by action type
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Filtered list of audit trail entries
        """
        entries = self._audit_trail

        if employee_id:
            entries = [e for e in entries if e["employee_id"] == employee_id]

        if action_type:
            entries = [e for e in entries if e["action"] == action_type]

        if start_date:
            entries = [e for e in entries if e["timestamp"] >= start_date]

        if end_date:
            entries = [e for e in entries if e["timestamp"] <= end_date]

        return entries

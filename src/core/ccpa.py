"""
COMP-002: CCPA Data Privacy Compliance Module.

Provides California Consumer Privacy Act (CCPA) compliance functionality including
consumer rights management, data inventory, opt-out of sale, and disclosure requirements.
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

class CCPADataCategory(str, Enum):
    """CCPA classification of personal information categories."""
    PERSONAL_INFO = "personal_info"
    FINANCIAL = "financial"
    BIOMETRIC = "biometric"
    GEOLOCATION = "geolocation"
    INTERNET_ACTIVITY = "internet_activity"
    PROFESSIONAL = "professional"
    EDUCATION = "education"
    INFERENCES = "inferences"


class ConsumerRight(str, Enum):
    """Consumer rights under CCPA."""
    RIGHT_TO_KNOW = "right_to_know"
    RIGHT_TO_DELETE = "right_to_delete"
    RIGHT_TO_OPT_OUT = "right_to_opt_out"
    RIGHT_TO_NON_DISCRIMINATION = "right_to_non_discrimination"
    RIGHT_TO_CORRECT = "right_to_correct"
    RIGHT_TO_LIMIT = "right_to_limit"


class CCPARequestStatus(str, Enum):
    """Status of a CCPA consumer request."""
    PENDING = "pending"
    VERIFICATION_REQUIRED = "verification_required"
    PROCESSING = "processing"
    COMPLETED = "completed"
    DENIED = "denied"


# ============================================================================
# Pydantic Models
# ============================================================================

class CCPARequest(BaseModel):
    """CCPA consumer rights request."""
    request_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique request ID")
    consumer_id: str = Field(..., description="Consumer ID")
    right_type: ConsumerRight = Field(..., description="Type of consumer right")
    data_categories: List[CCPADataCategory] = Field(
        default_factory=list,
        description="Specific data categories requested"
    )
    status: CCPARequestStatus = Field(
        default=CCPARequestStatus.PENDING,
        description="Request status"
    )
    submitted_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Submission timestamp"
    )
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    response_deadline: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=45),
        description="Legal response deadline (45 days)"
    )
    extended: bool = Field(default=False, description="Whether deadline was extended")
    extension_reason: Optional[str] = Field(None, description="Reason for extension")

    model_config = ConfigDict(use_enum_values=False)


class DataInventoryItem(BaseModel):
    """Inventory of personal information collected."""
    item_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique item ID")
    category: CCPADataCategory = Field(..., description="Data category")
    source: str = Field(..., description="Source of data collection")
    purpose: str = Field(..., description="Business purpose for collection")
    shared_with_third_parties: bool = Field(
        default=False,
        description="Whether shared with third parties"
    )
    sale_opt_out: bool = Field(
        default=False,
        description="Whether consumer opted out of sale"
    )

    model_config = ConfigDict(use_enum_values=False)


class CCPAConfig(BaseModel):
    """CCPA compliance configuration."""
    enabled: bool = Field(default=True, description="Whether CCPA compliance is enabled")
    verification_required: bool = Field(
        default=True,
        description="Whether consumer verification required"
    )
    response_deadline_days: int = Field(
        default=45,
        description="Days to respond to requests"
    )
    extension_allowed_days: int = Field(
        default=45,
        description="Days allowed for extension"
    )
    min_age_for_consent: int = Field(
        default=16,
        description="Minimum age for independent consent (13+ for minors)"
    )
    data_broker_registration: bool = Field(
        default=True,
        description="Whether data broker registration is required"
    )
    annual_report_enabled: bool = Field(
        default=True,
        description="Whether annual report generation is enabled"
    )

    model_config = ConfigDict(use_enum_values=False)


# ============================================================================
# CCPA Compliance Service
# ============================================================================

class CCPAComplianceService:
    """
    CCPA compliance service for managing consumer privacy rights.

    Handles consumer requests for access, deletion, opt-out, data inventory management,
    and compliance reporting for California Consumer Privacy Act requirements.
    """

    def __init__(self, config: Optional[CCPAConfig] = None, audit_logger: Optional[Any] = None):
        """
        Initialize CCPA compliance service.

        Args:
            config: CCPAConfig object with compliance settings
            audit_logger: Logger for audit trail (optional)
        """
        self.config = config or CCPAConfig()
        self.audit_logger = audit_logger

        # In-memory storage
        self._requests: Dict[str, CCPARequest] = {}
        self._inventory: Dict[str, List[DataInventoryItem]] = {}
        self._verified_consumers: Dict[str, bool] = {}
        self._opt_out_list: Dict[str, bool] = {}
        self._audit_trail: List[Dict[str, Any]] = []
        self._correction_records: Dict[str, List[Dict[str, Any]]] = {}

        logger.info("CCPAComplianceService initialized with config: %s", self.config.enabled)

    def _log_audit_trail(
        self,
        action: str,
        consumer_id: str,
        details: Optional[Dict[str, Any]] = None,
        legal_basis: Optional[str] = None
    ) -> None:
        """
        Log an action to audit trail for compliance tracking.

        Args:
            action: Type of action performed
            consumer_id: Consumer ID involved
            details: Additional details about the action
            legal_basis: Legal basis for the action
        """
        try:
            entry = {
                "timestamp": datetime.utcnow(),
                "action": action,
                "consumer_id": consumer_id,
                "details": details or {},
                "legal_basis": legal_basis,
            }
            self._audit_trail.append(entry)
            logger.info(
                "CCPA audit: %s for consumer %s (basis: %s)",
                action,
                consumer_id,
                legal_basis
            )
        except Exception as e:
            logger.error("Failed to log audit trail: %s", str(e))

    def submit_request(
        self,
        consumer_id: str,
        right_type: ConsumerRight,
        data_categories: Optional[List[CCPADataCategory]] = None
    ) -> CCPARequest:
        """
        Submit a CCPA consumer request.

        Args:
            consumer_id: Consumer ID
            right_type: Type of consumer right being exercised
            data_categories: Specific data categories (optional)

        Returns:
            CCPARequest object

        Raises:
            ValueError: If consumer ID is invalid
        """
        try:
            if not consumer_id or not isinstance(consumer_id, str):
                raise ValueError("Invalid consumer_id provided")

            request = CCPARequest(
                consumer_id=consumer_id,
                right_type=right_type,
                data_categories=data_categories or [],
                response_deadline=datetime.utcnow() + timedelta(
                    days=self.config.response_deadline_days
                )
            )

            self._requests[request.request_id] = request

            self._log_audit_trail(
                action="ccpa_request_submitted",
                consumer_id=consumer_id,
                details={
                    "request_id": request.request_id,
                    "right_type": right_type.value,
                    "deadline": request.response_deadline.isoformat()
                },
                legal_basis="CCPA Consumer Right"
            )

            logger.info(
                "CCPA request submitted: %s (%s) for consumer %s",
                request.request_id,
                right_type.value,
                consumer_id
            )
            return request
        except Exception as e:
            logger.error("Failed to submit CCPA request: %s", str(e))
            raise

    def process_request(self, request_id: str) -> Dict[str, Any]:
        """
        Process a CCPA consumer request.

        Args:
            request_id: Request ID to process

        Returns:
            Dictionary with status and details

        Raises:
            ValueError: If request not found
        """
        try:
            if request_id not in self._requests:
                raise ValueError(f"Request {request_id} not found")

            request = self._requests[request_id]
            request.status = CCPARequestStatus.PROCESSING

            self._log_audit_trail(
                action="ccpa_request_processing",
                consumer_id=request.consumer_id,
                details={"request_id": request_id},
                legal_basis="CCPA Request Processing"
            )

            result = {
                "request_id": request_id,
                "consumer_id": request.consumer_id,
                "right_type": request.right_type.value,
                "status": request.status.value,
                "deadline": request.response_deadline.isoformat(),
            }

            # Process by right type
            if request.right_type == ConsumerRight.RIGHT_TO_KNOW:
                result["disclosure"] = self.generate_disclosure(request.consumer_id)
            elif request.right_type == ConsumerRight.RIGHT_TO_DELETE:
                result["deletion_result"] = self._process_deletion(request.consumer_id)
            elif request.right_type == ConsumerRight.RIGHT_TO_OPT_OUT:
                result["opt_out_result"] = self.opt_out_of_sale(request.consumer_id)
            elif request.right_type == ConsumerRight.RIGHT_TO_CORRECT:
                result["correction_status"] = "pending_correction_verification"
            elif request.right_type == ConsumerRight.RIGHT_TO_LIMIT:
                result["limit_status"] = "use_limited_to_purpose"
            elif request.right_type == ConsumerRight.RIGHT_TO_NON_DISCRIMINATION:
                result["discrimination_status"] = "no_discrimination_enforced"

            request.status = CCPARequestStatus.COMPLETED
            request.completed_at = datetime.utcnow()

            self._log_audit_trail(
                action="ccpa_request_completed",
                consumer_id=request.consumer_id,
                details={"request_id": request_id},
                legal_basis="CCPA Request Completion"
            )

            return result
        except Exception as e:
            logger.error("Failed to process request: %s", str(e))
            raise

    def verify_consumer(
        self,
        consumer_id: str,
        verification_data: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Verify consumer identity for request processing.

        Args:
            consumer_id: Consumer ID to verify
            verification_data: Verification information (name, email, etc.)

        Returns:
            True if verification successful

        Raises:
            ValueError: If verification fails
        """
        try:
            if not self.config.verification_required:
                self._verified_consumers[consumer_id] = True
                self._log_audit_trail(
                    action="consumer_verification_skipped",
                    consumer_id=consumer_id,
                    legal_basis="Verification Not Required"
                )
                return True

            # In production, would validate against identity verification service
            if verification_data and "email" in verification_data:
                self._verified_consumers[consumer_id] = True

                self._log_audit_trail(
                    action="consumer_verified",
                    consumer_id=consumer_id,
                    details={"verification_method": "email"},
                    legal_basis="Consumer Verification"
                )

                logger.info("Consumer verified: %s", consumer_id)
                return True

            raise ValueError("Verification data incomplete")
        except Exception as e:
            logger.error("Consumer verification failed: %s", str(e))
            raise

    def opt_out_of_sale(self, consumer_id: str) -> Dict[str, Any]:
        """
        Process consumer opt-out of sale of personal information.

        Args:
            consumer_id: Consumer ID opting out

        Returns:
            Dictionary with opt-out confirmation

        Raises:
            ValueError: If consumer ID invalid
        """
        try:
            if not consumer_id:
                raise ValueError("Invalid consumer_id")

            self._opt_out_list[consumer_id] = True

            # Update inventory to reflect opt-out
            if consumer_id in self._inventory:
                for item in self._inventory[consumer_id]:
                    item.sale_opt_out = True

            result = {
                "consumer_id": consumer_id,
                "opt_out_status": "confirmed",
                "effective_date": datetime.utcnow().isoformat(),
                "message": "Consumer has opted out of sale of personal information"
            }

            self._log_audit_trail(
                action="opt_out_of_sale",
                consumer_id=consumer_id,
                details={"status": "confirmed"},
                legal_basis="CCPA Right to Opt-Out of Sale"
            )

            logger.info("Consumer opted out of sale: %s", consumer_id)
            return result
        except Exception as e:
            logger.error("Failed to process opt-out: %s", str(e))
            raise

    def get_data_inventory(self, consumer_id: str) -> List[DataInventoryItem]:
        """
        Get data inventory for a consumer.

        Args:
            consumer_id: Consumer ID

        Returns:
            List of DataInventoryItem objects

        Raises:
            ValueError: If consumer not found
        """
        try:
            self._log_audit_trail(
                action="data_inventory_accessed",
                consumer_id=consumer_id,
                legal_basis="Consumer Access Right"
            )

            if consumer_id not in self._inventory:
                self._inventory[consumer_id] = self._init_data_inventory(consumer_id)

            logger.info("Data inventory retrieved for consumer: %s", consumer_id)
            return self._inventory[consumer_id]
        except Exception as e:
            logger.error("Failed to get data inventory: %s", str(e))
            raise

    def _init_data_inventory(self, consumer_id: str) -> List[DataInventoryItem]:
        """
        Initialize default data inventory for a consumer.

        Args:
            consumer_id: Consumer ID

        Returns:
            List of DataInventoryItem objects
        """
        return [
            DataInventoryItem(
                category=CCPADataCategory.PERSONAL_INFO,
                source="HRIS System",
                purpose="Employment Administration"
            ),
            DataInventoryItem(
                category=CCPADataCategory.FINANCIAL,
                source="Payroll System",
                purpose="Compensation Management"
            ),
            DataInventoryItem(
                category=CCPADataCategory.INTERNET_ACTIVITY,
                source="Network Activity Logs",
                purpose="Security and Compliance"
            ),
            DataInventoryItem(
                category=CCPADataCategory.PROFESSIONAL,
                source="HRIS System",
                purpose="Performance Management"
            ),
        ]

    def classify_data(self, data: Dict[str, Any]) -> List[CCPADataCategory]:
        """
        Classify data fields into CCPA categories.

        Args:
            data: Dictionary of data to classify

        Returns:
            List of CCPADataCategory classifications

        Raises:
            ValueError: If data is invalid
        """
        try:
            if not isinstance(data, dict):
                raise ValueError("Data must be a dictionary")

            categories = set()

            for field_name in data.keys():
                category = self._classify_field(field_name)
                categories.add(category)

            logger.info("Data classified into %d categories", len(categories))
            return list(categories)
        except Exception as e:
            logger.error("Failed to classify data: %s", str(e))
            raise

    def _classify_field(self, field_name: str) -> CCPADataCategory:
        """
        Classify a single data field.

        Args:
            field_name: Name of the field

        Returns:
            CCPADataCategory classification
        """
        field_lower = field_name.lower()

        # Financial data
        if any(term in field_lower for term in ["salary", "bonus", "bank", "credit", "payment"]):
            return CCPADataCategory.FINANCIAL

        # Biometric data
        if any(term in field_lower for term in ["fingerprint", "facial", "biometric", "iris"]):
            return CCPADataCategory.BIOMETRIC

        # Geolocation data
        if any(term in field_lower for term in ["location", "gps", "latitude", "longitude"]):
            return CCPADataCategory.GEOLOCATION

        # Internet activity
        if any(term in field_lower for term in ["browser", "ip_address", "cookie", "session"]):
            return CCPADataCategory.INTERNET_ACTIVITY

        # Professional data
        if any(term in field_lower for term in ["job_title", "department", "manager", "skills"]):
            return CCPADataCategory.PROFESSIONAL

        # Education data
        if any(term in field_lower for term in ["degree", "university", "certification"]):
            return CCPADataCategory.EDUCATION

        # Inferences
        if any(term in field_lower for term in ["profile", "score", "preference", "predicted"]):
            return CCPADataCategory.INFERENCES

        return CCPADataCategory.PERSONAL_INFO

    def check_minor_consent(self, consumer_id: str, age: int) -> Dict[str, Any]:
        """
        Check consent requirements for minors under CCPA.

        Args:
            consumer_id: Consumer ID
            age: Consumer age

        Returns:
            Dictionary with consent requirements

        Raises:
            ValueError: If age invalid
        """
        try:
            if not isinstance(age, int) or age < 0:
                raise ValueError("Age must be a positive integer")

            result = {
                "consumer_id": consumer_id,
                "age": age,
                "minor_status": "under_16" if age < 16 else "over_13",
            }

            if age < 13:
                result["parental_consent_required"] = True
                result["consent_type"] = "verifiable_parental_consent"
            elif age < 16:
                result["parental_consent_required"] = True
                result["consent_type"] = "parental_consent"
            else:
                result["parental_consent_required"] = False
                result["consent_type"] = "consumer_consent"

            self._log_audit_trail(
                action="minor_consent_check",
                consumer_id=consumer_id,
                details={"age": age, "minor_status": result["minor_status"]},
                legal_basis="CCPA Minor Consent Requirement"
            )

            logger.info("Minor consent check for consumer %s (age %d)", consumer_id, age)
            return result
        except Exception as e:
            logger.error("Failed to check minor consent: %s", str(e))
            raise

    def generate_disclosure(self, consumer_id: str) -> Dict[str, Any]:
        """
        Generate 12-month disclosure report of personal information.

        Args:
            consumer_id: Consumer ID

        Returns:
            Dictionary with disclosure information

        Raises:
            ValueError: If consumer not found
        """
        try:
            self._log_audit_trail(
                action="disclosure_generated",
                consumer_id=consumer_id,
                legal_basis="CCPA Right to Know"
            )

            inventory = self.get_data_inventory(consumer_id)

            # Categorize inventory
            categories_collected = {}
            sources = set()
            purposes = set()

            for item in inventory:
                cat = item.category.value
                if cat not in categories_collected:
                    categories_collected[cat] = 0
                categories_collected[cat] += 1
                sources.add(item.source)
                purposes.add(item.purpose)

            disclosure = {
                "consumer_id": consumer_id,
                "lookback_period": "12 months",
                "categories_collected": categories_collected,
                "data_sources": list(sources),
                "business_purposes": list(purposes),
                "third_party_sharing": self._get_third_party_list(consumer_id),
                "sale_status": consumer_id in self._opt_out_list,
                "generated_at": datetime.utcnow().isoformat(),
            }

            logger.info("Disclosure generated for consumer: %s", consumer_id)
            return disclosure
        except Exception as e:
            logger.error("Failed to generate disclosure: %s", str(e))
            raise

    def _get_third_party_list(self, consumer_id: str) -> List[str]:
        """
        Get list of third parties with whom data is shared.

        Args:
            consumer_id: Consumer ID

        Returns:
            List of third party names
        """
        try:
            if consumer_id not in self._inventory:
                return []

            third_parties = []
            for item in self._inventory[consumer_id]:
                if item.shared_with_third_parties and item.source not in third_parties:
                    third_parties.append(item.source)

            return third_parties
        except Exception as e:
            logger.error("Failed to get third party list: %s", str(e))
            return []

    def extend_deadline(self, request_id: str, reason: str) -> CCPARequest:
        """
        Extend response deadline for complex request.

        Args:
            request_id: Request ID to extend
            reason: Reason for extension

        Returns:
            Updated CCPARequest object

        Raises:
            ValueError: If request not found or extension not allowed
        """
        try:
            if request_id not in self._requests:
                raise ValueError(f"Request {request_id} not found")

            request = self._requests[request_id]

            if request.extended:
                raise ValueError("Deadline already extended once")

            if not self.config.extension_allowed_days:
                raise ValueError("Extensions not allowed in configuration")

            request.extended = True
            request.extension_reason = reason
            request.response_deadline = request.response_deadline + timedelta(
                days=self.config.extension_allowed_days
            )

            self._log_audit_trail(
                action="deadline_extended",
                consumer_id=request.consumer_id,
                details={
                    "request_id": request_id,
                    "reason": reason,
                    "new_deadline": request.response_deadline.isoformat()
                },
                legal_basis="CCPA Extension"
            )

            logger.info("Deadline extended for request: %s", request_id)
            return request
        except Exception as e:
            logger.error("Failed to extend deadline: %s", str(e))
            raise

    def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """
        Get current status of a CCPA request.

        Args:
            request_id: Request ID

        Returns:
            Dictionary with request status

        Raises:
            ValueError: If request not found
        """
        try:
            if request_id not in self._requests:
                raise ValueError(f"Request {request_id} not found")

            request = self._requests[request_id]

            status = {
                "request_id": request_id,
                "consumer_id": request.consumer_id,
                "right_type": request.right_type.value,
                "status": request.status.value,
                "submitted_at": request.submitted_at.isoformat(),
                "deadline": request.response_deadline.isoformat(),
                "extended": request.extended,
                "completed_at": request.completed_at.isoformat() if request.completed_at else None,
            }

            days_remaining = (request.response_deadline - datetime.utcnow()).days
            status["days_remaining"] = max(0, days_remaining)

            logger.info("Request status retrieved: %s", request_id)
            return status
        except Exception as e:
            logger.error("Failed to get request status: %s", str(e))
            raise

    def get_annual_metrics(self) -> Dict[str, Any]:
        """
        Generate annual CCPA compliance metrics.

        Returns:
            Dictionary with annual compliance metrics
        """
        try:
            year_ago = datetime.utcnow() - timedelta(days=365)
            recent_requests = [
                r for r in self._requests.values()
                if r.submitted_at >= year_ago
            ]

            # Count by right type
            by_right = {}
            for request in recent_requests:
                right = request.right_type.value
                by_right[right] = by_right.get(right, 0) + 1

            # Count by status
            by_status = {}
            for request in recent_requests:
                status = request.status.value
                by_status[status] = by_status.get(status, 0) + 1

            # Calculate response times
            completed = [
                r for r in recent_requests
                if r.completed_at
            ]
            avg_response_days = 0
            if completed:
                total_days = sum(
                    (r.completed_at - r.submitted_at).days for r in completed
                )
                avg_response_days = total_days / len(completed)

            metrics = {
                "period": "12 months",
                "total_requests": len(recent_requests),
                "by_right_type": by_right,
                "by_status": by_status,
                "average_response_days": round(avg_response_days, 1),
                "opt_outs_processed": len(self._opt_out_list),
                "consumers_verified": len(self._verified_consumers),
                "generated_at": datetime.utcnow().isoformat(),
            }

            self._log_audit_trail(
                action="annual_metrics_generated",
                consumer_id="SYSTEM",
                details=metrics,
                legal_basis="CCPA Annual Report"
            )

            logger.info("Annual metrics generated")
            return metrics
        except Exception as e:
            logger.error("Failed to generate annual metrics: %s", str(e))
            raise

    def _process_deletion(self, consumer_id: str) -> Dict[str, Any]:
        """
        Process data deletion request.

        Args:
            consumer_id: Consumer ID

        Returns:
            Dictionary with deletion results
        """
        try:
            # Simulate deletion process
            result = {
                "consumer_id": consumer_id,
                "action": "deletion_queued",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "scheduled_for_deletion",
                "retention_exceptions": [
                    "Legal compliance records",
                    "Tax records (7 years)",
                    "Contractual records",
                ]
            }

            self._log_audit_trail(
                action="data_deletion_initiated",
                consumer_id=consumer_id,
                legal_basis="CCPA Right to Delete"
            )

            return result
        except Exception as e:
            logger.error("Failed to process deletion: %s", str(e))
            raise

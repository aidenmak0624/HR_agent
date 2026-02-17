"""GDPR compliance repository for consent and data privacy."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin
from src.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ConsentRecordModel(Base, TimestampMixin):
    """
    SQLAlchemy model for GDPR consent records.

    Tracks employee consent for data processing purposes with legal basis.

    Attributes:
        id: Primary key
        employee_id: Employee ID who provided consent
        purpose: Purpose of data processing
        granted: Whether consent was granted
        legal_basis: Legal basis for processing
        granted_at: When consent was given
        revoked_at: When consent was revoked (if any)
    """

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)
    granted: Mapped[bool] = mapped_column(nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(255), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ConsentRecordModel(id={self.id}, employee_id={self.employee_id}, purpose={self.purpose})>"


class DSARRequestModel(Base, TimestampMixin):
    """
    SQLAlchemy model for Data Subject Access Requests.

    Tracks GDPR Data Subject Access Requests with legal deadlines.

    Attributes:
        id: Primary key
        employee_id: Employee ID submitting request
        request_type: Type of DSAR (access/erasure/rectification/portability)
        status: Request status (pending/processing/completed/rejected)
        requested_at: When request was submitted
        deadline: Legal deadline (30 days from submission)
        completed_at: When request was completed
        result_json: Result data as JSON
    """

    __tablename__ = "dsar_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    def __repr__(self) -> str:
        return f"<DSARRequestModel(id={self.id}, type={self.request_type}, status={self.status})>"


class RetentionPolicyModel(Base, TimestampMixin):
    """
    SQLAlchemy model for data retention policies.

    Defines retention periods and actions for different data categories.

    Attributes:
        id: Primary key
        data_category: Category of data (personal/sensitive/financial/health/biometric)
        retention_days: Number of days to retain data
        action: Action when retention expires (archive/delete)
        description: Human-readable description
    """

    __tablename__ = "retention_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_category: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    retention_days: Mapped[int] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    def __repr__(self) -> str:
        return f"<RetentionPolicyModel(id={self.id}, category={self.data_category})>"


class GDPRRepository(BaseRepository[ConsentRecordModel]):
    """
    Repository for GDPR compliance data management.

    Handles consent records, data subject access requests, and retention policies
    with full audit trail support for compliance reporting.
    """

    def __init__(self) -> None:
        """Initialize GDPR repository."""
        super().__init__(ConsentRecordModel)

    def record_consent(
        self,
        employee_id: int,
        purpose: str,
        granted: bool,
        legal_basis: str,
    ) -> Optional[ConsentRecordModel]:
        """
        Record employee consent for data processing.

        Args:
            employee_id: Employee ID
            purpose: Purpose of processing
            granted: Whether consent granted
            legal_basis: Legal basis for processing

        Returns:
            Created ConsentRecordModel or None on error
        """
        try:
            data = {
                "employee_id": employee_id,
                "purpose": purpose,
                "granted": granted,
                "legal_basis": legal_basis,
                "granted_at": datetime.utcnow(),
            }
            consent = self.create(data)
            if consent:
                logger.info(f"Recorded consent: employee={employee_id}, purpose={purpose}")
            return consent
        except Exception as e:
            logger.error(f"Error recording consent: {str(e)}")
            return None

    def get_active_consents(self, employee_id: int) -> List[ConsentRecordModel]:
        """
        Get active (non-revoked) consents for employee.

        Args:
            employee_id: Employee ID

        Returns:
            List of active ConsentRecordModel instances
        """
        try:
            with self._get_session() as session:
                stmt = select(ConsentRecordModel).where(
                    (ConsentRecordModel.employee_id == employee_id)
                    & (ConsentRecordModel.revoked_at.is_(None))
                )
                return session.execute(stmt).scalars().all()
        except Exception as e:
            logger.error(f"Error getting active consents for {employee_id}: {str(e)}")
            return []

    def revoke_consent(self, consent_id: int) -> Optional[ConsentRecordModel]:
        """
        Revoke consent record.

        Args:
            consent_id: Consent record ID

        Returns:
            Updated ConsentRecordModel or None on error
        """
        try:
            consent = self.update(consent_id, {"revoked_at": datetime.utcnow()})
            if consent:
                logger.info(f"Revoked consent: id={consent_id}")
            return consent
        except Exception as e:
            logger.error(f"Error revoking consent: {str(e)}")
            return None

    def check_consent(self, employee_id: int, purpose: str) -> bool:
        """
        Check if employee has active consent for purpose.

        Args:
            employee_id: Employee ID
            purpose: Purpose to check

        Returns:
            True if active consent exists and granted, False otherwise
        """
        try:
            consents = self.get_active_consents(employee_id)
            for consent in consents:
                if consent.purpose == purpose and consent.granted:
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking consent: {str(e)}")
            return False


class DSARRepository(BaseRepository[DSARRequestModel]):
    """
    Repository for Data Subject Access Request management.

    Handles creation, processing, and tracking of GDPR DSARs with deadline monitoring.
    """

    def __init__(self) -> None:
        """Initialize DSAR repository."""
        super().__init__(DSARRequestModel)

    def create_dsar(
        self,
        employee_id: int,
        request_type: str,
        deadline: datetime,
    ) -> Optional[DSARRequestModel]:
        """
        Create new Data Subject Access Request.

        Args:
            employee_id: Employee ID submitting request
            request_type: Type of request (access/erasure/rectification/portability)
            deadline: Legal deadline for fulfillment

        Returns:
            Created DSARRequestModel or None on error
        """
        try:
            data = {
                "employee_id": employee_id,
                "request_type": request_type,
                "status": "pending",
                "requested_at": datetime.utcnow(),
                "deadline": deadline,
            }
            dsar = self.create(data)
            if dsar:
                logger.info(f"Created DSAR: id={dsar.id}, type={request_type}, deadline={deadline}")
            return dsar
        except Exception as e:
            logger.error(f"Error creating DSAR: {str(e)}")
            return None

    def update_dsar_status(
        self,
        dsar_id: int,
        status: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[DSARRequestModel]:
        """
        Update DSAR status with optional result data.

        Args:
            dsar_id: DSAR request ID
            status: New status
            result: Result data (if completing)

        Returns:
            Updated DSARRequestModel or None on error
        """
        try:
            data = {"status": status}
            if result:
                data["result_json"] = result
            if status == "completed":
                data["completed_at"] = datetime.utcnow()

            dsar = self.update(dsar_id, data)
            if dsar:
                logger.info(f"Updated DSAR {dsar_id} status to {status}")
            return dsar
        except Exception as e:
            logger.error(f"Error updating DSAR status: {str(e)}")
            return None

    def get_pending_dsars(self) -> List[DSARRequestModel]:
        """
        Get all pending DSAR requests.

        Returns:
            List of pending DSARRequestModel instances
        """
        return self.list({"status": "pending"})

    def get_overdue_dsars(self) -> List[DSARRequestModel]:
        """
        Get DSAR requests past their deadline.

        Returns:
            List of overdue DSARRequestModel instances
        """
        try:
            with self._get_session() as session:
                stmt = select(DSARRequestModel).where(
                    (DSARRequestModel.deadline < datetime.utcnow())
                    & (DSARRequestModel.status != "completed")
                )
                return session.execute(stmt).scalars().all()
        except Exception as e:
            logger.error(f"Error getting overdue DSARs: {str(e)}")
            return []

    def get_dsars_for_employee(self, employee_id: int) -> List[DSARRequestModel]:
        """
        Get all DSARs for specific employee.

        Args:
            employee_id: Employee ID

        Returns:
            List of DSARRequestModel instances
        """
        return self.list({"employee_id": employee_id})


class RetentionPolicyRepository(BaseRepository[RetentionPolicyModel]):
    """
    Repository for data retention policy management.

    Manages retention periods and automatic actions for different data categories.
    """

    def __init__(self) -> None:
        """Initialize retention policy repository."""
        super().__init__(RetentionPolicyModel)

    def get_retention_policies(self) -> List[RetentionPolicyModel]:
        """
        Get all retention policies.

        Returns:
            List of all RetentionPolicyModel instances
        """
        return self.list()

    def get_policy_for_category(self, data_category: str) -> Optional[RetentionPolicyModel]:
        """
        Get retention policy for specific data category.

        Args:
            data_category: Data category name

        Returns:
            RetentionPolicyModel or None if not found
        """
        try:
            with self._get_session() as session:
                stmt = select(RetentionPolicyModel).where(
                    RetentionPolicyModel.data_category == data_category
                )
                return session.execute(stmt).scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting policy for {data_category}: {str(e)}")
            return None

    def create_policy(
        self,
        data_category: str,
        retention_days: int,
        action: str,
        description: str,
    ) -> Optional[RetentionPolicyModel]:
        """
        Create new retention policy.

        Args:
            data_category: Category name
            retention_days: Retention period in days
            action: Action to take (archive/delete)
            description: Policy description

        Returns:
            Created RetentionPolicyModel or None on error
        """
        try:
            data = {
                "data_category": data_category,
                "retention_days": retention_days,
                "action": action,
                "description": description,
            }
            policy = self.create(data)
            if policy:
                logger.info(f"Created retention policy for {data_category}")
            return policy
        except Exception as e:
            logger.error(f"Error creating retention policy: {str(e)}")
            return None

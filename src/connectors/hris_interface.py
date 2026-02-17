"""
HRIS-001: Abstract HRIS Connector interface and data models.

This module defines the abstract base class and Pydantic models for HRIS connectors,
providing a unified interface for interacting with different HR information systems.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

# ============================================================================
# Exception Classes
# ============================================================================


class ConnectorError(Exception):
    """Base exception for HRIS connector errors."""

    pass


class ConnectionError(ConnectorError):
    """Raised when unable to establish connection to HRIS system."""

    pass


class AuthenticationError(ConnectorError):
    """Raised when authentication fails."""

    pass


class NotFoundError(ConnectorError):
    """Raised when requested resource is not found."""

    pass


class RateLimitError(ConnectorError):
    """Raised when rate limit is exceeded."""

    pass


# ============================================================================
# Enums
# ============================================================================


class EmployeeStatus(str, Enum):
    """Employee employment status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class LeaveType(str, Enum):
    """Types of leave."""

    PTO = "pto"
    SICK = "sick"
    PERSONAL = "personal"
    UNPAID = "unpaid"
    OTHER = "other"


class LeaveStatus(str, Enum):
    """Status of leave request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"


class PlanType(str, Enum):
    """Types of benefit plans."""

    HEALTH = "health"
    DENTAL = "dental"
    VISION = "vision"
    FOUR_01K = "401k"
    LIFE_INSURANCE = "life_insurance"
    OTHER = "other"


# ============================================================================
# Pydantic Data Models
# ============================================================================


class Employee(BaseModel):
    """Employee information model."""

    id: str = Field(..., description="Internal employee ID")
    hris_id: str = Field(..., description="HRIS system employee ID")
    first_name: str = Field(..., description="Employee first name")
    last_name: str = Field(..., description="Employee last name")
    email: str = Field(..., description="Employee email address")
    department: str = Field(..., description="Department name")
    job_title: str = Field(..., description="Job title")
    manager_id: Optional[str] = Field(None, description="Manager's employee ID")
    hire_date: datetime = Field(..., description="Hire date")
    status: EmployeeStatus = Field(..., description="Employment status")
    location: str = Field(..., description="Office location")
    phone: Optional[str] = Field(None, description="Phone number")

    model_config = ConfigDict(use_enum_values=False)


class LeaveBalance(BaseModel):
    """Leave balance information model."""

    employee_id: str = Field(..., description="Employee ID")
    leave_type: LeaveType = Field(..., description="Type of leave")
    total_days: float = Field(..., description="Total days allocated")
    used_days: float = Field(..., description="Days already used")
    pending_days: float = Field(..., description="Days pending approval")
    available_days: float = Field(..., description="Days available to use")

    model_config = ConfigDict(use_enum_values=False)


class LeaveRequest(BaseModel):
    """Leave request information model."""

    id: Optional[str] = Field(None, description="Request ID")
    employee_id: str = Field(..., description="Employee ID")
    leave_type: LeaveType = Field(..., description="Type of leave")
    start_date: datetime = Field(..., description="Leave start date")
    end_date: datetime = Field(..., description="Leave end date")
    status: LeaveStatus = Field(..., description="Request status")
    reason: Optional[str] = Field(None, description="Reason for leave")
    approver_id: Optional[str] = Field(None, description="Approver's employee ID")
    submitted_at: datetime = Field(..., description="Submission timestamp")

    model_config = ConfigDict(use_enum_values=False)


class OrgNode(BaseModel):
    """Organization hierarchy node."""

    employee_id: str = Field(..., description="Employee ID")
    name: str = Field(..., description="Employee name")
    title: str = Field(..., description="Job title")
    department: str = Field(..., description="Department")
    direct_reports: List["OrgNode"] = Field(default_factory=list, description="Direct reports")


# Update forward references for recursive model
OrgNode.model_rebuild()


class BenefitsPlan(BaseModel):
    """Benefits plan information model."""

    id: str = Field(..., description="Plan ID")
    name: str = Field(..., description="Plan name")
    plan_type: PlanType = Field(..., description="Type of plan")
    coverage_level: str = Field(..., description="Coverage level (e.g., Employee, Family)")
    employee_cost: float = Field(..., description="Employee monthly cost")
    employer_cost: float = Field(..., description="Employer monthly cost")

    model_config = ConfigDict(use_enum_values=False)


# ============================================================================
# Abstract Base Class
# ============================================================================


class HRISConnector(ABC):
    """
    Abstract base class for HRIS connectors.

    This class defines the interface that all HRIS connector implementations
    must follow, ensuring consistent interaction with different HR systems.
    """

    @abstractmethod
    def get_employee(self, employee_id: str) -> Optional[Employee]:
        """
        Retrieve employee information.

        Args:
            employee_id: The employee ID to retrieve

        Returns:
            Employee object or None if not found

        Raises:
            NotFoundError: If employee does not exist
            ConnectionError: If unable to connect to HRIS
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    def search_employees(self, filters: Dict[str, Any]) -> List[Employee]:
        """
        Search for employees using filters.

        Args:
            filters: Dictionary of filter criteria (e.g., {"department": "Sales"})

        Returns:
            List of matching Employee objects

        Raises:
            ConnectionError: If unable to connect to HRIS
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    def get_leave_balance(self, employee_id: str) -> List[LeaveBalance]:
        """
        Get leave balance for an employee.

        Args:
            employee_id: The employee ID

        Returns:
            List of LeaveBalance objects for different leave types

        Raises:
            NotFoundError: If employee does not exist
            ConnectionError: If unable to connect to HRIS
        """
        pass

    @abstractmethod
    def get_leave_requests(
        self, employee_id: str, status: Optional[str] = None
    ) -> List[LeaveRequest]:
        """
        Get leave requests for an employee.

        Args:
            employee_id: The employee ID
            status: Optional status filter (pending/approved/denied/cancelled)

        Returns:
            List of LeaveRequest objects

        Raises:
            NotFoundError: If employee does not exist
            ConnectionError: If unable to connect to HRIS
        """
        pass

    @abstractmethod
    def submit_leave_request(self, request: LeaveRequest) -> LeaveRequest:
        """
        Submit a new leave request.

        Args:
            request: LeaveRequest object with request details

        Returns:
            LeaveRequest object with assigned ID and timestamps

        Raises:
            ConnectionError: If unable to connect to HRIS
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    def get_org_chart(self, department: Optional[str] = None) -> List[OrgNode]:
        """
        Get organization chart/hierarchy.

        Args:
            department: Optional department filter

        Returns:
            List of OrgNode objects representing org hierarchy

        Raises:
            ConnectionError: If unable to connect to HRIS
        """
        pass

    @abstractmethod
    def get_benefits(self, employee_id: str) -> List[BenefitsPlan]:
        """
        Get benefits plans for an employee.

        Args:
            employee_id: The employee ID

        Returns:
            List of BenefitsPlan objects

        Raises:
            NotFoundError: If employee does not exist
            ConnectionError: If unable to connect to HRIS
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if connector can reach HRIS system.

        Returns:
            True if healthy, False otherwise
        """
        pass


# ============================================================================
# Connector Registry
# ============================================================================


class ConnectorRegistry:
    """Registry for managing HRIS connector implementations."""

    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, connector_cls: type) -> None:
        """
        Register a connector class.

        Args:
            name: Name to register connector under
            connector_cls: Connector class (must inherit from HRISConnector)

        Raises:
            ValueError: If connector_cls is not a subclass of HRISConnector
        """
        if not issubclass(connector_cls, HRISConnector):
            raise ValueError(f"{connector_cls} must be a subclass of HRISConnector")
        cls._registry[name] = connector_cls

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """
        Get a registered connector class.

        Args:
            name: Name of the connector to retrieve

        Returns:
            Connector class or None if not found
        """
        return cls._registry.get(name)

    @classmethod
    def list_connectors(cls) -> List[str]:
        """
        List all registered connector names.

        Returns:
            List of registered connector names
        """
        return list(cls._registry.keys())

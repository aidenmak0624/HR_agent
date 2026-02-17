"""Tests for HRIS interface and models."""
import pytest
from datetime import datetime
from src.connectors.hris_interface import (
    Employee,
    LeaveBalance,
    LeaveRequest,
    EmployeeStatus,
    LeaveType,
    LeaveStatus,
    ConnectorRegistry,
    HRISConnector,
    NotFoundError,
)


class TestEmployeeModel:
    """Tests for Employee data model."""

    def test_employee_model_creation(self):
        """Employee model can be created."""
        employee = Employee(
            id="emp-001",
            hris_id="hr-system-001",
            first_name="John",
            last_name="Doe",
            email="john@company.com",
            department="Engineering",
            job_title="Software Engineer",
            manager_id="mgr-001",
            hire_date=datetime(2020, 1, 15),
            status=EmployeeStatus.ACTIVE,
            location="New York",
            phone="555-123-4567",
        )

        assert employee.id == "emp-001"
        assert employee.first_name == "John"
        assert employee.email == "john@company.com"
        assert employee.status == EmployeeStatus.ACTIVE

    def test_employee_model_required_fields(self):
        """Employee model requires specific fields."""
        with pytest.raises(Exception):
            # Missing required fields
            Employee()

    def test_employee_with_minimal_fields(self):
        """Employee can be created with just required fields."""
        employee = Employee(
            id="emp-001",
            hris_id="hr-001",
            first_name="John",
            last_name="Doe",
            email="john@company.com",
            department="Engineering",
            job_title="Engineer",
            hire_date=datetime(2020, 1, 1),
            status=EmployeeStatus.ACTIVE,
            location="Remote",
        )

        assert employee.id == "emp-001"
        assert employee.phone is None


class TestLeaveBalanceModel:
    """Tests for LeaveBalance data model."""

    def test_leave_balance_model_creation(self):
        """LeaveBalance model can be created."""
        balance = LeaveBalance(
            employee_id="emp-001",
            leave_type=LeaveType.PTO,
            total_days=20.0,
            used_days=5.0,
            pending_days=2.0,
            available_days=13.0,
        )

        assert balance.employee_id == "emp-001"
        assert balance.leave_type == LeaveType.PTO
        assert balance.total_days == 20.0
        assert balance.available_days == 13.0

    def test_leave_balance_available_calculation(self):
        """LeaveBalance available is correctly calculated."""
        balance = LeaveBalance(
            employee_id="emp-001",
            leave_type=LeaveType.SICK,
            total_days=10.0,
            used_days=2.0,
            pending_days=1.0,
            available_days=7.0,
        )

        # Available should be total - used - pending
        expected_available = 10.0 - 2.0 - 1.0
        assert balance.available_days == expected_available

    def test_leave_balance_multiple_types(self):
        """Multiple leave balance records can be created."""
        pto_balance = LeaveBalance(
            employee_id="emp-001",
            leave_type=LeaveType.PTO,
            total_days=20.0,
            used_days=5.0,
            pending_days=0.0,
            available_days=15.0,
        )

        sick_balance = LeaveBalance(
            employee_id="emp-001",
            leave_type=LeaveType.SICK,
            total_days=10.0,
            used_days=2.0,
            pending_days=0.0,
            available_days=8.0,
        )

        assert pto_balance.leave_type != sick_balance.leave_type
        assert pto_balance.total_days != sick_balance.total_days


class TestLeaveRequestModel:
    """Tests for LeaveRequest data model."""

    def test_leave_request_model_creation(self):
        """LeaveRequest model can be created."""
        now = datetime.now()
        request = LeaveRequest(
            id="leave-001",
            employee_id="emp-001",
            leave_type=LeaveType.PTO,
            start_date=now,
            end_date=datetime(2025, 2, 20),
            status=LeaveStatus.PENDING,
            reason="Vacation",
            approver_id="mgr-001",
            submitted_at=now,
        )

        assert request.id == "leave-001"
        assert request.employee_id == "emp-001"
        assert request.status == LeaveStatus.PENDING

    def test_leave_request_status_transitions(self):
        """LeaveRequest tracks different statuses."""
        now = datetime.now()

        pending = LeaveRequest(
            employee_id="emp-001",
            leave_type=LeaveType.PTO,
            start_date=now,
            end_date=datetime(2025, 2, 20),
            status=LeaveStatus.PENDING,
            submitted_at=now,
        )

        approved = LeaveRequest(
            employee_id="emp-001",
            leave_type=LeaveType.PTO,
            start_date=now,
            end_date=datetime(2025, 2, 20),
            status=LeaveStatus.APPROVED,
            submitted_at=now,
        )

        assert pending.status == LeaveStatus.PENDING
        assert approved.status == LeaveStatus.APPROVED


class TestConnectorRegistry:
    """Tests for HRIS connector registry."""

    def test_connector_registry_register_and_get(self):
        """Connectors can be registered and retrieved."""

        class MockConnector(HRISConnector):
            def get_employee(self, employee_id):
                return None

            def search_employees(self, filters):
                return []

            def get_leave_balance(self, employee_id):
                return []

            def get_leave_requests(self, employee_id, status=None):
                return []

            def submit_leave_request(self, request):
                return request

            def get_org_chart(self, department=None):
                return []

            def get_benefits(self, employee_id):
                return []

            def health_check(self):
                return True

        # Clear registry
        ConnectorRegistry._registry = {}

        # Register
        ConnectorRegistry.register("mock", MockConnector)

        # Retrieve
        retrieved = ConnectorRegistry.get("mock")

        assert retrieved == MockConnector

    def test_connector_registry_invalid_connector_raises(self):
        """Registering non-HRISConnector raises error."""

        class InvalidConnector:
            pass

        ConnectorRegistry._registry = {}

        with pytest.raises(ValueError):
            ConnectorRegistry.register("invalid", InvalidConnector)

    def test_connector_registry_unknown_returns_none(self):
        """Getting unknown connector returns None."""
        ConnectorRegistry._registry = {}

        result = ConnectorRegistry.get("unknown")

        assert result is None

    def test_connector_registry_list_connectors(self):
        """List all registered connectors."""

        class Connector1(HRISConnector):
            def get_employee(self, employee_id):
                return None

            def search_employees(self, filters):
                return []

            def get_leave_balance(self, employee_id):
                return []

            def get_leave_requests(self, employee_id, status=None):
                return []

            def submit_leave_request(self, request):
                return request

            def get_org_chart(self, department=None):
                return []

            def get_benefits(self, employee_id):
                return []

            def health_check(self):
                return True

        ConnectorRegistry._registry = {}
        ConnectorRegistry.register("conn1", Connector1)
        ConnectorRegistry.register("conn2", Connector1)

        connectors = ConnectorRegistry.list_connectors()

        assert "conn1" in connectors
        assert "conn2" in connectors
        assert len(connectors) >= 2


class TestEmployeeStatus:
    """Tests for EmployeeStatus enum."""

    def test_employee_status_values(self):
        """EmployeeStatus has expected values."""
        assert EmployeeStatus.ACTIVE.value == "active"
        assert EmployeeStatus.INACTIVE.value == "inactive"
        assert EmployeeStatus.ON_LEAVE.value == "on_leave"
        assert EmployeeStatus.TERMINATED.value == "terminated"


class TestLeaveType:
    """Tests for LeaveType enum."""

    def test_leave_type_values(self):
        """LeaveType has expected values."""
        assert LeaveType.PTO.value == "pto"
        assert LeaveType.SICK.value == "sick"
        assert LeaveType.PERSONAL.value == "personal"
        assert LeaveType.UNPAID.value == "unpaid"


class TestLeaveStatus:
    """Tests for LeaveStatus enum."""

    def test_leave_status_values(self):
        """LeaveStatus has expected values."""
        assert LeaveStatus.PENDING.value == "pending"
        assert LeaveStatus.APPROVED.value == "approved"
        assert LeaveStatus.DENIED.value == "denied"
        assert LeaveStatus.CANCELLED.value == "cancelled"


class TestHRISConnectorInterface:
    """Tests for HRISConnector abstract interface."""

    def test_hris_connector_is_abstract(self):
        """HRISConnector is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            HRISConnector()

    def test_hris_connector_subclass_implements_methods(self):
        """Subclass must implement all abstract methods."""

        class IncompleteConnector(HRISConnector):
            def get_employee(self, employee_id):
                return None

        with pytest.raises(TypeError):
            IncompleteConnector()

    def test_hris_connector_complete_subclass(self):
        """Complete subclass can be instantiated."""

        class CompleteConnector(HRISConnector):
            def get_employee(self, employee_id):
                return None

            def search_employees(self, filters):
                return []

            def get_leave_balance(self, employee_id):
                return []

            def get_leave_requests(self, employee_id, status=None):
                return []

            def submit_leave_request(self, request):
                return request

            def get_org_chart(self, department=None):
                return []

            def get_benefits(self, employee_id):
                return []

            def health_check(self):
                return True

        connector = CompleteConnector()
        assert connector is not None

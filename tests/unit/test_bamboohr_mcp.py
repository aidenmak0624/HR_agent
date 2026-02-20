"""
Tests for BambooHR MCP server tools.

Tests both the standalone BambooHR MCP server (src/mcp/bamboohr_mcp.py)
and the BambooHR tools integrated into the main FastMCP server.
Uses mocked BambooHR API responses — no real API calls are made.
"""

import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root on path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.connectors.hris_interface import (
    Employee,
    EmployeeStatus,
    LeaveBalance,
    LeaveType,
    LeaveRequest,
    LeaveStatus,
    OrgNode,
    BenefitsPlan,
    PlanType,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_employee():
    """Sample Employee object."""
    return Employee(
        id="101",
        hris_id="101",
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@company.com",
        department="Engineering",
        job_title="Senior Engineer",
        manager_id="50",
        hire_date=datetime(2022, 3, 15),
        status=EmployeeStatus.ACTIVE,
        location="San Francisco",
        phone="+1-555-0101",
    )


@pytest.fixture
def mock_leave_balances():
    """Sample leave balances."""
    return [
        LeaveBalance(
            employee_id="101",
            leave_type=LeaveType.PTO,
            total_days=20.0,
            used_days=5.0,
            pending_days=2.0,
            available_days=13.0,
        ),
        LeaveBalance(
            employee_id="101",
            leave_type=LeaveType.SICK,
            total_days=10.0,
            used_days=1.0,
            pending_days=0.0,
            available_days=9.0,
        ),
    ]


@pytest.fixture
def mock_benefits():
    """Sample benefits plans."""
    return [
        BenefitsPlan(
            id="b1",
            name="Premium Health Plan",
            plan_type=PlanType.HEALTH,
            coverage_level="Family",
            employee_cost=250.0,
            employer_cost=500.0,
        ),
    ]


@pytest.fixture
def mock_connector(mock_employee, mock_leave_balances, mock_benefits):
    """Mocked BambooHRConnector."""
    connector = MagicMock()
    connector.get_employee.return_value = mock_employee
    connector.search_employees.return_value = [mock_employee]
    connector.get_leave_balance.return_value = mock_leave_balances
    connector.get_leave_requests.return_value = []
    connector.submit_leave_request.return_value = LeaveRequest(
        id="lr-999",
        employee_id="101",
        leave_type=LeaveType.PTO,
        start_date=datetime(2025, 7, 1),
        end_date=datetime(2025, 7, 5),
        status=LeaveStatus.PENDING,
        reason="Summer vacation",
        submitted_at=datetime.utcnow(),
    )
    connector.get_org_chart.return_value = [
        OrgNode(
            employee_id="50",
            name="John Manager",
            title="VP Engineering",
            department="Engineering",
            direct_reports=[
                OrgNode(
                    employee_id="101",
                    name="Jane Doe",
                    title="Senior Engineer",
                    department="Engineering",
                    direct_reports=[],
                )
            ],
        )
    ]
    connector.get_benefits.return_value = mock_benefits
    connector.health_check.return_value = True
    return connector


# ============================================================
# Standalone BambooHR MCP server tests
# ============================================================


class TestBambooHRMCPStandalone:
    """Tests for the standalone bamboohr_mcp server module."""

    @patch.dict(os.environ, {"BAMBOOHR_API_KEY": "test-key", "BAMBOOHR_SUBDOMAIN": "testco"})
    @patch("src.mcp.bamboohr_mcp._connector", None)
    @patch("src.mcp.bamboohr_mcp.BambooHRConnector", autospec=True)
    def _patch_connector(self, MockCls, mock_connector):
        """Helper: patch the connector module-level cache."""
        MockCls.return_value = mock_connector
        from src.mcp import bamboohr_mcp

        bamboohr_mcp._connector = None  # Reset cache
        return bamboohr_mcp

    def test_get_employee(self, mock_connector):
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "k", "BAMBOOHR_SUBDOMAIN": "s"}):
            with patch("src.connectors.bamboohr.BambooHRConnector", return_value=mock_connector):
                from src.mcp.bamboohr_mcp import bamboohr_get_employee, _get_connector
                import src.mcp.bamboohr_mcp as mod

                mod._connector = mock_connector
                try:
                    result = json.loads(bamboohr_get_employee("101"))
                    assert result["first_name"] == "Jane"
                    assert result["department"] == "Engineering"
                finally:
                    mod._connector = None

    def test_search_employees(self, mock_connector):
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "k", "BAMBOOHR_SUBDOMAIN": "s"}):
            import src.mcp.bamboohr_mcp as mod

            mod._connector = mock_connector
            try:
                from src.mcp.bamboohr_mcp import bamboohr_search_employees

                result = json.loads(bamboohr_search_employees(department="Engineering"))
                assert result["count"] == 1
                assert result["employees"][0]["last_name"] == "Doe"
            finally:
                mod._connector = None

    def test_get_leave_balance(self, mock_connector):
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "k", "BAMBOOHR_SUBDOMAIN": "s"}):
            import src.mcp.bamboohr_mcp as mod

            mod._connector = mock_connector
            try:
                from src.mcp.bamboohr_mcp import bamboohr_get_leave_balance

                result = json.loads(bamboohr_get_leave_balance("101"))
                assert result["count"] == 2
                assert result["balances"][0]["available_days"] == 13.0
            finally:
                mod._connector = None

    def test_submit_leave_request(self, mock_connector):
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "k", "BAMBOOHR_SUBDOMAIN": "s"}):
            import src.mcp.bamboohr_mcp as mod

            mod._connector = mock_connector
            try:
                from src.mcp.bamboohr_mcp import bamboohr_submit_leave_request

                result = json.loads(
                    bamboohr_submit_leave_request(
                        "101", "pto", "2025-07-01", "2025-07-05", "Vacation"
                    )
                )
                assert result["status"] == "pending"
                assert result["request_id"] == "lr-999"
            finally:
                mod._connector = None

    def test_get_org_chart(self, mock_connector):
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "k", "BAMBOOHR_SUBDOMAIN": "s"}):
            import src.mcp.bamboohr_mcp as mod

            mod._connector = mock_connector
            try:
                from src.mcp.bamboohr_mcp import bamboohr_get_org_chart

                result = json.loads(bamboohr_get_org_chart())
                assert result["root_count"] == 1
                assert len(result["org_chart"][0]["direct_reports"]) == 1
            finally:
                mod._connector = None

    def test_get_benefits(self, mock_connector):
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "k", "BAMBOOHR_SUBDOMAIN": "s"}):
            import src.mcp.bamboohr_mcp as mod

            mod._connector = mock_connector
            try:
                from src.mcp.bamboohr_mcp import bamboohr_get_benefits

                result = json.loads(bamboohr_get_benefits("101"))
                assert result["count"] == 1
                assert result["benefits"][0]["name"] == "Premium Health Plan"
            finally:
                mod._connector = None

    def test_health_check(self, mock_connector):
        with patch.dict(os.environ, {"BAMBOOHR_API_KEY": "k", "BAMBOOHR_SUBDOMAIN": "s"}):
            import src.mcp.bamboohr_mcp as mod

            mod._connector = mock_connector
            try:
                from src.mcp.bamboohr_mcp import bamboohr_health_check

                result = json.loads(bamboohr_health_check())
                assert result["status"] == "healthy"
            finally:
                mod._connector = None

    def test_missing_credentials_returns_error(self):
        """Tools should return a helpful error when credentials are missing."""
        with patch.dict(
            os.environ, {"BAMBOOHR_API_KEY": "", "BAMBOOHR_SUBDOMAIN": ""}, clear=False
        ):
            import src.mcp.bamboohr_mcp as mod

            mod._connector = None
            from src.mcp.bamboohr_mcp import bamboohr_health_check

            result = json.loads(bamboohr_health_check())
            assert "error" in result
            assert "BAMBOOHR_API_KEY" in result["error"]


# ============================================================
# FastMCP integrated BambooHR tools tests
# ============================================================


class TestBambooHRToolsInFastMCP:
    """Tests for BambooHR tools registered on the main FastMCP server."""

    def test_bamboohr_tools_exist(self):
        """Verify BambooHR tools are registered on the main MCP server."""
        from src.mcp.fastmcp_server import mcp

        tool_names = [t.name for t in mcp._tool_manager.list_tools()]
        expected = [
            "bamboohr_get_employee",
            "bamboohr_search_employees",
            "bamboohr_get_leave_balance",
            "bamboohr_get_leave_requests",
            "bamboohr_submit_leave_request",
            "bamboohr_get_org_chart",
            "bamboohr_get_benefits",
            "bamboohr_health_check",
            "get_hris_provider_info",
        ]
        for name in expected:
            assert name in tool_names, f"Tool '{name}' not found in FastMCP server"

    @patch.dict(os.environ, {"BAMBOOHR_API_KEY": "", "BAMBOOHR_SUBDOMAIN": ""}, clear=False)
    def test_unconfigured_returns_error(self):
        """BambooHR tools return config error when env vars are missing."""
        from src.mcp.fastmcp_server import bamboohr_health_check as fmcp_health

        result = json.loads(fmcp_health())
        assert "error" in result
        assert "BAMBOOHR_API_KEY" in result["error"]

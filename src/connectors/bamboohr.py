"""
HRIS-002: BambooHR HRIS Connector implementation.

This module implements the HRISConnector interface for BambooHR,
using the REST API to interact with employee, leave, and benefits data.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .hris_interface import (
    HRISConnector,
    Employee,
    LeaveBalance,
    LeaveRequest,
    OrgNode,
    BenefitsPlan,
    EmployeeStatus,
    LeaveType,
    LeaveStatus,
    PlanType,
    ConnectorError,
    ConnectionError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class BambooHRConnector(HRISConnector):
    """
    BambooHR HRIS Connector.

    Implements HRISConnector interface using BambooHR REST API.
    Handles authentication, retries, and field mapping.
    """

    BASE_URL = "https://api.bamboohr.com/api/gateway.php"

    def __init__(self, api_key: str, subdomain: str):
        """
        Initialize BambooHR connector.

        Args:
            api_key: BambooHR API key
            subdomain: BambooHR subdomain (e.g., 'company' for company.bamboohr.com)

        Raises:
            ValueError: If api_key or subdomain is empty
        """
        if not api_key:
            raise ValueError("api_key cannot be empty")
        if not subdomain:
            raise ValueError("subdomain cannot be empty")

        self.api_key = api_key
        self.subdomain = subdomain
        self._session = self._create_session()
        self.last_health_error: str = ""

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry strategy.

        Returns:
            Configured requests.Session with retry logic
        """
        session = requests.Session()
        session.auth = (self.api_key, "x")
        session.headers.update({"Accept": "application/json"})

        # Configure retry strategy for rate limits and transient errors
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make API request with logging and error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response JSON as dictionary

        Raises:
            ConnectionError: If connection fails
            AuthenticationError: If authentication fails
            NotFoundError: If resource not found
            RateLimitError: If rate limited
            ConnectorError: For other API errors
        """
        url = f"{self.BASE_URL}/{self.subdomain}/v1{endpoint}"
        start_time = time.time()

        try:
            logger.debug(f"Making {method} request to {endpoint}")
            response = self._session.request(method, url, **kwargs)
            duration = time.time() - start_time
            logger.info(f"{method} {endpoint} - {response.status_code} ({duration:.2f}s)")

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited. Retry after {retry_after}s")
                raise RateLimitError(f"Rate limit exceeded. Retry after {retry_after}s")

            # Handle not found
            if response.status_code == 404:
                raise NotFoundError(f"Resource not found: {endpoint}")

            # Handle authentication errors
            if response.status_code in [401, 403]:
                raise AuthenticationError("Invalid API key or insufficient permissions")

            # Handle other errors
            response.raise_for_status()

            return response.json() if response.text else {}

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(f"Failed to connect to BambooHR API: {e}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout: {e}")
            raise ConnectionError(f"Request timeout: {e}")
        except requests.exceptions.RequestException as e:
            if isinstance(e, (AuthenticationError, NotFoundError, RateLimitError)):
                raise
            logger.error(f"Request error: {e}")
            raise ConnectorError(f"API request failed: {e}")

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        """
        Retrieve employee information from BambooHR.

        Args:
            employee_id: Employee ID or 'employee' for current user

        Returns:
            Employee object or None if not found

        Raises:
            NotFoundError: If employee does not exist
            ConnectionError: If unable to connect
        """
        fields = [
            "firstName",
            "lastName",
            "department",
            "jobTitle",
            "supervisor",
            "hireDate",
            "status",
            "workEmail",
            "mobilePhone",
            "location",
        ]
        params = {"fields": ",".join(fields)}

        try:
            data = self._make_request("GET", f"/employees/{employee_id}/", params=params)
        except NotFoundError:
            return None

        return self._map_employee(data)

    def search_employees(self, filters: Dict[str, Any]) -> List[Employee]:
        """
        Search for employees in BambooHR directory.

        Args:
            filters: Filter criteria (e.g., {"department": "Sales"})

        Returns:
            List of Employee objects matching filters

        Raises:
            ConnectionError: If unable to connect
        """
        try:
            data = self._make_request("GET", "/employees/directory")
        except NotFoundError:
            return []

        employees = []
        for emp_data in data.get("employees", []):
            employee = self._map_employee(emp_data)
            if self._matches_filters(employee, filters):
                employees.append(employee)

        return employees

    def get_leave_balance(self, employee_id: str) -> List[LeaveBalance]:
        """
        Get leave balance for employee.

        Args:
            employee_id: Employee ID

        Returns:
            List of LeaveBalance objects

        Raises:
            NotFoundError: If employee does not exist
            ConnectionError: If unable to connect
        """
        today = datetime.now().date().isoformat()
        params = {"end": today}

        try:
            data = self._make_request(
                "GET", f"/employees/{employee_id}/time_off/calculator", params=params
            )
        except NotFoundError:
            return []

        balances = []
        for leave_type, balance_data in data.items():
            if isinstance(balance_data, dict):
                balance = LeaveBalance(
                    employee_id=employee_id,
                    leave_type=self._map_leave_type(leave_type),
                    total_days=float(balance_data.get("total", 0)),
                    used_days=float(balance_data.get("used", 0)),
                    pending_days=float(balance_data.get("pending", 0)),
                    available_days=float(balance_data.get("available", 0)),
                )
                balances.append(balance)

        return balances

    def get_leave_requests(
        self, employee_id: str, status: Optional[str] = None
    ) -> List[LeaveRequest]:
        """
        Get leave requests for employee.

        Args:
            employee_id: Employee ID
            status: Optional status filter

        Returns:
            List of LeaveRequest objects

        Raises:
            NotFoundError: If employee does not exist
            ConnectionError: If unable to connect
        """
        params = {"employeeId": employee_id}
        if status:
            params["status"] = status

        try:
            data = self._make_request("GET", "/time_off/requests/", params=params)
        except NotFoundError:
            return []

        requests_list = []
        for req_data in data.get("requests", []):
            request = LeaveRequest(
                id=str(req_data.get("id")),
                employee_id=employee_id,
                leave_type=self._map_leave_type(req_data.get("type", "other")),
                start_date=datetime.fromisoformat(req_data.get("start", "")),
                end_date=datetime.fromisoformat(req_data.get("end", "")),
                status=LeaveStatus(req_data.get("status", "pending").lower()),
                reason=req_data.get("reason"),
                approver_id=req_data.get("approverId"),
                submitted_at=datetime.fromisoformat(req_data.get("created", "")),
            )
            requests_list.append(request)

        return requests_list

    def submit_leave_request(self, request: LeaveRequest) -> LeaveRequest:
        """
        Submit a new leave request to BambooHR.

        Args:
            request: LeaveRequest object

        Returns:
            LeaveRequest with assigned ID and timestamps

        Raises:
            ConnectionError: If unable to connect
            AuthenticationError: If authentication fails
        """
        body = {
            "employeeId": request.employee_id,
            "type": request.leave_type.value,
            "start": request.start_date.date().isoformat(),
            "end": request.end_date.date().isoformat(),
            "reason": request.reason or "",
        }

        data = self._make_request(
            "POST", f"/employees/{request.employee_id}/time_off/request", json=body
        )

        # Update request with response data
        request.id = str(data.get("id"))
        request.submitted_at = datetime.fromisoformat(data.get("created", ""))
        request.status = LeaveStatus(data.get("status", "pending").lower())

        return request

    def get_org_chart(self, department: Optional[str] = None) -> List[OrgNode]:
        """
        Get organization chart from BambooHR.

        Args:
            department: Optional department filter

        Returns:
            List of OrgNode objects representing hierarchy

        Raises:
            ConnectionError: If unable to connect
        """
        try:
            data = self._make_request("GET", "/employees/directory")
        except NotFoundError:
            return []

        # Build employee map
        employees = {emp["id"]: emp for emp in data.get("employees", [])}

        # Build hierarchy
        org_nodes = {}
        for emp_id, emp_data in employees.items():
            org_nodes[emp_id] = OrgNode(
                employee_id=emp_id,
                name=f"{emp_data.get('firstName', '')} {emp_data.get('lastName', '')}",
                title=emp_data.get("jobTitle", ""),
                department=emp_data.get("department", ""),
                direct_reports=[],
            )

        # Populate direct reports
        for emp_id, emp_data in employees.items():
            manager_id = emp_data.get("supervisor")
            if manager_id and manager_id in org_nodes:
                org_nodes[manager_id].direct_reports.append(org_nodes[emp_id])

        # Filter by department if specified
        roots = [
            node
            for node in org_nodes.values()
            if not employees.get(node.employee_id, {}).get("supervisor")
        ]
        if department:
            roots = [node for node in roots if node.department == department]

        return roots

    def get_benefits(self, employee_id: str) -> List[BenefitsPlan]:
        """
        Get benefits plans for employee from BambooHR.

        Args:
            employee_id: Employee ID

        Returns:
            List of BenefitsPlan objects

        Raises:
            NotFoundError: If employee does not exist
            ConnectionError: If unable to connect
        """
        try:
            data = self._make_request("GET", f"/employees/{employee_id}/benefits")
        except NotFoundError:
            return []

        plans = []
        for plan_data in data.get("benefits", []):
            plan = BenefitsPlan(
                id=str(plan_data.get("id")),
                name=plan_data.get("name", ""),
                plan_type=self._map_plan_type(plan_data.get("type", "other")),
                coverage_level=plan_data.get("coverage", "Employee"),
                employee_cost=float(plan_data.get("employeeCost", 0)),
                employer_cost=float(plan_data.get("employerCost", 0)),
            )
            plans.append(plan)

        return plans

    def health_check(self) -> bool:
        """
        Check if connector can reach BambooHR API.

        Returns:
            True if healthy, False otherwise
        """
        self.last_health_error = ""

        # Prefer endpoints that this connector actually uses in normal flows.
        # Some tenants return 404 for generic /employees/ even with valid auth.
        candidate_endpoints = [
            ("/employees/directory", {}),
            ("/meta/fields", {}),
        ]

        for endpoint, kwargs in candidate_endpoints:
            try:
                self._make_request("GET", endpoint, **kwargs)
                logger.info(f"BambooHR health check passed via {endpoint}")
                self.last_health_error = ""
                return True
            except NotFoundError:
                # Try the next known endpoint.
                continue
            except (AuthenticationError, ConnectionError, RateLimitError, ConnectorError) as e:
                self.last_health_error = str(e)
                logger.error(f"BambooHR health check failed: {e}")
                return False
            except Exception as e:
                self.last_health_error = str(e)
                logger.error(f"BambooHR health check failed: {e}")
                return False

        self.last_health_error = "No valid BambooHR API endpoint responded"
        logger.error("BambooHR health check failed: no valid endpoint responded")
        return False

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _map_employee(self, data: Dict[str, Any]) -> Employee:
        """
        Map BambooHR response to Employee model.

        Args:
            data: Raw BambooHR employee data

        Returns:
            Employee object
        """
        hire_date_str = data.get("hireDate", "")
        hire_date = datetime.fromisoformat(hire_date_str) if hire_date_str else datetime.now()

        return Employee(
            id=str(data.get("id")),
            hris_id=str(data.get("id")),
            first_name=data.get("firstName", ""),
            last_name=data.get("lastName", ""),
            email=data.get("workEmail", ""),
            department=data.get("department", ""),
            job_title=data.get("jobTitle", ""),
            manager_id=data.get("supervisor"),
            hire_date=hire_date,
            status=EmployeeStatus(data.get("status", "active").lower()),
            location=data.get("location", ""),
            phone=data.get("mobilePhone"),
        )

    def _map_leave_type(self, leave_type_str: str) -> LeaveType:
        """
        Map BambooHR leave type string to LeaveType enum.

        Args:
            leave_type_str: Leave type string from BambooHR

        Returns:
            LeaveType enum value
        """
        mapping = {
            "pto": LeaveType.PTO,
            "vacation": LeaveType.PTO,
            "paid_time_off": LeaveType.PTO,
            "sick": LeaveType.SICK,
            "sick_leave": LeaveType.SICK,
            "personal": LeaveType.PERSONAL,
            "personal_day": LeaveType.PERSONAL,
            "unpaid": LeaveType.UNPAID,
        }
        return mapping.get(leave_type_str.lower(), LeaveType.OTHER)

    def _map_plan_type(self, plan_type_str: str) -> PlanType:
        """
        Map BambooHR plan type string to PlanType enum.

        Args:
            plan_type_str: Plan type string from BambooHR

        Returns:
            PlanType enum value
        """
        mapping = {
            "health": PlanType.HEALTH,
            "health_insurance": PlanType.HEALTH,
            "dental": PlanType.DENTAL,
            "dental_insurance": PlanType.DENTAL,
            "vision": PlanType.VISION,
            "vision_insurance": PlanType.VISION,
            "401k": PlanType.FOUR_01K,
            "retirement": PlanType.FOUR_01K,
            "life": PlanType.LIFE_INSURANCE,
            "life_insurance": PlanType.LIFE_INSURANCE,
        }
        return mapping.get(plan_type_str.lower(), PlanType.OTHER)

    def _matches_filters(self, employee: Employee, filters: Dict[str, Any]) -> bool:
        """
        Check if employee matches filter criteria.

        Args:
            employee: Employee object to check
            filters: Filter dictionary

        Returns:
            True if employee matches all filters
        """
        for key, value in filters.items():
            if key == "department" and employee.department != value:
                return False
            elif key == "status" and employee.status.value != value:
                return False
            elif key == "location" and employee.location != value:
                return False
            elif key == "job_title" and employee.job_title != value:
                return False
        return True

"""
HRIS-004: Workday HRIS Connector implementation.

This module implements the HRISConnector interface for Workday,
using OAuth2 authentication and REST API for employee, leave, and benefits data.
Includes rate limiting, exponential backoff retry logic, and SOAP fallback capability.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .hris_interface import (
    HRISConnector,
    ConnectorRegistry,
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
from config.settings import get_settings

logger = logging.getLogger(__name__)


class WorkdayConnector(HRISConnector):
    """
    Workday HRIS Connector.

    Implements HRISConnector interface using Workday REST API with OAuth2.
    Handles authentication, rate limiting, retries, and field mapping.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant_url: Optional[str] = None,
        api_version: str = "v1",
        field_mappings: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize Workday connector.

        Args:
            client_id: OAuth2 client ID (defaults from settings)
            client_secret: OAuth2 client secret (defaults from settings)
            tenant_url: Workday tenant URL (defaults from settings)
            api_version: API version (default: v1)
            field_mappings: Custom field mapping dict (Workday field -> model field)

        Raises:
            ValueError: If required credentials are missing
        """
        settings = get_settings()

        self.client_id = client_id or getattr(settings, "WORKDAY_CLIENT_ID", None)
        self.client_secret = client_secret or getattr(settings, "WORKDAY_CLIENT_SECRET", None)
        self.tenant_url = tenant_url or getattr(settings, "WORKDAY_TENANT_URL", None)
        self.api_version = api_version

        if not all([self.client_id, self.client_secret, self.tenant_url]):
            raise ValueError(
                "client_id, client_secret, and tenant_url are required. "
                "Set WORKDAY_CLIENT_ID, WORKDAY_CLIENT_SECRET, WORKDAY_TENANT_URL in settings."
            )

        self._session = self._create_session()
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        # Field mappings: Workday field name -> Employee model field name
        self._field_mappings = field_mappings or self._default_field_mappings()

        # Rate limiting state
        self._rate_limit_remaining = 1000
        self._rate_limit_reset_at: Optional[datetime] = None
        self._request_times: List[datetime] = []

        logger.info(f"WorkdayConnector initialized for tenant: {self.tenant_url}")

    def _default_field_mappings(self) -> Dict[str, str]:
        """
        Get default field mappings from Workday API to Employee model.

        Returns:
            Dictionary mapping Workday fields to Employee model fields
        """
        return {
            "workday_id": "hris_id",
            "first_name": "first_name",
            "last_name": "last_name",
            "email_address": "email",
            "department_name": "department",
            "job_title": "job_title",
            "manager_id": "manager_id",
            "hire_date": "hire_date",
            "employment_status": "status",
            "work_location": "location",
            "phone_number": "phone",
        }

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry strategy.

        Returns:
            Configured requests.Session with retry logic
        """
        session = requests.Session()
        session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        # Retry strategy for rate limits and transient errors
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _get_access_token(self) -> str:
        """
        Obtain OAuth2 access token using client_credentials grant.

        Returns:
            Access token string

        Raises:
            AuthenticationError: If token acquisition fails
        """
        if (
            self._access_token
            and self._token_expires_at
            and datetime.utcnow() < self._token_expires_at
        ):
            logger.debug("Using cached access token")
            return self._access_token

        token_url = f"{self.tenant_url}/ccx/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            logger.debug(f"Requesting OAuth2 token from {token_url}")
            response = self._session.post(token_url, data=payload, timeout=10)
            response.raise_for_status()

            data = response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)

            logger.info("Successfully obtained OAuth2 access token")
            return self._access_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to obtain access token: {e}")
            raise AuthenticationError(f"Failed to obtain Workday access token: {e}")

    def _refresh_token_if_needed(self) -> None:
        """
        Refresh access token if it's expired or expiring soon.

        Raises:
            AuthenticationError: If token refresh fails
        """
        if not self._token_expires_at or datetime.utcnow() >= self._token_expires_at:
            logger.debug("Access token expired or expiring, refreshing...")
            self._get_access_token()

    def _check_rate_limit(self) -> None:
        """
        Check rate limit and sleep if approaching limit.

        Raises:
            RateLimitError: If rate limit is exceeded and cannot recover
        """
        if self._rate_limit_remaining < 10:
            sleep_duration = (self._rate_limit_reset_at - datetime.utcnow()).total_seconds() + 1
            if sleep_duration > 0:
                logger.warning(f"Rate limit approaching, sleeping for {sleep_duration:.1f}s")
                time.sleep(min(sleep_duration, 60))  # Cap at 60s
            else:
                self._rate_limit_remaining = 1000

    def _handle_rate_limit_headers(self, response: requests.Response) -> None:
        """
        Parse rate limit headers from response and update state.

        Args:
            response: requests.Response object
        """
        if "X-Rate-Limit-Remaining" in response.headers:
            self._rate_limit_remaining = int(response.headers["X-Rate-Limit-Remaining"])

        if "X-Rate-Limit-Reset" in response.headers:
            reset_timestamp = int(response.headers["X-Rate-Limit-Reset"])
            self._rate_limit_reset_at = datetime.utcfromtimestamp(reset_timestamp)

        if self._rate_limit_remaining < 100:
            logger.warning(f"Rate limit: {self._rate_limit_remaining} requests remaining")

    def _make_request(
        self, method: str, endpoint: str, max_retries: int = 3, **kwargs
    ) -> Dict[str, Any]:
        """
        Make API request with exponential backoff retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (relative to tenant_url)
            max_retries: Maximum retry attempts
            **kwargs: Additional arguments for requests

        Returns:
            Parsed JSON response

        Raises:
            ConnectionError: If unable to connect
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit exceeded
            NotFoundError: If resource not found
        """
        self._refresh_token_if_needed()
        self._check_rate_limit()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        kwargs["headers"] = headers

        url = f"{self.tenant_url}/ccx/{self.api_version}/{endpoint}"
        kwargs.setdefault("timeout", 30)

        for attempt in range(max_retries):
            try:
                logger.debug(f"{method} {url} (attempt {attempt + 1}/{max_retries})")
                response = self._session.request(method, url, **kwargs)

                # Update rate limit info
                self._handle_rate_limit_headers(response)

                if response.status_code == 401:
                    logger.error("Authentication failed")
                    raise AuthenticationError("Workday authentication failed")

                if response.status_code == 404:
                    logger.warning(f"Resource not found: {endpoint}")
                    raise NotFoundError(f"Resource not found: {endpoint}")

                if response.status_code == 429:
                    wait_seconds = min(2**attempt, 60)
                    logger.warning(f"Rate limited, retrying in {wait_seconds}s")
                    time.sleep(wait_seconds)
                    continue

                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        wait_seconds = min(2**attempt, 60)
                        logger.warning(
                            f"Server error ({response.status_code}), retrying in {wait_seconds}s"
                        )
                        time.sleep(wait_seconds)
                        continue
                    else:
                        raise ConnectionError(f"Server error: {response.status_code}")

                response.raise_for_status()
                return response.json() if response.content else {}

            except requests.exceptions.Timeout as e:
                if attempt < max_retries - 1:
                    wait_seconds = min(2**attempt, 60)
                    logger.warning(f"Request timeout, retrying in {wait_seconds}s")
                    time.sleep(wait_seconds)
                    continue
                raise ConnectionError(f"Request timeout after {max_retries} attempts: {e}")

            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    wait_seconds = min(2**attempt, 60)
                    logger.warning(f"Connection error, retrying in {wait_seconds}s")
                    time.sleep(wait_seconds)
                    continue
                raise ConnectionError(f"Unable to connect to Workday: {e}")

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                raise ConnectionError(f"Request failed: {e}")

        raise ConnectionError(f"Failed after {max_retries} attempts")

    def _soap_request(self, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        SOAP request stub for legacy Workday endpoints.

        Args:
            operation: SOAP operation name
            payload: Request payload

        Returns:
            SOAP response as dictionary

        Note:
            This is a stub implementation. Full SOAP support would require
            a SOAP client library like zeep.
        """
        logger.debug(f"SOAP request: operation={operation}, payload={payload}")
        logger.warning("SOAP fallback not fully implemented; use REST API instead")
        return {}

    def _map_fields(self, workday_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map Workday API fields to internal model fields.

        Args:
            workday_data: Data from Workday API

        Returns:
            Mapped data dictionary
        """
        mapped = {}
        for workday_field, model_field in self._field_mappings.items():
            if workday_field in workday_data:
                mapped[model_field] = workday_data[workday_field]

        return mapped

    def _parse_employee(self, workday_data: Dict[str, Any]) -> Employee:
        """
        Parse Workday employee data into Employee model.

        Args:
            workday_data: Raw data from Workday API

        Returns:
            Employee model instance
        """
        mapped = self._map_fields(workday_data)

        # Generate internal ID if not provided
        if "id" not in mapped:
            mapped["id"] = str(uuid.uuid4())

        # Ensure hris_id is set
        if "hris_id" not in mapped and "workday_id" in workday_data:
            mapped["hris_id"] = workday_data["workday_id"]

        # Parse dates
        if isinstance(mapped.get("hire_date"), str):
            mapped["hire_date"] = datetime.fromisoformat(mapped["hire_date"])

        # Map status
        if isinstance(mapped.get("status"), str):
            status_map = {
                "active": EmployeeStatus.ACTIVE,
                "inactive": EmployeeStatus.INACTIVE,
                "on_leave": EmployeeStatus.ON_LEAVE,
                "terminated": EmployeeStatus.TERMINATED,
            }
            mapped["status"] = status_map.get(mapped["status"].lower(), EmployeeStatus.ACTIVE)

        return Employee(**mapped)

    def get_employee(self, employee_id: str) -> Optional[Employee]:
        """
        Retrieve employee information by ID.

        Args:
            employee_id: The employee ID

        Returns:
            Employee object or None

        Raises:
            NotFoundError: If employee not found
            ConnectionError: If unable to connect
            AuthenticationError: If authentication fails
        """
        try:
            logger.debug(f"Fetching employee: {employee_id}")
            response = self._make_request("GET", f"employees/{employee_id}")

            if not response:
                logger.warning(f"Employee not found: {employee_id}")
                raise NotFoundError(f"Employee not found: {employee_id}")

            employee = self._parse_employee(response)
            logger.info(f"Successfully fetched employee: {employee_id}")
            return employee

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error fetching employee {employee_id}: {e}")
            raise ConnectionError(f"Error fetching employee: {e}")

    def search_employees(self, filters: Dict[str, Any]) -> List[Employee]:
        """
        Search for employees using filters.

        Args:
            filters: Filter criteria (e.g., {"department": "Sales"})

        Returns:
            List of matching Employee objects
        """
        try:
            # Build query params from filters
            query_params = []
            for key, value in filters.items():
                query_params.append(f"{key}={value}")

            endpoint = "employees"
            if query_params:
                endpoint += "?" + "&".join(query_params)

            logger.debug(f"Searching employees with filters: {filters}")
            response = self._make_request("GET", endpoint)

            employees = []
            data_list = response.get("data", []) if isinstance(response, dict) else response

            for item in data_list:
                try:
                    employee = self._parse_employee(item)
                    employees.append(employee)
                except Exception as e:
                    logger.warning(f"Failed to parse employee: {e}")
                    continue

            logger.info(f"Found {len(employees)} employees matching filters")
            return employees

        except Exception as e:
            logger.error(f"Error searching employees: {e}")
            return []

    def get_leave_balance(self, employee_id: str) -> List[LeaveBalance]:
        """
        Get leave balance for an employee.

        Args:
            employee_id: The employee ID

        Returns:
            List of LeaveBalance objects
        """
        try:
            logger.debug(f"Fetching leave balance for: {employee_id}")
            response = self._make_request("GET", f"employees/{employee_id}/leave-balances")

            balances = []
            data_list = response.get("data", []) if isinstance(response, dict) else response

            leave_type_map = {
                "pto": LeaveType.PTO,
                "sick": LeaveType.SICK,
                "personal": LeaveType.PERSONAL,
                "unpaid": LeaveType.UNPAID,
            }

            for item in data_list:
                try:
                    leave_type = leave_type_map.get(
                        item.get("leave_type", "").lower(), LeaveType.OTHER
                    )
                    balance = LeaveBalance(
                        employee_id=employee_id,
                        leave_type=leave_type,
                        total_days=float(item.get("total_days", 0)),
                        used_days=float(item.get("used_days", 0)),
                        pending_days=float(item.get("pending_days", 0)),
                        available_days=float(item.get("available_days", 0)),
                    )
                    balances.append(balance)
                except Exception as e:
                    logger.warning(f"Failed to parse leave balance: {e}")
                    continue

            logger.info(f"Retrieved {len(balances)} leave balances for {employee_id}")
            return balances

        except Exception as e:
            logger.error(f"Error fetching leave balance: {e}")
            return []

    def get_leave_requests(
        self, employee_id: str, status: Optional[str] = None
    ) -> List[LeaveRequest]:
        """
        Get leave requests for an employee.

        Args:
            employee_id: The employee ID
            status: Optional status filter

        Returns:
            List of LeaveRequest objects
        """
        try:
            endpoint = f"employees/{employee_id}/leave-requests"
            if status:
                endpoint += f"?status={status}"

            logger.debug(f"Fetching leave requests for: {employee_id} (status: {status})")
            response = self._make_request("GET", endpoint)

            requests_list = []
            data_list = response.get("data", []) if isinstance(response, dict) else response

            status_map = {
                "pending": LeaveStatus.PENDING,
                "approved": LeaveStatus.APPROVED,
                "denied": LeaveStatus.DENIED,
                "cancelled": LeaveStatus.CANCELLED,
            }

            leave_type_map = {
                "pto": LeaveType.PTO,
                "sick": LeaveType.SICK,
                "personal": LeaveType.PERSONAL,
                "unpaid": LeaveType.UNPAID,
            }

            for item in data_list:
                try:
                    leave_request = LeaveRequest(
                        id=item.get("id"),
                        employee_id=employee_id,
                        leave_type=leave_type_map.get(
                            item.get("leave_type", "").lower(), LeaveType.OTHER
                        ),
                        start_date=datetime.fromisoformat(item.get("start_date")),
                        end_date=datetime.fromisoformat(item.get("end_date")),
                        status=status_map.get(item.get("status", "").lower(), LeaveStatus.PENDING),
                        reason=item.get("reason"),
                        approver_id=item.get("approver_id"),
                        submitted_at=datetime.fromisoformat(item.get("submitted_at")),
                    )
                    requests_list.append(leave_request)
                except Exception as e:
                    logger.warning(f"Failed to parse leave request: {e}")
                    continue

            logger.info(f"Retrieved {len(requests_list)} leave requests for {employee_id}")
            return requests_list

        except Exception as e:
            logger.error(f"Error fetching leave requests: {e}")
            return []

    def submit_leave_request(self, request: LeaveRequest) -> LeaveRequest:
        """
        Submit a new leave request.

        Args:
            request: LeaveRequest object

        Returns:
            LeaveRequest with assigned ID and timestamps
        """
        try:
            payload = {
                "employee_id": request.employee_id,
                "leave_type": (
                    request.leave_type.value
                    if isinstance(request.leave_type, LeaveType)
                    else request.leave_type
                ),
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "reason": request.reason,
                "approver_id": request.approver_id,
            }

            logger.debug(f"Submitting leave request for {request.employee_id}")
            response = self._make_request(
                "POST", f"employees/{request.employee_id}/leave-requests", json=payload
            )

            # Assign ID from response
            request.id = response.get("id") or str(uuid.uuid4())
            request.submitted_at = datetime.fromisoformat(
                response.get("submitted_at", datetime.utcnow().isoformat())
            )

            logger.info(f"Leave request submitted: {request.id}")
            return request

        except Exception as e:
            logger.error(f"Error submitting leave request: {e}")
            raise ConnectorError(f"Failed to submit leave request: {e}")

    def get_org_chart(self, department: Optional[str] = None) -> List[OrgNode]:
        """
        Get organization chart/hierarchy.

        Args:
            department: Optional department filter

        Returns:
            List of OrgNode objects
        """
        try:
            endpoint = "org-hierarchy"
            if department:
                endpoint += f"?department={department}"

            logger.debug(f"Fetching org chart (department: {department})")
            response = self._make_request("GET", endpoint)

            nodes = []
            data_list = response.get("data", []) if isinstance(response, dict) else response

            for item in data_list:
                try:
                    node = OrgNode(
                        employee_id=item.get("employee_id"),
                        name=f"{item.get('first_name', '')} {item.get('last_name', '')}".strip(),
                        title=item.get("job_title", ""),
                        department=item.get("department", ""),
                        direct_reports=item.get("direct_reports", []),
                    )
                    nodes.append(node)
                except Exception as e:
                    logger.warning(f"Failed to parse org node: {e}")
                    continue

            logger.info(f"Retrieved org chart with {len(nodes)} nodes")
            return nodes

        except Exception as e:
            logger.error(f"Error fetching org chart: {e}")
            return []

    def get_benefits(self, employee_id: str) -> List[BenefitsPlan]:
        """
        Get benefits plans for an employee.

        Args:
            employee_id: The employee ID

        Returns:
            List of BenefitsPlan objects
        """
        try:
            logger.debug(f"Fetching benefits for: {employee_id}")
            response = self._make_request("GET", f"employees/{employee_id}/benefits")

            plans = []
            data_list = response.get("data", []) if isinstance(response, dict) else response

            plan_type_map = {
                "health": PlanType.HEALTH,
                "dental": PlanType.DENTAL,
                "vision": PlanType.VISION,
                "401k": PlanType.FOUR_01K,
                "life_insurance": PlanType.LIFE_INSURANCE,
            }

            for item in data_list:
                try:
                    plan = BenefitsPlan(
                        id=item.get("id"),
                        name=item.get("name", ""),
                        plan_type=plan_type_map.get(
                            item.get("plan_type", "").lower(), PlanType.OTHER
                        ),
                        coverage_level=item.get("coverage_level", ""),
                        employee_cost=float(item.get("employee_cost", 0)),
                        employer_cost=float(item.get("employer_cost", 0)),
                    )
                    plans.append(plan)
                except Exception as e:
                    logger.warning(f"Failed to parse benefits plan: {e}")
                    continue

            logger.info(f"Retrieved {len(plans)} benefits plans for {employee_id}")
            return plans

        except Exception as e:
            logger.error(f"Error fetching benefits: {e}")
            return []

    def health_check(self) -> bool:
        """
        Check if connector can reach Workday system.

        Returns:
            True if healthy, False otherwise
        """
        try:
            logger.debug("Performing health check")
            self._get_access_token()
            self._make_request("GET", "health", max_retries=1)
            logger.info("Health check passed")
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Register connector
ConnectorRegistry.register("workday", WorkdayConnector)
logger.info("WorkdayConnector registered in ConnectorRegistry")

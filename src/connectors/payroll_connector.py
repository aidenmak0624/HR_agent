"""
PAYROLL-001: Read-only Payroll Data Connector implementation.

This module implements payroll data retrieval from Workday, ADP, Paychex, and
generic HTTP APIs. Includes OAuth2 authentication, rate limiting, retry logic,
and provider-specific field mapping. Read-only operations only.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class PayrollProvider(str, Enum):
    """Supported payroll providers."""
    WORKDAY = "workday"
    ADP = "adp"
    PAYCHEX = "paychex"
    GENERIC = "generic"


# ============================================================================
# Pydantic Models
# ============================================================================

class PayrollConfig(BaseModel):
    """Payroll connector configuration."""
    provider: PayrollProvider = Field(..., description="Payroll provider type")
    base_url: str = Field(..., description="API base URL")
    api_key: Optional[str] = Field(None, description="API key for authentication")
    client_id: Optional[str] = Field(None, description="OAuth2 client ID")
    client_secret: Optional[str] = Field(None, description="OAuth2 client secret")
    timeout: int = Field(30, description="Request timeout in seconds")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    read_only: bool = Field(True, description="Enforce read-only mode (always True)")

    model_config = ConfigDict(use_enum_values=False)


class PayrollRecord(BaseModel):
    """Individual payroll record for an employee pay period."""
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique record ID")
    employee_id: str = Field(..., description="Employee ID")
    pay_period_start: datetime = Field(..., description="Pay period start date")
    pay_period_end: datetime = Field(..., description="Pay period end date")
    gross_pay: float = Field(..., description="Gross pay amount")
    net_pay: float = Field(..., description="Net pay amount")
    deductions: Dict[str, float] = Field(default_factory=dict, description="Deductions breakdown")
    taxes: Dict[str, float] = Field(default_factory=dict, description="Taxes breakdown")
    benefits: Dict[str, float] = Field(default_factory=dict, description="Benefits breakdown")
    status: str = Field(default="completed", description="Status (completed, pending, draft)")
    currency: str = Field(default="USD", description="Currency code")

    model_config = ConfigDict(use_enum_values=False)


class PayrollSummary(BaseModel):
    """Summary of payroll data for an employee over a period."""
    employee_id: str = Field(..., description="Employee ID")
    period: str = Field(..., description="Period identifier (e.g., '2024-Q1')")
    total_gross: float = Field(..., description="Total gross pay in period")
    total_net: float = Field(..., description="Total net pay in period")
    total_deductions: float = Field(..., description="Total deductions in period")
    total_taxes: float = Field(..., description="Total taxes in period")
    records_count: int = Field(..., description="Number of payroll records in summary")

    model_config = ConfigDict(use_enum_values=False)


# ============================================================================
# Payroll Connector
# ============================================================================

class PayrollConnector:
    """
    Read-only Payroll Data Connector.

    Retrieves payroll information from Workday, ADP, Paychex, or generic HTTP API.
    Includes OAuth2 token caching, rate limiting, retry logic, and field mapping.
    All operations are read-only.
    """

    def __init__(self, config: PayrollConfig) -> None:
        """
        Initialize payroll connector.

        Args:
            config: PayrollConfig instance with provider and credentials

        Raises:
            ValueError: If config is invalid or credentials missing
        """
        if not config.read_only:
            raise ValueError("Payroll connector must be read-only")

        self.config = config
        self.provider = config.provider
        self._session = self._create_session()
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._rate_limit_remaining = 1000
        self._rate_limit_reset_at: Optional[datetime] = None
        self._request_times: List[datetime] = []

        logger.info(f"PayrollConnector initialized for provider: {self.provider}")

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry strategy.

        Returns:
            Configured requests.Session with retry logic
        """
        session = requests.Session()
        session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })

        retry_strategy = Retry(
            total=self.config.retry_attempts,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def authenticate(self) -> bool:
        """
        Authenticate with payroll provider using OAuth2 or API key.

        Returns:
            True if authentication successful

        Raises:
            ValueError: If authentication fails
        """
        try:
            if self.config.client_id and self.config.client_secret:
                return self._authenticate_oauth2()
            elif self.config.api_key:
                self._session.headers.update({
                    'Authorization': f'Bearer {self.config.api_key}'
                })
                logger.info("Authenticated with API key")
                return True
            else:
                raise ValueError("No valid credentials provided")

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise ValueError(f"Failed to authenticate: {e}")

    def _authenticate_oauth2(self) -> bool:
        """
        Obtain OAuth2 access token.

        Returns:
            True if token obtained successfully

        Raises:
            ValueError: If token acquisition fails
        """
        if self._access_token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            logger.debug("Using cached access token")
            return True

        token_endpoints = {
            PayrollProvider.WORKDAY: f"{self.config.base_url}/ccx/oauth2/token",
            PayrollProvider.ADP: f"{self.config.base_url}/auth/oauth/v2/token",
            PayrollProvider.PAYCHEX: f"{self.config.base_url}/api/v2/oauth2/token",
            PayrollProvider.GENERIC: f"{self.config.base_url}/oauth2/token",
        }

        token_url = token_endpoints.get(
            self.provider,
            f"{self.config.base_url}/oauth2/token"
        )

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }

        try:
            logger.debug(f"Requesting OAuth2 token from {token_url}")
            response = self._session.post(token_url, data=payload, timeout=self.config.timeout)
            response.raise_for_status()

            data = response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)

            self._session.headers.update({
                'Authorization': f'Bearer {self._access_token}'
            })

            logger.info("Successfully obtained OAuth2 access token")
            return True

        except Exception as e:
            logger.error(f"OAuth2 token acquisition failed: {e}")
            raise ValueError(f"Failed to obtain access token: {e}")

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP GET request to payroll API with retry logic.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If request fails after retries
        """
        url = f"{self.config.base_url}/{endpoint}"
        params = params or {}

        for attempt in range(self.config.retry_attempts):
            try:
                logger.debug(f"GET {url} (attempt {attempt + 1}/{self.config.retry_attempts})")
                response = self._session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout
                )

                # Update rate limit info
                if "X-Rate-Limit-Remaining" in response.headers:
                    self._rate_limit_remaining = int(response.headers["X-Rate-Limit-Remaining"])

                if response.status_code == 429:
                    wait_seconds = min(2 ** attempt, 60)
                    logger.warning(f"Rate limited, retrying in {wait_seconds}s")
                    time.sleep(wait_seconds)
                    continue

                if response.status_code >= 500:
                    if attempt < self.config.retry_attempts - 1:
                        wait_seconds = min(2 ** attempt, 60)
                        logger.warning(f"Server error ({response.status_code}), retrying in {wait_seconds}s")
                        time.sleep(wait_seconds)
                        continue
                    else:
                        raise ValueError(f"Server error: {response.status_code}")

                response.raise_for_status()
                return response.json() if response.content else {}

            except requests.exceptions.Timeout as e:
                if attempt < self.config.retry_attempts - 1:
                    wait_seconds = min(2 ** attempt, 60)
                    logger.warning(f"Request timeout, retrying in {wait_seconds}s")
                    time.sleep(wait_seconds)
                    continue
                raise ValueError(f"Request timeout after {self.config.retry_attempts} attempts: {e}")

            except requests.exceptions.RequestException as e:
                if attempt < self.config.retry_attempts - 1:
                    wait_seconds = min(2 ** attempt, 60)
                    logger.warning(f"Connection error, retrying in {wait_seconds}s")
                    time.sleep(wait_seconds)
                    continue
                logger.error(f"Request failed: {e}")
                raise ValueError(f"Failed to fetch payroll data: {e}")

        raise ValueError(f"Failed after {self.config.retry_attempts} attempts")

    def _map_provider_fields(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map provider-specific fields to standard PayrollRecord fields.

        Args:
            raw_data: Raw data from provider API

        Returns:
            Mapped data dictionary

        Raises:
            ValueError: If mapping fails
        """
        try:
            if self.provider == PayrollProvider.WORKDAY:
                return {
                    'employee_id': raw_data.get('workdayID'),
                    'pay_period_start': self._parse_date(raw_data.get('periodStartDate')),
                    'pay_period_end': self._parse_date(raw_data.get('periodEndDate')),
                    'gross_pay': float(raw_data.get('grossPay', 0)),
                    'net_pay': float(raw_data.get('netPay', 0)),
                    'deductions': raw_data.get('deductions', {}),
                    'taxes': raw_data.get('taxes', {}),
                    'benefits': raw_data.get('benefits', {}),
                    'status': raw_data.get('paymentStatus', 'completed'),
                    'currency': raw_data.get('currency', 'USD'),
                }
            elif self.provider == PayrollProvider.ADP:
                return {
                    'employee_id': raw_data.get('employeeId'),
                    'pay_period_start': self._parse_date(raw_data.get('payPeriodStartDate')),
                    'pay_period_end': self._parse_date(raw_data.get('payPeriodEndDate')),
                    'gross_pay': float(raw_data.get('grossAmount', 0)),
                    'net_pay': float(raw_data.get('netAmount', 0)),
                    'deductions': raw_data.get('deductionBreakdown', {}),
                    'taxes': raw_data.get('taxBreakdown', {}),
                    'benefits': raw_data.get('benefitBreakdown', {}),
                    'status': raw_data.get('payCheckStatus', 'completed'),
                    'currency': raw_data.get('currencyCode', 'USD'),
                }
            elif self.provider == PayrollProvider.PAYCHEX:
                return {
                    'employee_id': raw_data.get('empID'),
                    'pay_period_start': self._parse_date(raw_data.get('checkPeriodStartDate')),
                    'pay_period_end': self._parse_date(raw_data.get('checkPeriodEndDate')),
                    'gross_pay': float(raw_data.get('grossPayAmount', 0)),
                    'net_pay': float(raw_data.get('netPayAmount', 0)),
                    'deductions': raw_data.get('deductionsDetail', {}),
                    'taxes': raw_data.get('taxesDetail', {}),
                    'benefits': raw_data.get('benefitsDetail', {}),
                    'status': raw_data.get('checkStatus', 'completed'),
                    'currency': raw_data.get('currency', 'USD'),
                }
            else:  # GENERIC
                return {
                    'employee_id': raw_data.get('employee_id'),
                    'pay_period_start': self._parse_date(raw_data.get('pay_period_start')),
                    'pay_period_end': self._parse_date(raw_data.get('pay_period_end')),
                    'gross_pay': float(raw_data.get('gross_pay', 0)),
                    'net_pay': float(raw_data.get('net_pay', 0)),
                    'deductions': raw_data.get('deductions', {}),
                    'taxes': raw_data.get('taxes', {}),
                    'benefits': raw_data.get('benefits', {}),
                    'status': raw_data.get('status', 'completed'),
                    'currency': raw_data.get('currency', 'USD'),
                }
        except Exception as e:
            logger.error(f"Field mapping failed: {e}")
            raise ValueError(f"Failed to map provider fields: {e}")

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> datetime:
        """
        Parse date string to datetime object.

        Args:
            date_str: Date string in ISO format or common formats

        Returns:
            Parsed datetime object
        """
        if not date_str:
            return datetime.utcnow()

        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%m/%d/%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}, using current time")
        return datetime.utcnow()

    def get_payroll_record(self, employee_id: str, pay_period: str) -> Optional[PayrollRecord]:
        """
        Retrieve payroll record for employee in specific pay period.

        Args:
            employee_id: Employee ID
            pay_period: Pay period identifier

        Returns:
            PayrollRecord or None if not found

        Raises:
            ValueError: If request fails
        """
        try:
            logger.debug(f"Fetching payroll record for {employee_id} in {pay_period}")
            response = self._make_request(
                f"payroll/employees/{employee_id}/records",
                params={'period': pay_period}
            )

            if not response:
                logger.warning(f"No payroll record found for {employee_id} in {pay_period}")
                return None

            mapped = self._map_provider_fields(response)
            record = PayrollRecord(**mapped)
            logger.info(f"Retrieved payroll record for {employee_id}")
            return record

        except Exception as e:
            logger.error(f"Error fetching payroll record: {e}")
            raise ValueError(f"Failed to fetch payroll record: {e}")

    def get_payroll_history(
        self,
        employee_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[PayrollRecord]:
        """
        Retrieve payroll history for employee over date range.

        Args:
            employee_id: Employee ID
            start_date: Start date for history
            end_date: End date for history

        Returns:
            List of PayrollRecord objects
        """
        try:
            logger.debug(f"Fetching payroll history for {employee_id} from {start_date} to {end_date}")
            response = self._make_request(
                f"payroll/employees/{employee_id}/history",
                params={
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                }
            )

            records = []
            data_list = response.get('data', []) if isinstance(response, dict) else response

            for item in data_list:
                try:
                    mapped = self._map_provider_fields(item)
                    record = PayrollRecord(**mapped)
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Failed to parse payroll record: {e}")
                    continue

            logger.info(f"Retrieved {len(records)} payroll records for {employee_id}")
            return records

        except Exception as e:
            logger.error(f"Error fetching payroll history: {e}")
            return []

    def get_payroll_summary(self, employee_id: str, year: int) -> Optional[PayrollSummary]:
        """
        Get payroll summary for employee for a specific year.

        Args:
            employee_id: Employee ID
            year: Year for summary

        Returns:
            PayrollSummary or None if not found
        """
        try:
            logger.debug(f"Fetching payroll summary for {employee_id} for year {year}")
            response = self._make_request(
                f"payroll/employees/{employee_id}/summary",
                params={'year': year}
            )

            if not response:
                logger.warning(f"No payroll summary found for {employee_id}")
                return None

            summary = PayrollSummary(
                employee_id=employee_id,
                period=f"{year}",
                total_gross=float(response.get('totalGross', 0)),
                total_net=float(response.get('totalNet', 0)),
                total_deductions=float(response.get('totalDeductions', 0)),
                total_taxes=float(response.get('totalTaxes', 0)),
                records_count=int(response.get('recordCount', 0)),
            )
            logger.info(f"Retrieved payroll summary for {employee_id}")
            return summary

        except Exception as e:
            logger.error(f"Error fetching payroll summary: {e}")
            return None

    def get_deduction_breakdown(self, employee_id: str, pay_period: str) -> Dict[str, float]:
        """
        Get detailed deduction breakdown for employee in pay period.

        Args:
            employee_id: Employee ID
            pay_period: Pay period identifier

        Returns:
            Dictionary of deduction types and amounts
        """
        try:
            logger.debug(f"Fetching deduction breakdown for {employee_id} in {pay_period}")
            response = self._make_request(
                f"payroll/employees/{employee_id}/deductions",
                params={'period': pay_period}
            )

            deductions = response.get('deductions', {}) if isinstance(response, dict) else {}
            logger.info(f"Retrieved deduction breakdown for {employee_id}")
            return deductions

        except Exception as e:
            logger.error(f"Error fetching deduction breakdown: {e}")
            return {}

    def get_tax_summary(self, employee_id: str, year: int) -> Dict[str, Any]:
        """
        Get tax summary for employee for a specific year.

        Args:
            employee_id: Employee ID
            year: Year for tax summary

        Returns:
            Dictionary with tax information
        """
        try:
            logger.debug(f"Fetching tax summary for {employee_id} for year {year}")
            response = self._make_request(
                f"payroll/employees/{employee_id}/taxes",
                params={'year': year}
            )

            tax_summary = response if isinstance(response, dict) else {}
            logger.info(f"Retrieved tax summary for {employee_id}")
            return tax_summary

        except Exception as e:
            logger.error(f"Error fetching tax summary: {e}")
            return {}

    def validate_connection(self) -> Dict[str, Any]:
        """
        Validate connection to payroll provider.

        Returns:
            Dictionary with validation status and details
        """
        try:
            logger.debug("Validating payroll connector connection")
            response = self._make_request("health")

            is_healthy = response.get('status') == 'healthy' or response.get('success') is True

            result = {
                'connected': is_healthy,
                'provider': self.provider.value,
                'status': 'connected' if is_healthy else 'disconnected',
                'timestamp': datetime.utcnow().isoformat(),
            }

            logger.info(f"Connection validation: {result}")
            return result

        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            return {
                'connected': False,
                'provider': self.provider.value,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
            }

    def get_pay_periods(self, year: int) -> List[Dict[str, Any]]:
        """
        Get all pay periods for a specific year.

        Args:
            year: Year to retrieve pay periods for

        Returns:
            List of pay period information dictionaries
        """
        try:
            logger.debug(f"Fetching pay periods for year {year}")
            response = self._make_request(
                "payroll/pay-periods",
                params={'year': year}
            )

            periods = response.get('periods', []) if isinstance(response, dict) else response
            logger.info(f"Retrieved {len(periods)} pay periods for year {year}")
            return periods

        except Exception as e:
            logger.error(f"Error fetching pay periods: {e}")
            return []

    def search_records(self, filters: Dict[str, Any]) -> List[PayrollRecord]:
        """
        Search payroll records using filter criteria.

        Args:
            filters: Dictionary of filter criteria (employee_id, status, date range, etc.)

        Returns:
            List of matching PayrollRecord objects
        """
        try:
            logger.debug(f"Searching payroll records with filters: {filters}")
            response = self._make_request(
                "payroll/records/search",
                params=filters
            )

            records = []
            data_list = response.get('data', []) if isinstance(response, dict) else response

            for item in data_list:
                try:
                    mapped = self._map_provider_fields(item)
                    record = PayrollRecord(**mapped)
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Failed to parse payroll record: {e}")
                    continue

            logger.info(f"Found {len(records)} payroll records matching filters")
            return records

        except Exception as e:
            logger.error(f"Error searching payroll records: {e}")
            return []

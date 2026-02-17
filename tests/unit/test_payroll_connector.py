"""
Unit tests for payroll_connector.py module.

Tests cover all PayrollConnector classes and methods with comprehensive
coverage of enums, models, authentication, and data retrieval operations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import uuid
import json

from src.connectors.payroll_connector import (
    PayrollProvider,
    PayrollConfig,
    PayrollRecord,
    PayrollSummary,
    PayrollConnector,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def valid_config():
    """Create a valid PayrollConfig for testing."""
    return PayrollConfig(
        provider=PayrollProvider.GENERIC,
        base_url="https://api.payroll.example.com",
        api_key="test-api-key-123"
    )


@pytest.fixture
def oauth_config():
    """Create a PayrollConfig with OAuth2 credentials."""
    return PayrollConfig(
        provider=PayrollProvider.WORKDAY,
        base_url="https://workday.example.com",
        client_id="test-client-id",
        client_secret="test-client-secret"
    )


@pytest.fixture
def payroll_connector(valid_config):
    """Create a PayrollConnector instance for testing."""
    return PayrollConnector(valid_config)


@pytest.fixture
def payroll_record():
    """Create a sample PayrollRecord."""
    return PayrollRecord(
        employee_id="EMP001",
        pay_period_start=datetime(2024, 1, 1),
        pay_period_end=datetime(2024, 1, 15),
        gross_pay=5000.00,
        net_pay=4000.00,
        deductions={"401k": 300.00, "insurance": 200.00},
        taxes={"federal": 800.00, "state": 100.00},
        benefits={"health": 150.00}
    )


# ============================================================================
# Test PayrollProvider Enum
# ============================================================================

class TestPayrollProvider:
    """Tests for PayrollProvider enum."""

    def test_provider_enum_has_workday(self):
        """Test WORKDAY provider is available."""
        assert PayrollProvider.WORKDAY == "workday"

    def test_provider_enum_has_adp(self):
        """Test ADP provider is available."""
        assert PayrollProvider.ADP == "adp"

    def test_provider_enum_has_paychex(self):
        """Test PAYCHEX provider is available."""
        assert PayrollProvider.PAYCHEX == "paychex"

    def test_provider_enum_has_generic(self):
        """Test GENERIC provider is available."""
        assert PayrollProvider.GENERIC == "generic"

    def test_provider_enum_count(self):
        """Test PayrollProvider enum has exactly 4 values."""
        assert len(PayrollProvider) == 4

    def test_provider_enum_string_representation(self):
        """Test provider string representation."""
        assert str(PayrollProvider.WORKDAY.value) == "workday"


# ============================================================================
# Test PayrollConfig Model
# ============================================================================

class TestPayrollConfig:
    """Tests for PayrollConfig model."""

    def test_config_defaults(self):
        """Test PayrollConfig default values."""
        config = PayrollConfig(
            provider=PayrollProvider.GENERIC,
            base_url="https://api.example.com"
        )
        assert config.timeout == 30
        assert config.retry_attempts == 3
        assert config.read_only is True

    def test_config_custom_values(self):
        """Test PayrollConfig with custom values."""
        config = PayrollConfig(
            provider=PayrollProvider.ADP,
            base_url="https://adp.example.com",
            timeout=60,
            retry_attempts=5
        )
        assert config.timeout == 60
        assert config.retry_attempts == 5

    def test_config_read_only_always_true(self):
        """Test that read_only is always enforced as True."""
        config = PayrollConfig(
            provider=PayrollProvider.GENERIC,
            base_url="https://api.example.com",
            read_only=True
        )
        assert config.read_only is True

    def test_config_provider_type(self):
        """Test PayrollConfig stores provider correctly."""
        config = PayrollConfig(
            provider=PayrollProvider.WORKDAY,
            base_url="https://workday.example.com"
        )
        assert config.provider == PayrollProvider.WORKDAY


# ============================================================================
# Test PayrollRecord Model
# ============================================================================

class TestPayrollRecord:
    """Tests for PayrollRecord model."""

    def test_record_defaults(self):
        """Test PayrollRecord default values."""
        record = PayrollRecord(
            employee_id="EMP001",
            pay_period_start=datetime(2024, 1, 1),
            pay_period_end=datetime(2024, 1, 15),
            gross_pay=5000.00,
            net_pay=4000.00
        )
        assert record.status == "completed"
        assert record.currency == "USD"
        assert isinstance(record.deductions, dict)

    def test_record_custom_values(self):
        """Test PayrollRecord with custom values."""
        record = PayrollRecord(
            employee_id="EMP002",
            pay_period_start=datetime(2024, 2, 1),
            pay_period_end=datetime(2024, 2, 15),
            gross_pay=6000.00,
            net_pay=4800.00,
            status="pending",
            currency="EUR"
        )
        assert record.status == "pending"
        assert record.currency == "EUR"

    def test_record_uuid_generation(self):
        """Test PayrollRecord generates unique record_id."""
        record1 = PayrollRecord(
            employee_id="EMP001",
            pay_period_start=datetime(2024, 1, 1),
            pay_period_end=datetime(2024, 1, 15),
            gross_pay=5000.00,
            net_pay=4000.00
        )
        record2 = PayrollRecord(
            employee_id="EMP001",
            pay_period_start=datetime(2024, 1, 1),
            pay_period_end=datetime(2024, 1, 15),
            gross_pay=5000.00,
            net_pay=4000.00
        )
        assert record1.record_id != record2.record_id
        assert len(record1.record_id) > 0

    def test_record_pay_calculations(self):
        """Test PayrollRecord stores pay amounts correctly."""
        record = PayrollRecord(
            employee_id="EMP001",
            pay_period_start=datetime(2024, 1, 1),
            pay_period_end=datetime(2024, 1, 15),
            gross_pay=5000.00,
            net_pay=4000.00,
            deductions={"401k": 300.00, "insurance": 200.00},
            taxes={"federal": 800.00}
        )
        assert record.gross_pay == 5000.00
        assert record.net_pay == 4000.00
        assert record.deductions["401k"] == 300.00
        assert record.taxes["federal"] == 800.00


# ============================================================================
# Test PayrollSummary Model
# ============================================================================

class TestPayrollSummary:
    """Tests for PayrollSummary model."""

    def test_summary_defaults(self):
        """Test PayrollSummary default values."""
        summary = PayrollSummary(
            employee_id="EMP001",
            period="2024-Q1",
            total_gross=15000.00,
            total_net=12000.00,
            total_deductions=1500.00,
            total_taxes=1500.00,
            records_count=3
        )
        assert summary.employee_id == "EMP001"
        assert summary.period == "2024-Q1"

    def test_summary_custom_values(self):
        """Test PayrollSummary with custom values."""
        summary = PayrollSummary(
            employee_id="EMP002",
            period="2024",
            total_gross=50000.00,
            total_net=40000.00,
            total_deductions=5000.00,
            total_taxes=5000.00,
            records_count=12
        )
        assert summary.records_count == 12

    def test_summary_record_counts(self):
        """Test PayrollSummary records_count field."""
        summary = PayrollSummary(
            employee_id="EMP001",
            period="2024-Q1",
            total_gross=15000.00,
            total_net=12000.00,
            total_deductions=1500.00,
            total_taxes=1500.00,
            records_count=0
        )
        assert summary.records_count == 0


# ============================================================================
# Test PayrollConnector Initialization
# ============================================================================

class TestPayrollConnectorInit:
    """Tests for PayrollConnector initialization."""

    def test_connector_creates_with_config(self, valid_config):
        """Test PayrollConnector initializes with config."""
        connector = PayrollConnector(valid_config)
        assert connector is not None
        assert isinstance(connector, PayrollConnector)

    def test_connector_stores_config(self, valid_config):
        """Test PayrollConnector stores the config."""
        connector = PayrollConnector(valid_config)
        assert connector.config == valid_config
        assert connector.config.provider == PayrollProvider.GENERIC

    def test_connector_no_token_initially(self, valid_config):
        """Test PayrollConnector has no access token initially."""
        connector = PayrollConnector(valid_config)
        assert connector._access_token is None
        assert connector._token_expires_at is None

    def test_connector_raises_on_non_readonly(self):
        """Test PayrollConnector raises ValueError if read_only is False."""
        config = PayrollConfig(
            provider=PayrollProvider.GENERIC,
            base_url="https://api.example.com",
            read_only=False
        )
        with pytest.raises(ValueError, match="read-only"):
            PayrollConnector(config)


# ============================================================================
# Test Authentication
# ============================================================================

class TestAuthenticate:
    """Tests for PayrollConnector.authenticate method."""

    def test_successful_auth_with_api_key(self, valid_config):
        """Test successful authentication with API key."""
        connector = PayrollConnector(valid_config)
        result = connector.authenticate()
        assert result is True

    @patch('src.connectors.payroll_connector.requests.Session.post')
    def test_successful_oauth2_auth(self, mock_post, oauth_config):
        """Test successful OAuth2 authentication."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test-token-123',
            'expires_in': 3600
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        connector = PayrollConnector(oauth_config)
        result = connector.authenticate()
        assert result is True
        assert connector._access_token == 'test-token-123'

    def test_failed_auth_raises_error(self, valid_config):
        """Test authentication failure raises ValueError."""
        config = PayrollConfig(
            provider=PayrollProvider.GENERIC,
            base_url="https://api.example.com"
        )
        connector = PayrollConnector(config)
        with pytest.raises(ValueError, match="No valid credentials"):
            connector.authenticate()

    @patch('src.connectors.payroll_connector.requests.Session.post')
    def test_token_caching(self, mock_post, oauth_config):
        """Test OAuth2 token caching."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test-token-123',
            'expires_in': 3600
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        connector = PayrollConnector(oauth_config)
        connector.authenticate()
        first_call_count = mock_post.call_count

        # Second auth should use cached token
        connector.authenticate()
        assert mock_post.call_count == first_call_count


# ============================================================================
# Test Get Payroll Record
# ============================================================================

class TestGetPayrollRecord:
    """Tests for PayrollConnector.get_payroll_record method."""

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_returns_record(self, mock_get, payroll_connector):
        """Test get_payroll_record returns PayrollRecord."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'employee_id': 'EMP001',
            'pay_period_start': '2024-01-01',
            'pay_period_end': '2024-01-15',
            'gross_pay': 5000.00,
            'net_pay': 4000.00
        }
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        record = payroll_connector.get_payroll_record("EMP001", "2024-01")
        assert isinstance(record, PayrollRecord)
        assert record.employee_id == "EMP001"

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_employee_not_found(self, mock_get, payroll_connector):
        """Test get_payroll_record returns None for missing employee."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        record = payroll_connector.get_payroll_record("NONEXISTENT", "2024-01")
        assert record is None

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_invalid_period(self, mock_get, payroll_connector):
        """Test get_payroll_record handles invalid period."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        record = payroll_connector.get_payroll_record("EMP001", "invalid")
        assert record is None


# ============================================================================
# Test Get Payroll History
# ============================================================================

class TestGetPayrollHistory:
    """Tests for PayrollConnector.get_payroll_history method."""

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_returns_history(self, mock_get, payroll_connector):
        """Test get_payroll_history returns list of records."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': [
                {
                    'employee_id': 'EMP001',
                    'pay_period_start': '2024-01-01',
                    'pay_period_end': '2024-01-15',
                    'gross_pay': 5000.00,
                    'net_pay': 4000.00
                },
                {
                    'employee_id': 'EMP001',
                    'pay_period_start': '2024-01-16',
                    'pay_period_end': '2024-01-31',
                    'gross_pay': 5000.00,
                    'net_pay': 4000.00
                }
            ]
        }
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        history = payroll_connector.get_payroll_history(
            "EMP001",
            datetime(2024, 1, 1),
            datetime(2024, 1, 31)
        )
        assert len(history) == 2
        assert all(isinstance(r, PayrollRecord) for r in history)

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_date_range_filtering(self, mock_get, payroll_connector):
        """Test get_payroll_history respects date range."""
        mock_response = Mock()
        mock_response.json.return_value = {'data': []}
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        start = datetime(2024, 1, 1)
        end = datetime(2024, 3, 31)
        history = payroll_connector.get_payroll_history("EMP001", start, end)
        assert isinstance(history, list)

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_empty_results(self, mock_get, payroll_connector):
        """Test get_payroll_history handles empty results."""
        mock_response = Mock()
        mock_response.json.return_value = {'data': []}
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        history = payroll_connector.get_payroll_history(
            "NONEXISTENT",
            datetime(2024, 1, 1),
            datetime(2024, 12, 31)
        )
        assert len(history) == 0


# ============================================================================
# Test Get Payroll Summary
# ============================================================================

class TestGetPayrollSummary:
    """Tests for PayrollConnector.get_payroll_summary method."""

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_returns_summary(self, mock_get, payroll_connector):
        """Test get_payroll_summary returns PayrollSummary."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'totalGross': 50000.00,
            'totalNet': 40000.00,
            'totalDeductions': 5000.00,
            'totalTaxes': 5000.00,
            'recordCount': 12
        }
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        summary = payroll_connector.get_payroll_summary("EMP001", 2024)
        assert isinstance(summary, PayrollSummary)
        assert summary.total_gross == 50000.00

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_calculates_totals(self, mock_get, payroll_connector):
        """Test get_payroll_summary calculates totals correctly."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'totalGross': 100000.00,
            'totalNet': 80000.00,
            'totalDeductions': 10000.00,
            'totalTaxes': 10000.00,
            'recordCount': 26
        }
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        summary = payroll_connector.get_payroll_summary("EMP001", 2024)
        assert summary.total_deductions == 10000.00
        assert summary.total_taxes == 10000.00

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_year_filtering(self, mock_get, payroll_connector):
        """Test get_payroll_summary filters by year."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        summary = payroll_connector.get_payroll_summary("EMP001", 2025)
        assert summary is None


# ============================================================================
# Test Get Deduction Breakdown
# ============================================================================

class TestGetDeductionBreakdown:
    """Tests for PayrollConnector.get_deduction_breakdown method."""

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_returns_breakdown(self, mock_get, payroll_connector):
        """Test get_deduction_breakdown returns dict."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'deductions': {
                '401k': 300.00,
                'insurance': 200.00,
                'hsa': 100.00
            }
        }
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        breakdown = payroll_connector.get_deduction_breakdown("EMP001", "2024-01")
        assert isinstance(breakdown, dict)
        assert breakdown['401k'] == 300.00
        assert breakdown['insurance'] == 200.00

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_empty_deductions(self, mock_get, payroll_connector):
        """Test get_deduction_breakdown handles empty deductions."""
        mock_response = Mock()
        mock_response.json.return_value = {'deductions': {}}
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        breakdown = payroll_connector.get_deduction_breakdown("EMP001", "2024-01")
        assert breakdown == {}

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_valid_structure(self, mock_get, payroll_connector):
        """Test get_deduction_breakdown returns valid structure."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'deductions': {
                'item1': 50.00,
                'item2': 75.00
            }
        }
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        breakdown = payroll_connector.get_deduction_breakdown("EMP001", "2024-01")
        assert all(isinstance(v, float) for v in breakdown.values())


# ============================================================================
# Test Validate Connection
# ============================================================================

class TestValidateConnection:
    """Tests for PayrollConnector.validate_connection method."""

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_successful_validation(self, mock_get, payroll_connector):
        """Test validate_connection succeeds."""
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'healthy'}
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        result = payroll_connector.validate_connection()
        assert result['connected'] is True
        assert result['status'] == 'connected'

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_failed_connection(self, mock_get, payroll_connector):
        """Test validate_connection handles failure."""
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'error'}
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock(side_effect=Exception("Connection error"))
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        result = payroll_connector.validate_connection()
        assert result['connected'] is False
        assert result['status'] == 'error'

    @patch('src.connectors.payroll_connector.requests.Session.get')
    def test_returns_status_dict(self, mock_get, payroll_connector):
        """Test validate_connection returns status dictionary."""
        mock_response = Mock()
        mock_response.json.return_value = {'success': True}
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        payroll_connector.authenticate()
        result = payroll_connector.validate_connection()
        assert isinstance(result, dict)
        assert 'connected' in result
        assert 'provider' in result
        assert 'timestamp' in result

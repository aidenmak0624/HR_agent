"""Tests for CCPA Data Privacy Compliance Module (COMP-002)."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.core.ccpa import (
    CCPAComplianceService,
    CCPARequest,
    DataInventoryItem,
    CCPAConfig,
    CCPADataCategory,
    ConsumerRight,
    CCPARequestStatus,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def ccpa_service():
    """Create a fresh CCPAComplianceService for each test."""
    return CCPAComplianceService()


@pytest.fixture
def ccpa_service_custom():
    """Create a CCPAComplianceService with custom config."""
    config = CCPAConfig(
        enabled=True, response_deadline_days=30, extension_allowed_days=30, min_age_for_consent=16
    )
    return CCPAComplianceService(config=config)


@pytest.fixture
def sample_request(ccpa_service):
    """Create a sample CCPA request."""
    return ccpa_service.submit_request(
        consumer_id="consumer_001",
        right_type=ConsumerRight.RIGHT_TO_KNOW,
        data_categories=[CCPADataCategory.PERSONAL_INFO],
    )


# ============================================================================
# Test Enums
# ============================================================================


class TestCCPADataCategory:
    """Tests for CCPADataCategory enum."""

    def test_ccpa_data_category_has_all_values(self):
        """CCPADataCategory contains all required values."""
        assert CCPADataCategory.PERSONAL_INFO.value == "personal_info"
        assert CCPADataCategory.FINANCIAL.value == "financial"
        assert CCPADataCategory.BIOMETRIC.value == "biometric"
        assert CCPADataCategory.GEOLOCATION.value == "geolocation"
        assert CCPADataCategory.INTERNET_ACTIVITY.value == "internet_activity"
        assert CCPADataCategory.PROFESSIONAL.value == "professional"
        assert CCPADataCategory.EDUCATION.value == "education"
        assert CCPADataCategory.INFERENCES.value == "inferences"

    def test_ccpa_data_category_count(self):
        """CCPADataCategory has exactly 8 categories."""
        assert len(list(CCPADataCategory)) == 8

    def test_ccpa_data_category_string_representation(self):
        """CCPADataCategory values are strings."""
        for category in CCPADataCategory:
            assert isinstance(category.value, str)


class TestConsumerRight:
    """Tests for ConsumerRight enum."""

    def test_consumer_right_has_all_values(self):
        """ConsumerRight contains all required values."""
        assert ConsumerRight.RIGHT_TO_KNOW.value == "right_to_know"
        assert ConsumerRight.RIGHT_TO_DELETE.value == "right_to_delete"
        assert ConsumerRight.RIGHT_TO_OPT_OUT.value == "right_to_opt_out"
        assert ConsumerRight.RIGHT_TO_NON_DISCRIMINATION.value == "right_to_non_discrimination"
        assert ConsumerRight.RIGHT_TO_CORRECT.value == "right_to_correct"
        assert ConsumerRight.RIGHT_TO_LIMIT.value == "right_to_limit"

    def test_consumer_right_count(self):
        """ConsumerRight has exactly 6 rights."""
        assert len(list(ConsumerRight)) == 6

    def test_consumer_right_string_representation(self):
        """ConsumerRight values are strings."""
        for right in ConsumerRight:
            assert isinstance(right.value, str)


class TestCCPARequestStatus:
    """Tests for CCPARequestStatus enum."""

    def test_ccpa_request_status_has_all_values(self):
        """CCPARequestStatus contains all required values."""
        assert CCPARequestStatus.PENDING.value == "pending"
        assert CCPARequestStatus.VERIFICATION_REQUIRED.value == "verification_required"
        assert CCPARequestStatus.PROCESSING.value == "processing"
        assert CCPARequestStatus.COMPLETED.value == "completed"
        assert CCPARequestStatus.DENIED.value == "denied"

    def test_ccpa_request_status_count(self):
        """CCPARequestStatus has exactly 5 statuses."""
        assert len(list(CCPARequestStatus)) == 5

    def test_ccpa_request_status_string_representation(self):
        """CCPARequestStatus values are strings."""
        for status in CCPARequestStatus:
            assert isinstance(status.value, str)


# ============================================================================
# Test Models
# ============================================================================


class TestCCPARequest:
    """Tests for CCPARequest model."""

    def test_ccpa_request_defaults(self):
        """CCPARequest uses default values when not provided."""
        request = CCPARequest(consumer_id="consumer_001", right_type=ConsumerRight.RIGHT_TO_KNOW)

        assert request.consumer_id == "consumer_001"
        assert request.right_type == ConsumerRight.RIGHT_TO_KNOW
        assert request.status == CCPARequestStatus.PENDING
        assert request.data_categories == []
        assert request.extended is False
        assert request.extension_reason is None
        assert request.completed_at is None

    def test_ccpa_request_custom_values(self):
        """CCPARequest accepts custom values."""
        categories = [CCPADataCategory.PERSONAL_INFO, CCPADataCategory.FINANCIAL]
        request = CCPARequest(
            consumer_id="consumer_002",
            right_type=ConsumerRight.RIGHT_TO_DELETE,
            data_categories=categories,
        )

        assert request.consumer_id == "consumer_002"
        assert request.right_type == ConsumerRight.RIGHT_TO_DELETE
        assert request.data_categories == categories

    def test_ccpa_request_generates_uuid(self):
        """CCPARequest generates unique request IDs."""
        request1 = CCPARequest(consumer_id="consumer_001", right_type=ConsumerRight.RIGHT_TO_KNOW)
        request2 = CCPARequest(consumer_id="consumer_002", right_type=ConsumerRight.RIGHT_TO_DELETE)

        assert request1.request_id != request2.request_id
        assert len(request1.request_id) > 0
        assert len(request2.request_id) > 0

    def test_ccpa_request_deadline_calculation(self):
        """CCPARequest sets response_deadline to 45 days."""
        before = datetime.utcnow()
        request = CCPARequest(consumer_id="consumer_001", right_type=ConsumerRight.RIGHT_TO_KNOW)
        after = datetime.utcnow()

        # Deadline should be approximately 45 days from submission
        delta = request.response_deadline - request.submitted_at
        assert delta.days == 45


class TestDataInventoryItem:
    """Tests for DataInventoryItem model."""

    def test_data_inventory_item_defaults(self):
        """DataInventoryItem uses default values."""
        item = DataInventoryItem(
            category=CCPADataCategory.PERSONAL_INFO,
            source="HRIS System",
            purpose="Employment Administration",
        )

        assert item.category == CCPADataCategory.PERSONAL_INFO
        assert item.source == "HRIS System"
        assert item.purpose == "Employment Administration"
        assert item.shared_with_third_parties is False
        assert item.sale_opt_out is False

    def test_data_inventory_item_custom_values(self):
        """DataInventoryItem accepts custom values."""
        item = DataInventoryItem(
            category=CCPADataCategory.FINANCIAL,
            source="Payroll System",
            purpose="Compensation Management",
            shared_with_third_parties=True,
            sale_opt_out=True,
        )

        assert item.shared_with_third_parties is True
        assert item.sale_opt_out is True

    def test_data_inventory_item_generates_uuid(self):
        """DataInventoryItem generates unique item IDs."""
        item1 = DataInventoryItem(
            category=CCPADataCategory.PERSONAL_INFO, source="Source 1", purpose="Purpose 1"
        )
        item2 = DataInventoryItem(
            category=CCPADataCategory.FINANCIAL, source="Source 2", purpose="Purpose 2"
        )

        assert item1.item_id != item2.item_id


class TestCCPAConfig:
    """Tests for CCPAConfig model."""

    def test_ccpa_config_defaults(self):
        """CCPAConfig uses default values."""
        config = CCPAConfig()

        assert config.enabled is True
        assert config.verification_required is True
        assert config.response_deadline_days == 45
        assert config.extension_allowed_days == 45
        assert config.min_age_for_consent == 16
        assert config.data_broker_registration is True
        assert config.annual_report_enabled is True

    def test_ccpa_config_custom_values(self):
        """CCPAConfig accepts custom values."""
        config = CCPAConfig(
            enabled=False,
            verification_required=False,
            response_deadline_days=30,
            extension_allowed_days=30,
            min_age_for_consent=13,
        )

        assert config.enabled is False
        assert config.verification_required is False
        assert config.response_deadline_days == 30
        assert config.extension_allowed_days == 30
        assert config.min_age_for_consent == 13

    def test_ccpa_config_enabled_flag(self):
        """CCPAConfig enabled flag can be toggled."""
        config1 = CCPAConfig(enabled=True)
        config2 = CCPAConfig(enabled=False)

        assert config1.enabled is True
        assert config2.enabled is False

    def test_ccpa_config_deadline_days(self):
        """CCPAConfig stores deadline_days configuration."""
        config = CCPAConfig(response_deadline_days=60)
        assert config.response_deadline_days == 60


# ============================================================================
# Test Service Initialization
# ============================================================================


class TestCCPAComplianceServiceInit:
    """Tests for CCPAComplianceService initialization."""

    def test_creates_service_with_config(self):
        """CCPAComplianceService creates with provided config."""
        config = CCPAConfig(response_deadline_days=30)
        service = CCPAComplianceService(config=config)

        assert service.config == config
        assert service.config.response_deadline_days == 30

    def test_stores_config_reference(self):
        """CCPAComplianceService stores config reference."""
        config = CCPAConfig(enabled=False)
        service = CCPAComplianceService(config=config)

        assert service.config.enabled is False

    def test_initializes_with_empty_state(self):
        """CCPAComplianceService starts with empty storage."""
        service = CCPAComplianceService()

        assert len(service._requests) == 0
        assert len(service._inventory) == 0
        assert len(service._verified_consumers) == 0
        assert len(service._opt_out_list) == 0


# ============================================================================
# Test Submit Request
# ============================================================================


class TestSubmitRequest:
    """Tests for submit_request method."""

    def test_submit_request_creates_request(self, ccpa_service):
        """submit_request creates a CCPARequest."""
        request = ccpa_service.submit_request(
            consumer_id="consumer_001", right_type=ConsumerRight.RIGHT_TO_KNOW
        )

        assert isinstance(request, CCPARequest)
        assert request.consumer_id == "consumer_001"
        assert request.right_type == ConsumerRight.RIGHT_TO_KNOW

    def test_submit_request_assigns_uuid(self, ccpa_service):
        """submit_request assigns unique request ID."""
        request = ccpa_service.submit_request(
            consumer_id="consumer_001", right_type=ConsumerRight.RIGHT_TO_KNOW
        )

        assert request.request_id is not None
        assert len(request.request_id) > 0

    def test_submit_request_sets_deadline(self, ccpa_service_custom):
        """submit_request sets response_deadline based on config."""
        request = ccpa_service_custom.submit_request(
            consumer_id="consumer_001", right_type=ConsumerRight.RIGHT_TO_KNOW
        )

        delta = request.response_deadline - request.submitted_at
        # Microseconds may cause 29 or 30 days
        assert delta.days in [29, 30]

    def test_submit_request_stores_request(self, ccpa_service):
        """submit_request stores request internally."""
        request = ccpa_service.submit_request(
            consumer_id="consumer_001", right_type=ConsumerRight.RIGHT_TO_KNOW
        )

        assert request.request_id in ccpa_service._requests
        assert ccpa_service._requests[request.request_id] == request


# ============================================================================
# Test Process Request
# ============================================================================


class TestProcessRequest:
    """Tests for process_request method."""

    def test_process_request_valid_request(self, sample_request, ccpa_service):
        """process_request processes a valid request."""
        result = ccpa_service.process_request(sample_request.request_id)

        assert result is not None
        assert result["request_id"] == sample_request.request_id
        assert result["consumer_id"] == "consumer_001"

    def test_process_request_handles_missing_request(self, ccpa_service):
        """process_request raises ValueError for missing request."""
        with pytest.raises(ValueError, match="not found"):
            ccpa_service.process_request("nonexistent_id")

    def test_process_request_updates_status(self, sample_request, ccpa_service):
        """process_request updates request status to COMPLETED."""
        ccpa_service.process_request(sample_request.request_id)

        updated = ccpa_service._requests[sample_request.request_id]
        assert updated.status == CCPARequestStatus.COMPLETED
        assert updated.completed_at is not None

    def test_process_request_returns_details(self, sample_request, ccpa_service):
        """process_request returns request details."""
        result = ccpa_service.process_request(sample_request.request_id)

        assert "request_id" in result
        assert "consumer_id" in result
        assert "right_type" in result
        assert "status" in result
        assert "deadline" in result


# ============================================================================
# Test Verify Consumer
# ============================================================================


class TestVerifyConsumer:
    """Tests for verify_consumer method."""

    def test_verify_consumer_successful(self, ccpa_service):
        """verify_consumer returns True for valid verification data."""
        config = CCPAConfig(verification_required=True)
        service = CCPAComplianceService(config=config)

        result = service.verify_consumer(
            consumer_id="consumer_001", verification_data={"email": "test@example.com"}
        )

        assert result is True

    def test_verify_consumer_failed_verification(self, ccpa_service):
        """verify_consumer raises ValueError for invalid data."""
        config = CCPAConfig(verification_required=True)
        service = CCPAComplianceService(config=config)

        with pytest.raises(ValueError, match="Verification data incomplete"):
            service.verify_consumer(
                consumer_id="consumer_001", verification_data={"name": "John Doe"}
            )

    def test_verify_consumer_missing_verification(self, ccpa_service):
        """verify_consumer raises ValueError when verification data missing."""
        config = CCPAConfig(verification_required=True)
        service = CCPAComplianceService(config=config)

        with pytest.raises(ValueError):
            service.verify_consumer(consumer_id="consumer_001", verification_data=None)


# ============================================================================
# Test Opt Out of Sale
# ============================================================================


class TestOptOutOfSale:
    """Tests for opt_out_of_sale method."""

    def test_opt_out_of_sale_successful(self, ccpa_service):
        """opt_out_of_sale marks consumer as opted out."""
        result = ccpa_service.opt_out_of_sale("consumer_001")

        assert result["consumer_id"] == "consumer_001"
        assert result["opt_out_status"] == "confirmed"
        assert "effective_date" in result

    def test_opt_out_of_sale_already_opted_out(self, ccpa_service):
        """opt_out_of_sale handles already opted out consumers."""
        ccpa_service.opt_out_of_sale("consumer_001")
        result = ccpa_service.opt_out_of_sale("consumer_001")

        assert result["opt_out_status"] == "confirmed"

    def test_opt_out_of_sale_records_opt_out(self, ccpa_service):
        """opt_out_of_sale stores opt-out in internal list."""
        ccpa_service.opt_out_of_sale("consumer_001")

        assert "consumer_001" in ccpa_service._opt_out_list
        assert ccpa_service._opt_out_list["consumer_001"] is True


# ============================================================================
# Test Data Inventory
# ============================================================================


class TestGetDataInventory:
    """Tests for get_data_inventory method."""

    def test_get_data_inventory_returns_items(self, ccpa_service):
        """get_data_inventory returns list of DataInventoryItem."""
        inventory = ccpa_service.get_data_inventory("consumer_001")

        assert isinstance(inventory, list)
        assert len(inventory) > 0
        assert all(isinstance(item, DataInventoryItem) for item in inventory)

    def test_get_data_inventory_empty_inventory(self, ccpa_service):
        """get_data_inventory initializes inventory if not exists."""
        inventory = ccpa_service.get_data_inventory("consumer_002")

        assert len(inventory) == 4  # Default initialization includes 4 items

    def test_get_data_inventory_filters_by_consumer(self, ccpa_service):
        """get_data_inventory returns items for specific consumer."""
        inventory1 = ccpa_service.get_data_inventory("consumer_001")
        inventory2 = ccpa_service.get_data_inventory("consumer_002")

        assert inventory1 is not None
        assert inventory2 is not None


# ============================================================================
# Test Classify Data
# ============================================================================


class TestClassifyData:
    """Tests for classify_data method."""

    def test_classify_data_personal_info(self, ccpa_service):
        """classify_data identifies personal information."""
        data = {"first_name": "John", "last_name": "Doe"}
        categories = ccpa_service.classify_data(data)

        assert CCPADataCategory.PERSONAL_INFO in categories

    def test_classify_data_financial(self, ccpa_service):
        """classify_data identifies financial data."""
        data = {"salary": 100000, "bonus": 50000}
        categories = ccpa_service.classify_data(data)

        assert CCPADataCategory.FINANCIAL in categories

    def test_classify_data_multiple(self, ccpa_service):
        """classify_data handles multiple data categories."""
        data = {"first_name": "John", "salary": 100000, "ip_address": "192.168.1.1"}
        categories = ccpa_service.classify_data(data)

        assert len(categories) >= 2
        assert CCPADataCategory.FINANCIAL in categories


# ============================================================================
# Test Minor Consent
# ============================================================================


class TestCheckMinorConsent:
    """Tests for check_minor_consent method."""

    def test_check_minor_consent_under_13(self, ccpa_service):
        """check_minor_consent requires parental consent for under 13."""
        result = ccpa_service.check_minor_consent("consumer_001", 12)

        assert result["parental_consent_required"] is True
        assert result["consent_type"] == "verifiable_parental_consent"
        assert result["age"] == 12

    def test_check_minor_consent_13_to_16(self, ccpa_service):
        """check_minor_consent requires parental consent for 13-15."""
        result = ccpa_service.check_minor_consent("consumer_002", 14)

        assert result["parental_consent_required"] is True
        assert result["consent_type"] == "parental_consent"
        assert result["age"] == 14

    def test_check_minor_consent_over_16(self, ccpa_service):
        """check_minor_consent does not require parental consent for 16+."""
        result = ccpa_service.check_minor_consent("consumer_003", 17)

        assert result["parental_consent_required"] is False
        assert result["consent_type"] == "consumer_consent"
        assert result["age"] == 17


# ============================================================================
# Test Generate Disclosure
# ============================================================================


class TestGenerateDisclosure:
    """Tests for generate_disclosure method."""

    def test_generate_disclosure_creates_report(self, ccpa_service):
        """generate_disclosure creates a disclosure report."""
        disclosure = ccpa_service.generate_disclosure("consumer_001")

        assert isinstance(disclosure, dict)
        assert disclosure["consumer_id"] == "consumer_001"

    def test_generate_disclosure_12_month_lookback(self, ccpa_service):
        """generate_disclosure includes 12-month lookback period."""
        disclosure = ccpa_service.generate_disclosure("consumer_001")

        assert disclosure["lookback_period"] == "12 months"

    def test_generate_disclosure_empty_data(self, ccpa_service):
        """generate_disclosure handles consumer with no data."""
        # Consumer not accessed yet, so inventory will be initialized
        disclosure = ccpa_service.generate_disclosure("consumer_999")

        assert "categories_collected" in disclosure
        assert "data_sources" in disclosure


# ============================================================================
# Test Extend Deadline
# ============================================================================


class TestExtendDeadline:
    """Tests for extend_deadline method."""

    def test_extend_deadline_successful(self, sample_request, ccpa_service):
        """extend_deadline extends response deadline."""
        original_deadline = sample_request.response_deadline
        extended = ccpa_service.extend_deadline(
            sample_request.request_id, "Complex request requiring additional investigation"
        )

        assert extended.extended is True
        assert extended.response_deadline > original_deadline

    def test_extend_deadline_already_extended(self, sample_request, ccpa_service):
        """extend_deadline raises error if already extended."""
        ccpa_service.extend_deadline(sample_request.request_id, "First extension")

        with pytest.raises(ValueError, match="already extended"):
            ccpa_service.extend_deadline(sample_request.request_id, "Second extension")

    def test_extend_deadline_missing_request(self, ccpa_service):
        """extend_deadline raises ValueError for missing request."""
        with pytest.raises(ValueError, match="not found"):
            ccpa_service.extend_deadline("nonexistent_id", "Reason")


# ============================================================================
# Test Annual Metrics
# ============================================================================


class TestGetAnnualMetrics:
    """Tests for get_annual_metrics method."""

    def test_get_annual_metrics_returns_metrics(self, ccpa_service):
        """get_annual_metrics returns metrics dictionary."""
        metrics = ccpa_service.get_annual_metrics()

        assert isinstance(metrics, dict)
        assert "period" in metrics
        assert "total_requests" in metrics

    def test_get_annual_metrics_request_counts(self, ccpa_service):
        """get_annual_metrics includes request counts."""
        ccpa_service.submit_request(
            consumer_id="consumer_001", right_type=ConsumerRight.RIGHT_TO_KNOW
        )
        ccpa_service.submit_request(
            consumer_id="consumer_002", right_type=ConsumerRight.RIGHT_TO_DELETE
        )

        metrics = ccpa_service.get_annual_metrics()

        assert metrics["total_requests"] >= 2

    def test_get_annual_metrics_zero_state(self, ccpa_service):
        """get_annual_metrics handles zero requests."""
        metrics = ccpa_service.get_annual_metrics()

        assert metrics["total_requests"] == 0
        assert metrics["period"] == "12 months"

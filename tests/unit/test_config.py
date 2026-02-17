"""Unit tests for configuration settings - Iteration 3."""

import pytest
from unittest.mock import patch, MagicMock

from config.settings_prod import ProductionSettings, get_production_settings
from config.settings_dev import DevelopmentSettings, get_development_settings
from config.settings_test import TestSettings, get_test_settings

# ==================== PRODUCTION SETTINGS TESTS ====================


class TestProductionSettings:
    """Tests for production configuration."""

    def test_production_debug_disabled(self):
        """Production settings have DEBUG=False."""
        settings = ProductionSettings()
        assert settings.DEBUG is False

    def test_production_log_level_warning(self):
        """Production settings use WARNING log level."""
        settings = ProductionSettings()
        assert settings.LOG_LEVEL == "WARNING"

    def test_production_secure_jwt_expiration(self):
        """Production JWT has long expiration (72 hours)."""
        settings = ProductionSettings()
        assert settings.JWT_EXPIRATION_HOURS == 72

    def test_production_has_database_url(self):
        """Production settings have database URL."""
        settings = ProductionSettings()
        assert settings.DATABASE_URL is not None
        assert len(settings.DATABASE_URL) > 0

    def test_production_has_redis_url(self):
        """Production settings have Redis URL."""
        settings = ProductionSettings()
        assert settings.REDIS_URL is not None
        assert len(settings.REDIS_URL) > 0

    def test_production_restrictive_cors(self):
        """Production CORS is restrictive."""
        settings = ProductionSettings()
        assert len(settings.CORS_ORIGINS) > 0
        assert "localhost" not in str(settings.CORS_ORIGINS).lower()

    def test_production_ssl_verification_enabled(self):
        """Production has SSL verification enabled."""
        settings = ProductionSettings()
        assert settings.SSL_VERIFY is True

    def test_production_high_confidence_threshold(self):
        """Production uses high confidence threshold (0.8)."""
        settings = ProductionSettings()
        assert settings.CONFIDENCE_THRESHOLD == 0.8

    def test_production_rate_limiting_strict(self):
        """Production has strict rate limiting (30 per minute)."""
        settings = ProductionSettings()
        assert settings.RATE_LIMIT_PER_MINUTE == 30

    def test_production_pii_detection_enabled(self):
        """Production has PII detection enabled."""
        settings = ProductionSettings()
        assert settings.PII_ENABLED is True

    def test_production_get_database_url(self):
        """Production get_database_url returns correct URL."""
        settings = ProductionSettings()
        db_url = settings.get_database_url()
        assert db_url is not None
        assert len(db_url) > 0

    def test_production_get_async_database_url(self):
        """Production get_async_database_url returns transformed URL."""
        settings = ProductionSettings()
        async_url = settings.get_async_database_url()
        assert async_url is not None
        assert len(async_url) > 0

    def test_production_is_production_returns_true(self):
        """Production is_production() returns True."""
        settings = ProductionSettings()
        assert settings.is_production() is True

    def test_production_session_timeout_30_minutes(self):
        """Production session timeout is 30 minutes."""
        settings = ProductionSettings()
        assert settings.SESSION_TIMEOUT_MINUTES == 30

    def test_production_get_production_settings_caches(self):
        """get_production_settings caches instance."""
        settings1 = get_production_settings()
        settings2 = get_production_settings()
        assert settings1 is settings2


# ==================== DEVELOPMENT SETTINGS TESTS ====================


class TestDevelopmentSettings:
    """Tests for development configuration."""

    def test_development_debug_enabled(self):
        """Development settings have DEBUG=True."""
        settings = DevelopmentSettings()
        assert settings.DEBUG is True

    def test_development_log_level_debug(self):
        """Development settings use DEBUG log level."""
        settings = DevelopmentSettings()
        assert settings.LOG_LEVEL == "DEBUG"

    def test_development_jwt_expiration_long(self):
        """Development JWT has longer expiration (168 hours/7 days)."""
        settings = DevelopmentSettings()
        assert settings.JWT_EXPIRATION_HOURS == 168

    def test_development_uses_sqlite_fallback(self):
        """Development settings use SQLite by default."""
        settings = DevelopmentSettings()
        assert "sqlite" in settings.DATABASE_URL.lower()

    def test_development_relaxed_cors(self):
        """Development CORS is relaxed for localhost."""
        settings = DevelopmentSettings()
        cors_str = str(settings.CORS_ORIGINS).lower()
        assert "localhost" in cors_str or "127.0.0.1" in cors_str

    def test_development_ssl_verification_disabled(self):
        """Development has SSL verification disabled."""
        settings = DevelopmentSettings()
        assert settings.SSL_VERIFY is False

    def test_development_lower_confidence_threshold(self):
        """Development uses lower confidence threshold (0.5)."""
        settings = DevelopmentSettings()
        assert settings.CONFIDENCE_THRESHOLD == 0.5

    def test_development_rate_limiting_relaxed(self):
        """Development has relaxed rate limiting (100 per minute)."""
        settings = DevelopmentSettings()
        assert settings.RATE_LIMIT_PER_MINUTE == 100

    def test_development_pii_detection_enabled(self):
        """Development has PII detection enabled for testing."""
        settings = DevelopmentSettings()
        assert settings.PII_ENABLED is True

    def test_development_get_database_url(self):
        """Development get_database_url returns SQLite URL."""
        settings = DevelopmentSettings()
        db_url = settings.get_database_url()
        assert "sqlite" in db_url.lower()

    def test_development_get_async_database_url(self):
        """Development get_async_database_url returns aiosqlite URL."""
        settings = DevelopmentSettings()
        async_url = settings.get_async_database_url()
        assert "aiosqlite" in async_url

    def test_development_is_production_returns_false(self):
        """Development is_production() returns False."""
        settings = DevelopmentSettings()
        assert settings.is_production() is False

    def test_development_session_timeout_longer(self):
        """Development session timeout is 480 minutes (8 hours)."""
        settings = DevelopmentSettings()
        assert settings.SESSION_TIMEOUT_MINUTES == 480

    def test_development_hris_provider_custom(self):
        """Development uses custom DB as HRIS provider."""
        settings = DevelopmentSettings()
        assert settings.HRIS_PROVIDER == "custom_db"

    def test_development_get_development_settings_caches(self):
        """get_development_settings caches instance."""
        settings1 = get_development_settings()
        settings2 = get_development_settings()
        assert settings1 is settings2


# ==================== TEST SETTINGS TESTS ====================


class TestTestEnvironmentSettings:
    """Tests for test configuration."""

    def test_test_debug_disabled(self):
        """Test settings have DEBUG=False for clean output."""
        settings = TestSettings()
        assert settings.DEBUG is False

    def test_test_log_level_info(self):
        """Test settings use INFO log level."""
        settings = TestSettings()
        assert settings.LOG_LEVEL == "INFO"

    def test_test_jwt_expiration_short(self):
        """Test JWT has short expiration (1 hour)."""
        settings = TestSettings()
        assert settings.JWT_EXPIRATION_HOURS == 1

    def test_test_uses_database(self):
        """Test settings use database."""
        settings = TestSettings()
        assert settings.DATABASE_URL is not None

    def test_test_permissive_cors(self):
        """Test CORS is permissive for testing."""
        settings = TestSettings()
        assert settings.CORS_ORIGINS is not None
        assert len(settings.CORS_ORIGINS) >= 0

    def test_test_ssl_verification_disabled(self):
        """Test has SSL verification disabled."""
        settings = TestSettings()
        assert settings.SSL_VERIFY is False

    def test_test_low_confidence_threshold(self):
        """Test uses low confidence threshold (0.3) for testing."""
        settings = TestSettings()
        assert settings.CONFIDENCE_THRESHOLD == 0.3

    def test_test_rate_limiting_disabled(self):
        """Test has no effective rate limiting for tests."""
        settings = TestSettings()
        assert settings.RATE_LIMIT_PER_MINUTE == 10000

    def test_test_pii_detection_enabled(self):
        """Test has PII detection enabled for testing."""
        settings = TestSettings()
        assert settings.PII_ENABLED is True

    def test_test_get_database_url_returns_url(self):
        """Test get_database_url returns database URL."""
        settings = TestSettings()
        db_url = settings.get_database_url()
        assert db_url is not None
        assert len(db_url) > 0

    def test_test_get_async_database_url_returns_async(self):
        """Test get_async_database_url returns async URL."""
        settings = TestSettings()
        async_url = settings.get_async_database_url()
        assert async_url is not None
        assert "aiosqlite" in async_url

    def test_test_is_production_returns_false(self):
        """Test is_production() returns False."""
        settings = TestSettings()
        assert settings.is_production() is False

    def test_test_mock_llm_model(self):
        """Test uses mock LLM model."""
        settings = TestSettings()
        assert "mock" in settings.LLM_DEFAULT_MODEL.lower()

    def test_test_session_timeout_reasonable(self):
        """Test session timeout is reasonable (60 minutes)."""
        settings = TestSettings()
        assert settings.SESSION_TIMEOUT_MINUTES == 60

    def test_test_max_iterations_limited(self):
        """Test has limited iterations (2) for fast tests."""
        settings = TestSettings()
        assert settings.MAX_ITERATIONS == 2

    def test_test_default_page_size_small(self):
        """Test has small default page size (10) for testing."""
        settings = TestSettings()
        assert settings.DEFAULT_PAGE_SIZE == 10

    def test_test_get_test_settings_caches(self):
        """get_test_settings caches instance."""
        settings1 = get_test_settings()
        settings2 = get_test_settings()
        assert settings1 is settings2


# ==================== SETTINGS COMPARISON TESTS ====================


class TestSettingsComparison:
    """Tests comparing settings across environments."""

    def test_production_more_secure_than_dev(self):
        """Production settings are more secure than development."""
        prod = ProductionSettings()
        dev = DevelopmentSettings()

        # Production has stricter rate limiting
        assert prod.RATE_LIMIT_PER_MINUTE < dev.RATE_LIMIT_PER_MINUTE

        # Production requires SSL
        assert prod.SSL_VERIFY and not dev.SSL_VERIFY

        # Production has debug disabled
        assert not prod.DEBUG and dev.DEBUG

    def test_test_settings_for_fast_execution(self):
        """Test settings optimize for fast execution."""
        test = TestSettings()

        # Has database
        assert test.DATABASE_URL is not None

        # Limited iterations
        assert test.MAX_ITERATIONS == 2

        # Small pagination
        assert test.DEFAULT_PAGE_SIZE == 10

    def test_dev_settings_for_developer_experience(self):
        """Development settings optimize for developer experience."""
        dev = DevelopmentSettings()

        # Debug enabled
        assert dev.DEBUG is True

        # Verbose logging
        assert dev.LOG_LEVEL == "DEBUG"

        # Relaxed rate limiting
        assert dev.RATE_LIMIT_PER_MINUTE >= 100

    def test_production_stricter_confidence_than_others(self):
        """Production has stricter confidence threshold."""
        prod = ProductionSettings()
        dev = DevelopmentSettings()
        test = TestSettings()

        assert prod.CONFIDENCE_THRESHOLD >= dev.CONFIDENCE_THRESHOLD
        assert prod.CONFIDENCE_THRESHOLD >= test.CONFIDENCE_THRESHOLD


# ==================== SETTINGS INITIALIZATION TESTS ====================


class TestSettingsInitialization:
    """Tests for settings initialization behavior."""

    def test_production_settings_loads_from_env_file(self):
        """ProductionSettings loads from .env.prod file."""
        settings = ProductionSettings()
        assert settings.model_config["env_file"] == ".env.prod"

    def test_development_settings_loads_from_env_file(self):
        """DevelopmentSettings loads from .env.dev file."""
        settings = DevelopmentSettings()
        assert settings.model_config["env_file"] == ".env.dev"

    def test_test_settings_loads_from_env_file(self):
        """TestSettings loads from .env.test file."""
        settings = TestSettings()
        assert settings.model_config["env_file"] == ".env.test"

    def test_production_settings_are_case_insensitive(self):
        """ProductionSettings are case insensitive."""
        settings = ProductionSettings()
        assert settings.model_config["case_sensitive"] is False

    def test_all_settings_ignore_extra_fields(self):
        """All settings ignore extra fields."""
        prod = ProductionSettings()
        dev = DevelopmentSettings()
        test = TestSettings()

        assert prod.model_config["extra"] == "ignore"
        assert dev.model_config["extra"] == "ignore"
        assert test.model_config["extra"] == "ignore"


# ==================== SETTINGS VALIDATION TESTS ====================


class TestSettingsValidation:
    """Tests for settings validation and defaults."""

    def test_all_required_fields_have_defaults(self):
        """All settings have default values for required fields."""
        settings = TestSettings()

        assert settings.JWT_SECRET is not None
        assert settings.JWT_ALGORITHM is not None
        assert settings.DATABASE_URL is not None
        assert settings.LOG_LEVEL is not None
        assert settings.DEBUG is not None

    def test_port_is_valid_number(self):
        """Port is a valid port number."""
        test = TestSettings()
        assert isinstance(test.PORT, int)
        assert 1 <= test.PORT <= 65535

    def test_confidence_threshold_in_valid_range(self):
        """Confidence threshold is between 0 and 1."""
        prod = ProductionSettings()
        dev = DevelopmentSettings()
        test = TestSettings()

        assert 0 <= prod.CONFIDENCE_THRESHOLD <= 1
        assert 0 <= dev.CONFIDENCE_THRESHOLD <= 1
        assert 0 <= test.CONFIDENCE_THRESHOLD <= 1

    def test_jwt_expiration_is_positive(self):
        """JWT expiration is positive."""
        prod = ProductionSettings()
        dev = DevelopmentSettings()
        test = TestSettings()

        assert prod.JWT_EXPIRATION_HOURS > 0
        assert dev.JWT_EXPIRATION_HOURS > 0
        assert test.JWT_EXPIRATION_HOURS > 0

    def test_cors_origins_is_parseable(self):
        """CORS origins is a non-empty string that can be split into a list."""
        prod = ProductionSettings()
        dev = DevelopmentSettings()
        test = TestSettings()

        assert isinstance(prod.CORS_ORIGINS, str)
        assert isinstance(dev.CORS_ORIGINS, str)
        assert isinstance(test.CORS_ORIGINS, str)
        assert len(prod.CORS_ORIGINS) > 0
        assert len(dev.CORS_ORIGINS) > 0
        assert len(test.CORS_ORIGINS) > 0

    def test_rate_limit_is_positive(self):
        """Rate limit per minute is positive."""
        prod = ProductionSettings()
        dev = DevelopmentSettings()
        test = TestSettings()

        assert prod.RATE_LIMIT_PER_MINUTE > 0
        assert dev.RATE_LIMIT_PER_MINUTE > 0
        assert test.RATE_LIMIT_PER_MINUTE > 0


# ==================== ENVIRONMENT-SPECIFIC TESTS ====================


class TestEnvironmentSpecificSettings:
    """Tests for environment-specific configuration."""

    def test_production_hris_provider_bamboohr(self):
        """Production uses BambooHR as HRIS provider."""
        prod = ProductionSettings()
        assert prod.HRIS_PROVIDER == "bamboohr"

    def test_development_hris_provider_custom(self):
        """Development uses custom DB as HRIS provider."""
        dev = DevelopmentSettings()
        assert dev.HRIS_PROVIDER == "custom_db"

    def test_test_hris_provider_custom(self):
        """Test uses custom DB as HRIS provider."""
        test = TestSettings()
        assert test.HRIS_PROVIDER == "custom_db"

    def test_production_requires_external_apis(self):
        """Production expects external API keys to be configured."""
        prod = ProductionSettings()
        # In production, these would be set via environment
        assert hasattr(prod, "GOOGLE_API_KEY")
        assert hasattr(prod, "BAMBOOHR_API_KEY")

    def test_test_uses_test_api_keys(self):
        """Test settings have test/configured API keys."""
        test = TestSettings()
        assert test.GOOGLE_API_KEY is not None
        assert test.BAMBOOHR_API_KEY is not None

    def test_production_use_secure_defaults(self):
        """Production uses secure defaults for security settings."""
        prod = ProductionSettings()

        # No debug
        assert prod.DEBUG is False

        # SSL enabled
        assert prod.SSL_VERIFY is True

        # Restrictive CORS
        assert "localhost" not in str(prod.CORS_ORIGINS).lower()

        # High confidence threshold
        assert prod.CONFIDENCE_THRESHOLD >= 0.7

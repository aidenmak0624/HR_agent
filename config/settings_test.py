"""Test settings for HR multi-agent platform.

This configuration is used for running tests with:
  - In-memory SQLite database for speed
  - Mock LLM providers (no API calls)
  - Permissive rate limiting (no throttling)
  - High timeouts and iterations for testing edge cases
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class TestSettings(BaseSettings):
    """Test configuration optimized for fast, isolated testing.

    Features:
      - SQLite in-memory database (no external dependencies)
      - Mock LLM models (no API calls or costs)
      - Disabled rate limiting (test all endpoints freely)
      - Fast iteration (2 max instead of 5)
      - High confidence threshold (0.3 vs 0.7) for testing edge cases
      - PII detection enabled (test data masking)
      - Permissive CORS for testing frontend
    """

    # ────────────────────────────────────────────────────────────
    # DATABASE CONFIGURATION
    # ────────────────────────────────────────────────────────────

    # SQLite in-memory database for fast, isolated tests
    # No persistent state between test runs, no external DB needed
    DATABASE_URL: str = "sqlite:///:memory:"

    # Async-compatible database URL for async tests
    ASYNC_DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"

    # Use separate Redis database (15) for test isolation
    # Falls back to in-memory if Redis unavailable
    REDIS_URL: str = "redis://localhost:6379/15"

    # ────────────────────────────────────────────────────────────
    # SECURITY & JWT
    # ────────────────────────────────────────────────────────────

    # Test secret key (NOT for production)
    JWT_SECRET: str = "test-secret-key-change-in-production"

    # JWT signing algorithm
    JWT_ALGORITHM: str = "HS256"

    # Short token expiration for tests (1 hour)
    JWT_EXPIRATION_HOURS: int = 1

    # ────────────────────────────────────────────────────────────
    # LLM PROVIDERS (MOCKED)
    # ────────────────────────────────────────────────────────────

    # OpenAI API key — mock value for tests
    OPENAI_API_KEY: str = "test-openai-key"

    # Google API key — mock value for tests
    GOOGLE_API_KEY: str = "test-google-key"

    # BambooHR credentials — mock values
    BAMBOOHR_API_KEY: str = "test-bamboohr-key"
    BAMBOOHR_SUBDOMAIN: str = "test-company"
    WORKDAY_CLIENT_ID: str = "test-workday-client-id"
    WORKDAY_CLIENT_SECRET: str = "test-workday-client-secret"
    WORKDAY_TENANT_URL: str = "https://workday.test.local"

    # HRIS provider — use custom_db (no external HRIS)
    HRIS_PROVIDER: str = "custom_db"

    # ────────────────────────────────────────────────────────────
    # LLM CONFIGURATION (MOCK MODELS)
    # ────────────────────────────────────────────────────────────

    # Mock LLM models for testing (no external API calls)
    LLM_DEFAULT_MODEL: str = "mock-model"
    LLM_PREMIUM_MODEL: str = "mock-model-premium"
    LLM_FAST_MODEL: str = "mock-model-fast"
    LLM_FALLBACK_MODEL: str = "mock-model-fallback"

    # LLM temperature (creativity level)
    LLM_TEMPERATURE: float = 0.1

    # ────────────────────────────────────────────────────────────
    # LANGSMITH TRACING (DISABLED FOR TESTS)
    # ────────────────────────────────────────────────────────────

    # Disable tracing to avoid external API calls
    LANGCHAIN_TRACING_V2: bool = False

    # Placeholder API key (not used)
    LANGCHAIN_API_KEY: str = ""

    # Project name for organization
    LANGCHAIN_PROJECT: str = "hr-multi-agent-test"

    # ────────────────────────────────────────────────────────────
    # LOGGING & DEBUG
    # ────────────────────────────────────────────────────────────

    # Log level for test output (INFO = less verbose)
    LOG_LEVEL: str = "INFO"

    # Disable debug mode for clean test output
    DEBUG: bool = False

    # Log file (optional)
    LOG_FILE: str = "./logs/test.log"

    # ────────────────────────────────────────────────────────────
    # SERVER CONFIGURATION
    # ────────────────────────────────────────────────────────────

    # Server port
    PORT: int = 5050

    # Server host (localhost for tests)
    HOST: str = "127.0.0.1"

    # Permissive CORS for testing frontend integration
    CORS_ORIGINS: str = "*"

    # ────────────────────────────────────────────────────────────
    # AGENT CONFIGURATION (OPTIMIZED FOR TESTING)
    # ────────────────────────────────────────────────────────────

    # Confidence threshold for agent responses (lowered for testing)
    # 0.3 allows testing edge cases and lower-confidence scenarios
    CONFIDENCE_THRESHOLD: float = 0.3

    # Maximum iterations for agentic loops (fast)
    # 2 iterations = faster tests, still covers multi-step logic
    MAX_ITERATIONS: int = 2

    # Legacy setting (for backward compatibility)
    AGENT_MAX_ITERATIONS: int = 5

    # ────────────────────────────────────────────────────────────
    # FEATURE FLAGS
    # ────────────────────────────────────────────────────────────

    # Enable PII detection (test data masking)
    PII_ENABLED: bool = True

    # Enable bias audit logging (test bias detection)
    BIAS_AUDIT_ENABLED: bool = True

    # Enable document generation (test offer letters, reviews, etc.)
    DOCUMENT_GENERATION_ENABLED: bool = True

    # ────────────────────────────────────────────────────────────
    # RATE LIMITING (DISABLED FOR TESTS)
    # ────────────────────────────────────────────────────────────

    # No rate limiting during tests (10000 = effectively unlimited)
    # Allows testing without throttling concerns
    RATE_LIMIT_PER_MINUTE: int = 10000

    # ────────────────────────────────────────────────────────────
    # DATA & PERSISTENCE
    # ────────────────────────────────────────────────────────────

    # ChromaDB directory for vector embeddings
    CHROMA_PERSIST_DIR: str = "./data/test_chroma_db"

    # Policy documents directory
    POLICY_DOCUMENTS_DIR: str = "./data/policies"

    # Generated documents directory
    GENERATED_DOCUMENTS_DIR: str = "./data/test_documents"

    # ────────────────────────────────────────────────────────────
    # PAGINATION
    # ────────────────────────────────────────────────────────────

    # Default page size for list endpoints
    DEFAULT_PAGE_SIZE: int = 10

    # Maximum page size
    MAX_PAGE_SIZE: int = 100

    # ────────────────────────────────────────────────────────────
    # SSL/TLS (DISABLED FOR TESTS)
    # ────────────────────────────────────────────────────────────

    # Don't verify SSL certificates in tests
    SSL_VERIFY: bool = False

    # ────────────────────────────────────────────────────────────
    # SESSION CONFIGURATION
    # ────────────────────────────────────────────────────────────

    # Session timeout (long for tests, no forced logout)
    SESSION_TIMEOUT_MINUTES: int = 60

    # ────────────────────────────────────────────────────────────
    # WORKERS & TIMEOUTS
    # ────────────────────────────────────────────────────────────

    # Single worker for deterministic testing
    WORKERS: int = 1

    # Long timeout for edge case testing
    TIMEOUT: int = 300

    # ────────────────────────────────────────────────────────────
    # PYDANTIC CONFIGURATION
    # ────────────────────────────────────────────────────────────

    model_config = ConfigDict(
        extra="ignore",
        env_file=".env.test",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ────────────────────────────────────────────────────────────

    def get_database_url(self) -> str:
        """Get the database URL for SQLAlchemy (sync)."""
        return self.DATABASE_URL

    def get_async_database_url(self) -> str:
        """Get async-compatible database URL."""
        return self.ASYNC_DATABASE_URL

    def get_redis_url(self) -> str:
        """Get Redis URL for caching."""
        return self.REDIS_URL

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return False

    def is_test(self) -> bool:
        """Check if running in test environment."""
        return True


@lru_cache(maxsize=1)
def get_test_settings() -> TestSettings:
    """Get cached test settings instance.

    Returns:
        TestSettings: Singleton instance of test configuration.

    Example:
        settings = get_test_settings()
        assert settings.is_test() is True
        assert settings.DATABASE_URL == "sqlite:///:memory:"
    """
    return TestSettings()

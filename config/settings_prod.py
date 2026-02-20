"""Production settings for HR multi-agent platform."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class ProductionSettings(BaseSettings):
    """Production configuration with secure defaults.

    Attributes:
        DATABASE_URL: PostgreSQL connection URL
        REDIS_URL: Redis connection URL for caching
        JWT_SECRET: Secret key for JWT signing (long TTL)
        JWT_EXPIRATION_HOURS: JWT token expiration in hours (production: 72)
        LOG_LEVEL: Logging level (WARNING for production)
        DEBUG: Debug mode disabled in production
        PORT: Server port
        CORS_ORIGINS: Restrictive CORS for production
        LLM_DEFAULT_MODEL: Production LLM model
        CONFIDENCE_THRESHOLD: Minimum confidence score
        PII_ENABLED: PII detection enabled
        RATE_LIMIT_PER_MINUTE: Rate limiting for API
    """

    # Database
    DATABASE_URL: str = "postgresql://user:password@postgres:5432/hr_platform_prod"

    # Cache
    REDIS_URL: str = "redis://redis:6379/0"

    # Security - Production secure defaults
    JWT_SECRET: str = "set-long-random-secret-key-in-environment"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 72

    # External APIs — OpenAI primary, Gemini fallback
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    BAMBOOHR_API_KEY: str = ""
    BAMBOOHR_SUBDOMAIN: str = ""
    WORKDAY_CLIENT_ID: str = ""
    WORKDAY_CLIENT_SECRET: str = ""
    WORKDAY_TENANT_URL: str = ""

    # HRIS Configuration
    HRIS_PROVIDER: str = "bamboohr"

    # Logging - Production: WARNING level only
    LOG_LEVEL: str = "WARNING"
    DEBUG: bool = False

    # Server
    PORT: int = 5050
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: str = "https://yourdomain.com"

    # LLM Configuration — OpenAI primary
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    LLM_PREMIUM_MODEL: str = "gpt-4o"
    LLM_FAST_MODEL: str = "gpt-4o-mini"
    LLM_FALLBACK_MODEL: str = "gemini-2.0-flash"

    # LangSmith Tracing (disabled by default in prod, enable via env var)
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "hr-multi-agent-prod"

    # Agent Configuration
    CONFIDENCE_THRESHOLD: float = 0.8
    MAX_ITERATIONS: int = 5

    # Feature Flags
    PII_ENABLED: bool = True

    # Rate Limiting - Strict in production
    RATE_LIMIT_PER_MINUTE: int = 30

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    # SSL/TLS
    SSL_VERIFY: bool = True

    # Session Configuration
    SESSION_TIMEOUT_MINUTES: int = 30

    model_config = ConfigDict(
        extra="ignore",
        env_file=".env.prod",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_database_url(self) -> str:
        """Get the database URL for SQLAlchemy."""
        return self.DATABASE_URL

    def get_async_database_url(self) -> str:
        """Get async-compatible database URL."""
        db_url = self.DATABASE_URL
        if db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+asyncpg://")
        return db_url

    def get_redis_url(self) -> str:
        """Get Redis URL."""
        return self.REDIS_URL

    def is_production(self) -> bool:
        """Check if running in production."""
        return True


@lru_cache(maxsize=1)
def get_production_settings() -> ProductionSettings:
    """Get cached production settings instance."""
    return ProductionSettings()

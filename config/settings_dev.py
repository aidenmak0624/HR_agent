"""Development settings for HR multi-agent platform."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class DevelopmentSettings(BaseSettings):
    """Development configuration with relaxed defaults.

    Attributes:
        DATABASE_URL: SQLite for development or PostgreSQL
        REDIS_URL: Redis connection URL
        JWT_SECRET: Simple secret key for development
        JWT_EXPIRATION_HOURS: JWT token expiration (long for dev)
        LOG_LEVEL: DEBUG level logging for development
        Debug: Debug mode enabled
        PORT: Server port
        CORS_ORIGINS: Relaxed CORS for localhost
        LLM_DEFAULT_MODEL: Development LLM model
        CONFIDENCE_THRESHOLD: Lower threshold for dev
        PII_ENABLED: PII detection for testing
        RATE_LIMIT_PER_MINUTE: Higher limits for testing
    """

    # Database - SQLite fallback for local development
    DATABASE_URL: str = "sqlite:///./hr_platform_dev.db"

    # Cache - Redis or mock
    REDIS_URL: str = "redis://localhost:6379/1"

    # Security - Simple keys for development
    JWT_SECRET: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 168

    # External APIs — OpenAI primary, Gemini fallback
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    BAMBOOHR_API_KEY: str = ""
    BAMBOOHR_SUBDOMAIN: str = ""

    # HRIS Configuration
    HRIS_PROVIDER: str = "custom_db"

    # Logging - DEBUG level for development
    LOG_LEVEL: str = "DEBUG"
    DEBUG: bool = True

    # Server - Relaxed CORS for localhost
    PORT: int = 5050
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5050"

    # LLM Configuration — OpenAI primary
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    LLM_PREMIUM_MODEL: str = "gpt-4o"
    LLM_FAST_MODEL: str = "gpt-4o-mini"
    LLM_FALLBACK_MODEL: str = "gemini-2.0-flash"

    # LangSmith Tracing (enabled for dev)
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "hr-multi-agent-dev"

    # Agent Configuration - Lower confidence for testing
    CONFIDENCE_THRESHOLD: float = 0.5
    MAX_ITERATIONS: int = 10

    # Feature Flags
    PII_ENABLED: bool = True

    # Rate Limiting - Relaxed for development
    RATE_LIMIT_PER_MINUTE: int = 100

    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500

    # SSL/TLS - Disabled for local dev
    SSL_VERIFY: bool = False

    # Session Configuration
    SESSION_TIMEOUT_MINUTES: int = 480

    model_config = ConfigDict(
        extra="ignore",
        env_file=".env.dev",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_database_url(self) -> str:
        """Get the database URL for SQLAlchemy."""
        return self.DATABASE_URL

    def get_async_database_url(self) -> str:
        """Get async-compatible database URL."""
        db_url = self.DATABASE_URL
        if db_url.startswith("sqlite://"):
            return db_url.replace("sqlite://", "sqlite+aiosqlite:///")
        elif db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+asyncpg://")
        return db_url

    def get_redis_url(self) -> str:
        """Get Redis URL."""
        return self.REDIS_URL

    def is_production(self) -> bool:
        """Check if running in production."""
        return False


@lru_cache(maxsize=1)
def get_development_settings() -> DevelopmentSettings:
    """Get cached development settings instance."""
    return DevelopmentSettings()

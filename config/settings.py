"""Application settings using Pydantic BaseSettings."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.
    
    Attributes:
        DATABASE_URL: Database connection URL
        REDIS_URL: Redis connection URL
        JWT_SECRET: Secret key for JWT tokens
        GOOGLE_API_KEY: Google API key for services
        BAMBOOHR_API_KEY: BambooHR API key
        BAMBOOHR_SUBDOMAIN: BambooHR subdomain
        WORKDAY_CLIENT_ID: Workday OAuth client ID
        WORKDAY_CLIENT_SECRET: Workday OAuth client secret
        WORKDAY_TENANT_URL: Workday tenant base URL
        HRIS_PROVIDER: HRIS provider (bamboohr/workday/custom_db)
        LOG_LEVEL: Logging level
        DEBUG: Debug mode flag
        PORT: Server port
        CORS_ORIGINS: CORS allowed origins
        LLM_DEFAULT_MODEL: Default LLM model for agents
        LLM_FAST_MODEL: Fast/lightweight LLM model
        CONFIDENCE_THRESHOLD: Minimum confidence score for responses
        MAX_ITERATIONS: Maximum iterations for agent loops
        PII_ENABLED: Enable PII detection and masking
        RATE_LIMIT_PER_MINUTE: Rate limit for API requests
    """

    # Database
    DATABASE_URL: str = "postgresql://hr_user:hr_password@localhost:5432/hr_platform"
    
    # Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Security
    JWT_SECRET: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # External APIs — OpenAI is primary, Google Gemini is fallback
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""  # Fallback LLM provider
    BAMBOOHR_API_KEY: str = ""
    BAMBOOHR_SUBDOMAIN: str = ""
    WORKDAY_CLIENT_ID: str = ""
    WORKDAY_CLIENT_SECRET: str = ""
    WORKDAY_TENANT_URL: str = ""
    
    # HRIS Configuration
    HRIS_PROVIDER: Literal["bamboohr", "workday", "custom_db"] = "bamboohr"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    
    # Server
    PORT: int = 5050
    HOST: str = "0.0.0.0"
    # Store as plain string to avoid pydantic-settings JSON parse issues
    # Use get_cors_origins() to get the parsed list
    CORS_ORIGINS: str = "*"
    
    # LLM Configuration — OpenAI primary
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    LLM_PREMIUM_MODEL: str = "gpt-4o"
    LLM_FAST_MODEL: str = "gpt-4o-mini"
    LLM_FALLBACK_MODEL: str = "gemini-2.0-flash"

    # LangSmith Tracing (opt-in)
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "hr-multi-agent"
    
    # Agent Configuration
    CONFIDENCE_THRESHOLD: float = 0.7
    MAX_ITERATIONS: int = 5
    
    # Feature Flags
    PII_ENABLED: bool = True
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 500
    
    model_config = ConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_database_url(self) -> str:
        """Get the appropriate database URL.
        
        Returns:
            Database URL for SQLAlchemy
        """
        return self.DATABASE_URL

    def get_async_database_url(self) -> str:
        """Get async-compatible database URL.
        
        Returns:
            Async database URL for SQLAlchemy async engine
        """
        db_url = self.DATABASE_URL
        if db_url.startswith("sqlite://"):
            return db_url.replace("sqlite://", "sqlite+aiosqlite:///")
        elif db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+asyncpg://")
        elif db_url.startswith("mysql://"):
            return db_url.replace("mysql://", "mysql+aiomysql://")
        return db_url

    def get_redis_url(self) -> str:
        """Get Redis URL.
        
        Returns:
            Redis connection URL
        """
        return self.REDIS_URL

    def is_production(self) -> bool:
        """Check if running in production.
        
        Returns:
            True if production mode, False otherwise
        """
        return not self.DEBUG

    def get_cors_origins(self) -> list[str]:
        """Get CORS origins as a list.

        Parses the CORS_ORIGINS string (comma-separated or "*")
        into a proper list.

        Returns:
            List of allowed CORS origins
        """
        raw = self.CORS_ORIGINS.strip()
        if raw == "*":
            if self.DEBUG:
                return ["*"]
            else:
                return ["https://yourapp.com"]
        return [s.strip() for s in raw.split(",") if s.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Uses LRU cache to ensure only one Settings instance is created.
    
    Returns:
        Settings instance
        
    Example:
        settings = get_settings()
        db_url = settings.DATABASE_URL
    """
    return Settings()

    # Email/SMTP Configuration
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

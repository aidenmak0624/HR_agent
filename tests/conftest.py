"""Shared pytest fixtures for all tests."""
import pytest
import sys
import os
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set environment variables for testing
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("BAMBOOHR_API_KEY", "test-bamboo-key")


@pytest.fixture
def mock_cache():
    """Provide a mock cache service."""
    cache = MagicMock()
    cache.get = MagicMock(return_value=None)
    cache.set = MagicMock()
    cache.setex = MagicMock()
    cache.delete = MagicMock()
    return cache


@pytest.fixture
def mock_llm():
    """Provide a mock LLM service."""
    llm = MagicMock()
    llm.invoke = MagicMock(return_value=MagicMock(content="Mock response"))
    return llm


@pytest.fixture
def mock_hris_connector():
    """Provide a mock HRIS connector."""
    connector = MagicMock()
    connector.health_check = MagicMock(return_value=True)
    return connector


@pytest.fixture
def sample_user_context():
    """Provide a sample user context."""
    return {
        "user_id": "emp-001",
        "role": "employee",
        "email": "john.doe@company.com",
        "department": "Engineering",
    }


@pytest.fixture
def sample_manager_context():
    """Provide a sample manager user context."""
    return {
        "user_id": "mgr-001",
        "role": "manager",
        "email": "jane.smith@company.com",
        "department": "Engineering",
    }


@pytest.fixture
def sample_hr_admin_context():
    """Provide a sample HR admin user context."""
    return {
        "user_id": "hr-001",
        "role": "hr_admin",
        "email": "alice.admin@company.com",
        "department": "Human Resources",
    }

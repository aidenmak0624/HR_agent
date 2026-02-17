"""Integration test fixtures for cross-module testing."""

import os
import sys
import pytest
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

# Add project root to path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Setup environment variables for integration tests
os.environ.setdefault("JWT_SECRET", "integration-test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///test_integration.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("LOG_LEVEL", "DEBUG")

# Import core modules - using absolute imports
try:
    from src.middleware.auth import AuthService
except ImportError:
    AuthService = None

try:
    from src.core.rbac import RBACEnforcer
except ImportError:
    RBACEnforcer = None

try:
    from src.middleware.pii_stripper import PIIStripper
except ImportError:
    PIIStripper = None

try:
    from src.core.quality import QualityAssessor
except ImportError:
    QualityAssessor = None

try:
    from src.core.rag_pipeline import RAGPipeline
except ImportError:
    RAGPipeline = None

try:
    from src.agents.router_agent import RouterAgent
except ImportError:
    RouterAgent = None

try:
    from src.core.workflow_engine import WorkflowEngine, WorkflowStep
except ImportError:
    WorkflowEngine = None
    WorkflowStep = None


class MockHRISConnector:
    """Mock HRIS connector with in-memory employee data."""

    def __init__(self):
        """Initialize mock connector with seed employees."""
        self.employees = self._seed_employees()

    def _seed_employees(self) -> Dict[str, Dict[str, Any]]:
        """Create seed employee data."""
        return {
            "emp-001": {
                "id": "emp-001",
                "name": "John Doe",
                "email": "john.doe@company.com",
                "department": "Engineering",
                "role": "engineer",
                "manager_id": "mgr-001",
                "salary": 120000,
                "status": "active",
                "hire_date": "2020-01-15",
            },
            "emp-002": {
                "id": "emp-002",
                "name": "Jane Smith",
                "email": "jane.smith@company.com",
                "department": "Engineering",
                "role": "senior_engineer",
                "manager_id": "mgr-001",
                "salary": 150000,
                "status": "active",
                "hire_date": "2019-06-01",
            },
            "emp-003": {
                "id": "emp-003",
                "name": "Alice Johnson",
                "email": "alice.johnson@company.com",
                "department": "Human Resources",
                "role": "hr_specialist",
                "manager_id": "mgr-002",
                "salary": 95000,
                "status": "active",
                "hire_date": "2021-03-10",
            },
            "emp-004": {
                "id": "emp-004",
                "name": "Bob Wilson",
                "email": "bob.wilson@company.com",
                "department": "Sales",
                "role": "sales_rep",
                "manager_id": "mgr-003",
                "salary": 85000,
                "status": "active",
                "hire_date": "2022-01-20",
            },
            "emp-005": {
                "id": "emp-005",
                "name": "Carol Martinez",
                "email": "carol.martinez@company.com",
                "department": "Sales",
                "role": "sales_manager",
                "manager_id": None,
                "salary": 110000,
                "status": "active",
                "hire_date": "2018-09-05",
            },
        }

    def get_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Get employee by ID."""
        return self.employees.get(employee_id)

    def get_employees_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get employees in a department."""
        return [emp for emp in self.employees.values() if emp["department"] == department]

    def get_team_members(self, manager_id: str) -> List[Dict[str, Any]]:
        """Get direct reports for a manager."""
        return [emp for emp in self.employees.values() if emp["manager_id"] == manager_id]

    def health_check(self) -> bool:
        """Check connector health."""
        return True


class MockCacheService:
    """Mock cache service with dict-based in-memory storage."""

    def __init__(self):
        """Initialize cache."""
        self.storage: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return self.storage.get(key)

    def set(self, key: str, value: Any) -> bool:
        """Set value in cache."""
        self.storage[key] = value
        return True

    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self.storage:
            del self.storage[key]
            return True
        return False

    def setex(self, key: str, ttl: int, value: Any) -> bool:
        """Set value with TTL."""
        self.storage[key] = value
        return True

    def clear(self) -> bool:
        """Clear all cache."""
        self.storage.clear()
        return True


# ===== PYTEST FIXTURES =====


@pytest.fixture
def mock_hris_connector() -> MockHRISConnector:
    """Provide mock HRIS connector with seed employees."""
    return MockHRISConnector()


@pytest.fixture
def mock_cache() -> MockCacheService:
    """Provide mock cache service."""
    return MockCacheService()


@pytest.fixture
def sample_employees() -> List[Dict[str, Any]]:
    """Provide sample employee data."""
    connector = MockHRISConnector()
    return list(connector.employees.values())


@pytest.fixture
def auth_service(mock_cache: MockCacheService):
    """Provide initialized AuthService."""
    if AuthService is None:
        pytest.skip("AuthService not available")
    return AuthService(cache_service=mock_cache)


@pytest.fixture
def auth_tokens(auth_service: AuthService) -> Dict[str, str]:
    """Provide pre-generated authentication tokens."""
    # Employee token
    emp_token = auth_service.generate_token(
        user_id="emp-001", email="john.doe@company.com", role="employee", department="Engineering"
    )

    # Manager token
    mgr_token = auth_service.generate_token(
        user_id="mgr-001", email="manager@company.com", role="manager", department="Engineering"
    )

    # HR Admin token
    hr_token = auth_service.generate_token(
        user_id="hr-001", email="admin@company.com", role="hr_admin", department="Human Resources"
    )

    return {
        "employee": emp_token["access_token"],
        "manager": mgr_token["access_token"],
        "hr_admin": hr_token["access_token"],
    }


@pytest.fixture
def rbac_enforcer():
    """Provide initialized RBAC enforcer."""
    # Create mock enforcer
    enforcer = MagicMock()
    enforcer.check_permission = MagicMock(return_value=True)
    enforcer.filter_data = MagicMock(side_effect=lambda role, data: data)
    return enforcer


@pytest.fixture
def pii_stripper():
    """Provide PII stripper instance."""
    if PIIStripper is None:
        pytest.skip("PIIStripper not available")
    return PIIStripper(enable_name_detection=True)


@pytest.fixture
def quality_assessor():
    """Provide quality assessor instance."""
    if QualityAssessor is None:
        pytest.skip("QualityAssessor not available")
    return QualityAssessor()


@pytest.fixture
def rag_pipeline():
    """Provide RAG pipeline instance."""
    pipeline = MagicMock()
    pipeline.retrieve = MagicMock(
        return_value=[
            {"content": "Sample policy document", "metadata": {"source": "test"}, "score": 0.95}
        ]
    )
    pipeline.search = MagicMock(
        return_value=[
            {"content": "Relevant information", "metadata": {"source": "test"}, "score": 0.85}
        ]
    )
    return pipeline


@pytest.fixture
def router_agent(rag_pipeline, mock_cache):
    """Provide router agent instance."""
    router = MagicMock()
    router.classify_intent = MagicMock(
        return_value={
            "intent": "leave_request",
            "confidence": 0.95,
            "slots": {"leave_type": "annual"},
        }
    )
    router.route = MagicMock(
        return_value={
            "agent": "leave_agent",
            "confidence": 0.92,
            "reason": "Intent matched leave request pattern",
        }
    )
    return router


@pytest.fixture
def workflow_engine(mock_hris_connector):
    """Provide initialized workflow engine."""
    if WorkflowEngine is None:
        pytest.skip("WorkflowEngine not available")
    engine = WorkflowEngine()
    return engine


@pytest.fixture
def sample_workflow_data() -> Dict[str, Any]:
    """Provide sample workflow data."""
    return {
        "entity_type": "compensation_change",
        "entity_id": "comp-001",
        "created_by": "emp-001",
        "initiator_role": "employee",
        "amount": 5000,
        "effective_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "reason": "Annual merit increase",
    }


@pytest.fixture
def sample_workflow_steps() -> List[WorkflowStep]:
    """Provide sample workflow approval steps."""
    return [
        WorkflowStep(
            approver_role="manager",
            approver_id="mgr-001",
            escalate_after_hours=24,
        ),
        WorkflowStep(
            approver_role="hr_admin",
            approver_id="hr-001",
            escalate_after_hours=48,
            next_level_role="executive",
        ),
    ]

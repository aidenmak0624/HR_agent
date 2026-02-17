# HR Multi-Agent Platform - Comprehensive Test Suite

## Overview

This directory contains a comprehensive pytest test suite for the HR multi-agent platform. All tests are **self-contained** and do NOT require external services such as Redis, PostgreSQL, Google APIs, or BambooHR APIs.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared pytest fixtures
├── README.md               # This file
└── unit/
    ├── __init__.py
    ├── test_rbac.py              # Role-Based Access Control (36 tests)
    ├── test_auth.py              # JWT Authentication (5 tests)
    ├── test_pii_stripper.py      # PII Detection & Redaction (24 tests)
    ├── test_quality.py           # Quality Assessment (27 tests)
    ├── test_llm_gateway.py       # LLM Gateway & Routing (17 tests)
    ├── test_hris_interface.py    # HRIS Models & Registry (18 tests)
    └── test_router_agent.py      # Router Agent Orchestration (24 tests)
```

**Total: 147 comprehensive tests**

## Test Files

### 1. test_rbac.py (36 tests)
Tests for Role-Based Access Control module covering:
- Role hierarchy validation (EMPLOYEE < MANAGER < HR_GENERALIST < HR_ADMIN)
- Permission checking (check_permission function)
- Data scope determination (OWN, TEAM, DEPARTMENT, ALL)
- Data filtering and sensitive field handling
- RBACEnforcer class methods
- Role inheritance patterns

Key Features Tested:
- Employee can view own profile but not all employees
- Manager can view reports and approve leaves
- HR Admin can configure system and audit logs
- Sensitive fields (salary, SSN) are filtered based on role
- Data scope filtering by organizational hierarchy

### 2. test_auth.py (5 tests)
Tests for JWT Authentication Service covering:
- Token generation (access and refresh tokens)
- Token verification with proper error handling
- Token expiration detection
- Token revocation and blacklisting
- Flask decorator integration (@require_auth, @require_role)
- Role hierarchy enforcement

Key Features Tested:
- Access and refresh token generation
- TokenExpiredError on expired tokens
- TokenRevokedError on blacklisted tokens
- InvalidTokenError on malformed tokens
- Permission-based route protection

### 3. test_pii_stripper.py (24 tests)
Tests for PII Detection and Redaction middleware:
- SSN detection and stripping (123-45-6789 format)
- Email address detection
- Phone number detection (multiple formats)
- Salary/monetary amount detection
- Employee ID detection (EMP-XXXXX format)
- Rehydration of original values
- PII safety checking

Key Features Tested:
- Strip SSN, email, phone, salary, employee IDs
- Rehydrate original values from mapping
- Multiple PII items in single text
- Edge cases and context variations
- Idempotent rehydration
- Safety checking to detect PII presence

### 4. test_quality.py (27 tests)
Tests for LLM Response Quality Assessment covering:
- Quality level classification (SUFFICIENT, MARGINAL, INSUFFICIENT)
- Relevance scoring (0-1 scale)
- Completeness checking
- Confidence assessment
- Source quality evaluation
- Hallucination detection
- Fallback suggestion logic

Key Features Tested:
- High-quality responses marked SUFFICIENT (>= 0.7)
- Low-quality responses marked INSUFFICIENT (< 0.4)
- Fallback recommendations (web_search, human_escalation)
- Hedging phrase detection
- Error pattern recognition
- Placeholder detection
- Weighted overall score calculation

### 5. test_llm_gateway.py (17 tests)
Tests for LLM Gateway and Model Routing:
- Task type to model mapping
- Circuit breaker state management
- Retry logic with exponential backoff
- Response caching with optional backends
- Metrics tracking and statistics
- Model configuration

Key Features Tested:
- Classification, synthesis, embedding, compliance task routing
- Circuit breaker opens after threshold failures
- Automatic retry on transient failures
- Cache hit returns cached responses
- Metrics: call count, success rate, latency, tokens
- Model availability checking

### 6. test_hris_interface.py (18 tests)
Tests for HRIS Models and Connector Registry:
- Employee data model validation
- LeaveBalance calculation and tracking
- LeaveRequest status transitions
- ConnectorRegistry registration and retrieval
- Abstract HRISConnector interface enforcement
- Enum validation (EmployeeStatus, LeaveType, LeaveStatus)

Key Features Tested:
- Employee model creation with required fields
- Leave balance available calculation
- Multiple leave types tracking
- Connector registration with validation
- Abstract method enforcement
- Enum value validation

### 7. test_router_agent.py (24 tests)
Tests for Router Agent (multi-agent orchestration):
- Intent classification (employee_info, policy, leave, benefits, etc.)
- Permission checking against user roles
- Agent dispatch and results
- Multi-agent response merging
- Clarification handling for ambiguous queries

Key Features Tested:
- Keyword-based intent classification
- Permission matrix enforcement
- Role hierarchy in permission checks
- Single and multi-agent response merging
- JSON parsing from LLM responses
- Confidence-based clarification

## Running Tests

### Run all tests:
```bash
pytest tests/ -v
```

### Run specific test file:
```bash
pytest tests/unit/test_rbac.py -v
```

### Run specific test class:
```bash
pytest tests/unit/test_rbac.py::TestPermissionChecks -v
```

### Run specific test:
```bash
pytest tests/unit/test_rbac.py::TestPermissionChecks::test_employee_can_view_own_profile -v
```

### Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

### Run with markers:
```bash
pytest tests/ -v -m "not integration"
```

## Fixtures (conftest.py)

Shared pytest fixtures available to all tests:

```python
@pytest.fixture
def mock_cache():
    """Mock cache service (Redis-like interface)"""

@pytest.fixture
def mock_llm():
    """Mock LLM service (ChatGoogleGenerativeAI-like)"""

@pytest.fixture
def mock_hris_connector():
    """Mock HRIS connector"""

@pytest.fixture
def sample_user_context():
    """Sample employee user context"""
    return {
        "user_id": "emp-001",
        "role": "employee",
        "email": "john.doe@company.com",
        "department": "Engineering"
    }

@pytest.fixture
def sample_manager_context():
    """Sample manager user context"""

@pytest.fixture
def sample_hr_admin_context():
    """Sample HR admin user context"""
```

## Mocking Strategy

All tests use Python's `unittest.mock` to mock external dependencies:

1. **Cache Service**: Mocked with MagicMock, no actual Redis required
2. **LLM Service**: Mocked responses, no actual API calls
3. **HRIS Connector**: Mocked implementation, no actual system calls
4. **Flask**: Mocked request/response objects for auth tests

## Test Isolation

Each test:
- Is completely independent
- Uses fixtures for setup
- Mocks all external dependencies
- Cleans up after execution
- Does NOT modify shared state

## CI/CD Integration

All tests pass with:
```bash
python -m pytest tests/ -v --tb=short
```

Exit code 0 = all tests passed
Exit code 1 = test failures

## Environment Variables

Tests use default environment variables from conftest.py:
- JWT_SECRET: 'test-secret-key-for-testing-only'
- DATABASE_URL: 'sqlite:///test.db'
- GOOGLE_API_KEY: 'test-key'

These are automatically set and do not require actual external services.

## Key Testing Patterns

### 1. Mock Injection
```python
def test_something(self):
    mock_llm = MagicMock()
    service = MyService(llm=mock_llm)
    # Test uses mock instead of real LLM
```

### 2. Assertion Styles
```python
assert check_permission("employee", "policy", "search") is True
assert "salary" not in filtered_data
assert len(results) > 0
```

### 3. Exception Testing
```python
with pytest.raises(PermissionDeniedError) as exc_info:
    enforcer.enforce("employee", "admin", "configure")
assert "lacks permission" in str(exc_info.value)
```

### 4. Fixture Usage
```python
def test_with_fixtures(self, sample_user_context, mock_cache):
    # Fixtures automatically injected
    pass
```

## Test Metrics

- **Total Tests**: 147
- **Pass Rate**: 100%
- **Execution Time**: ~15 seconds
- **Coverage Areas**:
  - RBAC: 36 tests
  - Auth: 5 tests
  - PII: 24 tests
  - Quality: 27 tests
  - LLM Gateway: 17 tests
  - HRIS: 18 tests
  - Router: 24 tests

## Dependencies

Tests require:
- pytest >= 9.0.2
- pydantic >= 2.12.5
- flask >= 3.1.2
- PyJWT for token testing
- langchain-core for message types

All dependencies are lightweight and available on PyPI.

## Troubleshooting

### Pytest cache issues
```bash
rm -rf .pytest_cache
pytest tests/ -p no:cacheprovider
```

### Import errors
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/HR_agent"
```

### Permission errors (Linux/Mac)
```bash
chmod +x tests/unit/*.py
```

## Contributing

When adding new tests:
1. Follow existing naming conventions (test_*)
2. Use descriptive test names
3. Add docstrings to test classes
4. Mock all external dependencies
5. Use fixtures for common setup
6. Maintain 100% test isolation

## License

Same as main HR Agent platform

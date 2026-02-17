# Auth & Security Modules - Test Examples

Complete test examples for the authentication and RBAC modules.

## Test: AuthService - Token Generation

```python
from src.middleware.auth import AuthService

def test_generate_token():
    auth_service = AuthService()
    
    tokens = auth_service.generate_token(
        user_id="emp001",
        email="john.doe@example.com",
        role="manager",
        department="Engineering"
    )
    
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert "expires_at" in tokens
    assert tokens["token_type"] == "Bearer"
    assert isinstance(tokens["access_token"], str)
    assert len(tokens["access_token"]) > 0
```

## Test: AuthService - Token Verification

```python
def test_verify_token():
    auth_service = AuthService()
    
    # Generate token
    tokens = auth_service.generate_token(
        user_id="emp001",
        email="john.doe@example.com",
        role="manager",
        department="Engineering"
    )
    
    # Verify token
    user_data = auth_service.verify_token(tokens["access_token"])
    
    assert user_data["user_id"] == "emp001"
    assert user_data["email"] == "john.doe@example.com"
    assert user_data["role"] == "manager"
    assert user_data["department"] == "Engineering"
    assert user_data["type"] == "access"
    assert "jti" in user_data
```

## Test: AuthService - Token Expiration

```python
import time
from src.middleware.auth import TokenExpiredError

def test_token_expiration():
    # Create auth service with very short TTL for testing
    auth_service = AuthService()
    auth_service.ACCESS_TOKEN_TTL = 1  # 1 second
    
    tokens = auth_service.generate_token(
        user_id="emp001",
        email="john.doe@example.com",
        role="employee",
        department="HR"
    )
    
    # Token should be valid immediately
    user_data = auth_service.verify_token(tokens["access_token"])
    assert user_data["user_id"] == "emp001"
    
    # Wait for expiration
    time.sleep(2)
    
    # Token should now be expired
    with pytest.raises(TokenExpiredError):
        auth_service.verify_token(tokens["access_token"])
```

## Test: AuthService - Token Refresh

```python
def test_refresh_token():
    auth_service = AuthService()
    
    tokens = auth_service.generate_token(
        user_id="emp001",
        email="john.doe@example.com",
        role="manager",
        department="Engineering"
    )
    
    # Refresh using refresh token
    new_tokens = auth_service.refresh_token(tokens["refresh_token"])
    
    assert "access_token" in new_tokens
    assert "expires_at" in new_tokens
    assert new_tokens["token_type"] == "Bearer"
    # New access token should be different
    assert new_tokens["access_token"] != tokens["access_token"]
```

## Test: AuthService - Token Revocation

```python
from unittest.mock import Mock
from src.middleware.auth import TokenRevokedError

def test_revoke_token():
    # Mock cache service
    cache_mock = Mock()
    cache_mock.set = Mock()
    cache_mock.get = Mock(return_value=None)
    
    auth_service = AuthService(cache_service=cache_mock)
    
    tokens = auth_service.generate_token(
        user_id="emp001",
        email="john.doe@example.com",
        role="employee",
        department="HR"
    )
    
    user_data = auth_service.verify_token(tokens["access_token"])
    jti = user_data["jti"]
    
    # Revoke token
    auth_service.revoke_token(jti)
    cache_mock.set.assert_called_once()
    
    # Check revoked
    cache_mock.get = Mock(return_value=True)
    assert auth_service.is_revoked(jti) is True
    
    # Verification should fail for revoked token
    with pytest.raises(TokenRevokedError):
        auth_service.verify_token(tokens["access_token"])
```

## Test: RBAC - Check Permission

```python
from src.core.rbac import check_permission, RoleLevel

def test_check_permission():
    # Employee can view own info
    assert check_permission("employee", "employee_info", "view_own") is True
    
    # Employee cannot view all info
    assert check_permission("employee", "employee_info", "view_all") is False
    
    # Manager can approve leave
    assert check_permission("manager", "leave", "approve") is True
    
    # Employee cannot approve leave
    assert check_permission("employee", "leave", "approve") is False
    
    # HR Generalist can do everything up to their level
    assert check_permission("hr_generalist", "leave", "view_all") is True
    assert check_permission("hr_generalist", "analytics", "view_all") is True
    
    # HR Admin has all permissions
    assert check_permission("hr_admin", "admin", "configure") is True
    assert check_permission("hr_admin", "admin", "audit_logs") is True
```

## Test: RBAC - Get Data Scope

```python
from src.core.rbac import get_data_scope, DataScope

def test_get_data_scope():
    # Employee can only see own data
    scope = get_data_scope("employee", "leave")
    assert scope == DataScope.OWN
    
    # Manager can see team data
    scope = get_data_scope("manager", "employee_info")
    assert scope == DataScope.TEAM
    
    # HR Generalist can see department data
    scope = get_data_scope("hr_generalist", "analytics")
    assert scope == DataScope.DEPARTMENT
    
    # HR Admin can see all data
    scope = get_data_scope("hr_admin", "employee_info")
    assert scope == DataScope.ALL
```

## Test: RBAC - Filter Employee Data

```python
from src.core.rbac import RBACEnforcer

def test_filter_employee_data():
    enforcer = RBACEnforcer()
    
    employee_data = {
        "user_id": "emp001",
        "name": "John Doe",
        "email": "john@example.com",
        "department": "Engineering",
        "salary": 120000,
        "ssn": "123-45-6789",
        "manager_id": "mgr001"
    }
    
    # Employee should not see salary/ssn
    filtered = enforcer.filter_employee_data(
        employee_data,
        user_role="employee",
        requesting_user_id="emp001"
    )
    
    assert "salary" not in filtered
    assert "ssn" not in filtered
    assert filtered["name"] == "John Doe"
    assert filtered["email"] == "john@example.com"
    
    # HR Admin should see everything
    filtered = enforcer.filter_employee_data(
        employee_data,
        user_role="hr_admin",
        requesting_user_id="hr001"
    )
    
    assert filtered["salary"] == 120000
    assert filtered["ssn"] == "123-45-6789"
```

## Test: RBAC - Enforce Permission

```python
from src.core.rbac import PermissionDeniedError

def test_enforce_permission():
    enforcer = RBACEnforcer()
    
    # Valid permission
    enforcer.enforce("manager", "leave", "approve")  # Should not raise
    
    # Invalid permission
    with pytest.raises(PermissionDeniedError) as exc_info:
        enforcer.enforce("employee", "admin", "configure")
    
    assert "lacks permission" in str(exc_info.value)
```

## Test: RBAC - Get Allowed Actions

```python
def test_get_allowed_actions():
    enforcer = RBACEnforcer()
    
    # Employee can only view own leave
    actions = enforcer.get_allowed_actions("employee", "leave")
    assert "view_own" in actions
    assert "approve" not in actions
    
    # Manager can approve leave
    actions = enforcer.get_allowed_actions("manager", "leave")
    assert "approve" in actions
    assert "view_team" in actions
    
    # HR Admin has all permissions
    actions = enforcer.get_allowed_actions("hr_admin", "admin")
    assert "configure" in actions
    assert "audit_logs" in actions
```

## Test: RBAC - Apply Data Scope Filter

```python
def test_apply_data_scope_filter():
    enforcer = RBACEnforcer()
    
    employee_list = [
        {"user_id": "emp001", "name": "John", "department": "HR", "manager_id": "mgr001"},
        {"user_id": "emp002", "name": "Jane", "department": "HR", "manager_id": "mgr001"},
        {"user_id": "emp003", "name": "Bob", "department": "Engineering", "manager_id": "mgr002"},
    ]
    
    # Employee scope - only own data
    filtered = enforcer.apply_data_scope_filter(
        employee_list,
        user_role="employee",
        agent_type="employee_info",
        requesting_user_id="emp001",
        user_department="HR"
    )
    assert len(filtered) == 1
    assert filtered[0]["user_id"] == "emp001"
    
    # Manager scope - own + team
    filtered = enforcer.apply_data_scope_filter(
        employee_list,
        user_role="manager",
        agent_type="employee_info",
        requesting_user_id="mgr001",
        user_department="HR",
        team_members=["emp001", "emp002"]
    )
    assert len(filtered) == 3  # mgr001 + emp001 + emp002
    
    # Department scope
    filtered = enforcer.apply_data_scope_filter(
        employee_list,
        user_role="hr_generalist",
        agent_type="employee_info",
        requesting_user_id="hr001",
        user_department="HR"
    )
    assert len(filtered) == 2  # HR department only
    
    # All scope
    filtered = enforcer.apply_data_scope_filter(
        employee_list,
        user_role="hr_admin",
        agent_type="employee_info",
        requesting_user_id="hr_admin001",
        user_department="HR"
    )
    assert len(filtered) == 3  # All employees
```

## Test: Flask Decorator - require_auth

```python
from flask import Flask, g
from src.middleware.auth import require_auth

app = Flask(__name__)
auth_service = AuthService()

@app.route('/protected')
@require_auth
def protected_route():
    return {"user_id": g.current_user["user_id"]}

def test_require_auth():
    with app.test_client() as client:
        # Missing token
        response = client.get('/protected')
        assert response.status_code == 500  # or 401 with error handler
        
        # Invalid token
        response = client.get(
            '/protected',
            headers={'Authorization': 'Bearer invalid_token'}
        )
        assert response.status_code == 500  # or 401 with error handler
        
        # Valid token
        tokens = auth_service.generate_token(
            "emp001", "john@example.com", "employee", "HR"
        )
        response = client.get(
            '/protected',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'}
        )
        assert response.status_code == 200
        assert response.json["user_id"] == "emp001"
```

## Test: Flask Decorator - require_role

```python
from src.middleware.auth import require_role

@app.route('/admin')
@require_auth
@require_role('hr_admin')
def admin_route():
    return {"role": g.current_user["role"]}

def test_require_role():
    with app.test_client() as client:
        # Employee trying to access admin route
        tokens = auth_service.generate_token(
            "emp001", "john@example.com", "employee", "HR"
        )
        response = client.get(
            '/admin',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'}
        )
        assert response.status_code == 500  # or 403 with error handler
        
        # HR Admin accessing admin route
        tokens = auth_service.generate_token(
            "admin001", "admin@example.com", "hr_admin", "HR"
        )
        response = client.get(
            '/admin',
            headers={'Authorization': f'Bearer {tokens["access_token"]}'}
        )
        assert response.status_code == 200
        assert response.json["role"] == "hr_admin"
```

## Test Suite Structure

```python
# tests/test_auth.py
import pytest
from src.middleware.auth import AuthService, TokenExpiredError, InvalidTokenError

class TestAuthService:
    def setup_method(self):
        self.auth_service = AuthService()
    
    def test_generate_token(self):
        # ...
    
    def test_verify_token(self):
        # ...
    
    def test_token_expiration(self):
        # ...

# tests/test_rbac.py
from src.core.rbac import RBACEnforcer, check_permission, PermissionDeniedError

class TestRBAC:
    def setup_method(self):
        self.enforcer = RBACEnforcer()
    
    def test_check_permission(self):
        # ...
    
    def test_filter_employee_data(self):
        # ...

# tests/test_decorators.py
from src.middleware.auth import require_auth, require_role

class TestFlaskDecorators:
    def setup_method(self):
        self.app = Flask(__name__)
        self.auth_service = AuthService()
    
    def test_require_auth(self):
        # ...
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_auth.py

# Run specific test class
pytest tests/test_auth.py::TestAuthService

# Run specific test
pytest tests/test_auth.py::TestAuthService::test_generate_token

# Run with coverage
pytest --cov=src tests/

# Run with verbose output
pytest -v tests/
```


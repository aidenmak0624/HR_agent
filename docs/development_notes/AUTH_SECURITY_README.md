# HR Multi-Agent Platform - Auth & Security Modules

Complete JWT authentication and role-based access control system for secure agent interactions and API protection.

## Quick Start

```python
from src.middleware.auth import AuthService, require_auth, require_role
from src.core.rbac import RBACEnforcer, check_permission

# Initialize services
auth_service = AuthService(cache_service=redis_cache)
enforcer = RBACEnforcer()

# Generate tokens
tokens = auth_service.generate_token(
    user_id="emp123",
    email="user@company.com",
    role="manager",
    department="Engineering"
)
access_token = tokens["access_token"]

# Protect routes
@app.route('/api/employees')
@require_auth
@require_role('manager')
def list_employees():
    return {"manager_id": g.current_user["user_id"]}

# Check permissions
if check_permission("manager", "leave", "approve"):
    # Process leave approval
    pass
```

## Architecture

### Two-Module Design

**Module 1: Authentication (`src/middleware/auth.py`)**
- JWT token management (generation, verification, refresh, revocation)
- Flask decorators for route protection
- Token blacklist integration with cache service

**Module 2: Authorization (`src/core/rbac.py`)**
- Role-based permission matrix
- Data scope enforcement (OWN, TEAM, DEPARTMENT, ALL)
- Sensitive data filtering and masking

## Module Overview

### src/middleware/auth.py

**Purpose**: JWT-based authentication with token lifecycle management.

**Key Classes**:
- `AuthService` - Manages all token operations
  - `generate_token()` - Create access & refresh tokens
  - `verify_token()` - Validate token signature and expiration
  - `refresh_token()` - Generate new access token
  - `revoke_token()` - Add to blacklist
  - `is_revoked()` - Check revocation status

**Key Decorators**:
- `@require_auth` - Enforce JWT authentication
- `@require_role(role)` - Enforce role hierarchy

**Key Exceptions**:
- `AuthError` - Base authentication error
- `TokenExpiredError` - Token has expired
- `TokenRevokedError` - Token has been revoked
- `InvalidTokenError` - Token is malformed or invalid

### src/core/rbac.py

**Purpose**: Role-based access control with granular permissions and data filtering.

**Key Classes**:
- `RBACEnforcer` - Enforces permissions and filters data
  - `enforce()` - Raises exception if permission denied
  - `get_allowed_actions()` - List actions available to role
  - `filter_employee_data()` - Remove sensitive fields
  - `apply_data_scope_filter()` - Filter list by scope

**Key Enums**:
- `RoleLevel` - EMPLOYEE, MANAGER, HR_GENERALIST, HR_ADMIN
- `DataScope` - OWN, TEAM, DEPARTMENT, ALL

**Key Functions**:
- `check_permission()` - Verify single permission
- `get_data_scope()` - Get access scope for role/agent

**Key Exceptions**:
- `PermissionDeniedError` - User lacks required permissions

## Permission Matrix

Complete matrix of all defined permissions:

| Agent | Action | Min Role |
|-------|--------|----------|
| employee_info | view_own | EMPLOYEE |
| employee_info | view_reports | MANAGER |
| employee_info | view_all | HR_GENERALIST |
| policy | search | EMPLOYEE |
| policy | compliance_check | HR_GENERALIST |
| leave | view_own | EMPLOYEE |
| leave | view_team | MANAGER |
| leave | view_all | HR_GENERALIST |
| leave | approve | MANAGER |
| analytics | view_team | MANAGER |
| analytics | view_all | HR_GENERALIST |
| admin | configure | HR_ADMIN |
| admin | audit_logs | HR_ADMIN |

## Token Lifecycle

### Generation
```
User Login → AuthService.generate_token() → Access Token (1h) + Refresh Token (7d)
```

### Verification
```
API Request + Token → AuthService.verify_token() → User Data + Payload
```

### Refresh
```
Expired Access Token + Refresh Token → AuthService.refresh_token() → New Access Token
```

### Revocation
```
User Logout → AuthService.revoke_token(jti) → Redis Blacklist
Token Used → Check Redis → Reject if revoked
```

## Role Hierarchy

```
EMPLOYEE (1)
    ↓
MANAGER (2)
    ↓
HR_GENERALIST (3)
    ↓
HR_ADMIN (4)
```

Higher roles inherit all permissions of lower roles.

## Data Scope Model

```
EMPLOYEE     → OWN data only
    ↓
MANAGER      → Own + TEAM data
    ↓
HR_GENERALIST → Own + TEAM + DEPARTMENT data
    ↓
HR_ADMIN     → ALL organization data
```

## Sensitive Fields

Protected fields automatically filtered for non-HR roles:
- salary
- ssn
- bank_account
- tax_id
- compensation
- benefits_cost

## Configuration

Add to `config/settings.py`:

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    # JWT Configuration
    jwt_secret: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    
    # Optional: Cache for token blacklist
    redis_url: str = "redis://localhost:6379"
    
    class Config:
        env_file = ".env"
```

## Integration Examples

### Basic Authentication Flow

```python
# 1. User logs in
@app.route('/login', methods=['POST'])
def login():
    user = authenticate(request.json)
    tokens = auth_service.generate_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        department=user.department
    )
    return tokens

# 2. User includes token in requests
# Header: Authorization: Bearer <access_token>

# 3. Protected route
@app.route('/api/profile')
@require_auth
def get_profile():
    user_id = g.current_user['user_id']
    return get_user_profile(user_id)

# 4. Refresh expired token
@app.route('/refresh', methods=['POST'])
def refresh():
    new_tokens = auth_service.refresh_token(
        request.json['refresh_token']
    )
    return new_tokens

# 5. Logout (revoke token)
@app.route('/logout', methods=['POST'])
def logout():
    jti = g.current_user['jti']
    auth_service.revoke_token(jti)
    return {"status": "logged out"}
```

### Role-Based Route Protection

```python
# Employee routes
@app.route('/my-info')
@require_auth
def my_info():
    # Any authenticated user
    pass

# Manager routes
@app.route('/team-info')
@require_auth
@require_role('manager')
def team_info():
    # Managers and above
    pass

# Admin routes
@app.route('/admin/config', methods=['POST'])
@require_auth
@require_role('hr_admin')
def admin_config():
    # Only HR Admin
    pass
```

### Data Filtering

```python
@app.route('/api/employees')
@require_auth
def list_employees():
    all_employees = get_all_employees()
    
    # Apply scope filtering
    user = g.current_user
    scoped_data = enforcer.apply_data_scope_filter(
        all_employees,
        user_role=user['role'],
        agent_type='employee_info',
        requesting_user_id=user['user_id'],
        user_department=user['department'],
        team_members=get_team_members(user['user_id'])
    )
    
    # Apply sensitive field filtering
    filtered_data = [
        enforcer.filter_employee_data(emp, user['role'], user['user_id'])
        for emp in scoped_data
    ]
    
    return filtered_data
```

### Permission-Based Operations

```python
@app.route('/api/leave/approve', methods=['POST'])
@require_auth
def approve_leave():
    user = g.current_user
    
    # Enforce permission
    try:
        enforcer.enforce(user['role'], 'leave', 'approve')
    except PermissionDeniedError as e:
        return {"error": str(e)}, 403
    
    # Process approval
    leave_request = request.json
    approve_leave_request(leave_request)
    return {"status": "approved"}
```

## Error Handling

### Authentication Errors

```python
from src.middleware.auth import (
    AuthError,
    TokenExpiredError,
    TokenRevokedError,
    InvalidTokenError
)

try:
    user_data = auth_service.verify_token(token)
except TokenExpiredError:
    return {"error": "Token expired. Please refresh."}, 401
except TokenRevokedError:
    return {"error": "Token was revoked. Please login again."}, 401
except InvalidTokenError:
    return {"error": "Invalid token format."}, 401
except AuthError as e:
    return {"error": str(e)}, 400
```

### Authorization Errors

```python
from src.core.rbac import PermissionDeniedError

try:
    enforcer.enforce(user_role, agent_type, action)
except PermissionDeniedError as e:
    return {"error": str(e)}, 403
```

## Testing

Complete test examples provided in `TEST_EXAMPLES.md`.

Run tests:
```bash
# All tests
pytest tests/

# Specific module
pytest tests/test_auth.py
pytest tests/test_rbac.py

# With coverage
pytest --cov=src tests/
```

## Files

| File | Type | Size | Purpose |
|------|------|------|---------|
| `src/middleware/auth.py` | Source | 9.5K | JWT authentication |
| `src/core/rbac.py` | Source | 11K | Role-based access control |
| `AUTH_SECURITY_MODULES.md` | Doc | - | Detailed API reference |
| `QUICK_REFERENCE.md` | Doc | - | Quick lookup guide |
| `TEST_EXAMPLES.md` | Doc | - | Test suite examples |
| `IMPLEMENTATION_SUMMARY.md` | Doc | - | Completion status |

## Security Features

1. **Token Management**
   - Unique JTI for each token
   - Configurable expiration times
   - Redis blacklist for revocation
   - Separate access/refresh tokens

2. **Access Control**
   - Hierarchical role system
   - Granular action-level permissions
   - Scope-based data access
   - Automatic sensitive field filtering

3. **Error Handling**
   - Specific exception types
   - Clear error messages
   - No credential leakage
   - Proper HTTP status codes

## Dependencies

```
PyJWT>=2.0.0          # JWT encoding/decoding
Flask>=2.0.0          # Web framework
pydantic>=1.0.0       # Settings validation
redis>=4.0.0          # Optional: token blacklist
```

## Deployment Notes

1. **Generate Strong Secret Key**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Set Environment Variables**
   ```bash
   export JWT_SECRET="your-generated-secret"
   export JWT_ALGORITHM="HS256"
   export REDIS_URL="redis://localhost:6379"
   ```

3. **Initialize Cache Service**
   - Set up Redis for token blacklist
   - Or implement custom cache backend

4. **Configure Error Handlers**
   - Map AuthError to 401 responses
   - Map PermissionDeniedError to 403 responses

5. **Enable HTTPS**
   - Always use HTTPS in production
   - Tokens should only be transmitted over HTTPS

## Performance Considerations

- Tokens are stateless (no database lookup needed)
- Permission checks are O(1) with permission matrix
- Data filtering is O(n) for lists
- Cache blacklist lookups are O(1) with Redis

## Maintenance

All code follows Python best practices:
- Complete type hints
- Comprehensive docstrings
- Clear error messages
- Modular design
- Standard conventions

For questions, see documentation files:
1. `AUTH_SECURITY_MODULES.md` - Full API reference
2. `QUICK_REFERENCE.md` - Common operations
3. `TEST_EXAMPLES.md` - Usage patterns


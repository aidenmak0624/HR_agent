# Auth & Security Modules - HR Multi-Agent Platform

## Overview
Complete authentication and role-based access control (RBAC) system for the HR multi-agent platform with JWT token management, permission enforcement, and data filtering.

## Files Created

### 1. `/src/middleware/__init__.py`
Empty initialization file for the middleware package.

### 2. `/src/middleware/auth.py`
JWT Authentication Service with token generation, verification, and Flask decorators.

**Key Components:**

#### Custom Exceptions
- `AuthError` - Base authentication error
- `TokenExpiredError` - Token has expired
- `TokenRevokedError` - Token has been revoked
- `InvalidTokenError` - Token is invalid or malformed

#### AuthService Class
Handles all JWT token operations:

**Methods:**
- `generate_token(user_id, email, role, department)` 
  - Returns: dict with access_token, refresh_token, expires_at, token_type
  - Access token TTL: 3600 seconds (1 hour)
  - Refresh token TTL: 604800 seconds (7 days)
  - Token payload includes: user_id, email, role, department, iat, exp, jti (uuid4), type

- `verify_token(token)` 
  - Returns: dict with user_id, email, role, department, jti, type
  - Checks token expiration and blacklist status
  - Raises: TokenExpiredError, TokenRevokedError, InvalidTokenError

- `refresh_token(refresh_token_str)`
  - Returns: dict with new access_token, expires_at, token_type
  - Validates refresh token before generating new access token

- `revoke_token(jti)`
  - Adds token JTI to Redis blacklist via cache service
  - TTL matches token expiration time

- `is_revoked(jti)`
  - Returns: bool indicating if token has been revoked
  - Checks cache service for blacklist entry

#### Flask Decorators

**@require_auth**
- Enforces JWT authentication on routes
- Extracts Bearer token from Authorization header
- Verifies token and sets g.current_user with user information
- Raises AuthError if no token or invalid token

**@require_role(min_role)**
- Enforces role-based access control
- Must be used after @require_auth
- Checks role hierarchy: employee < manager < hr_generalist < hr_admin
- Raises AuthError if insufficient permissions

**Role Hierarchy:**
```
EMPLOYEE = 1
MANAGER = 2
HR_GENERALIST = 3
HR_ADMIN = 4
```

---

### 3. `/src/core/rbac.py`
Role-Based Access Control system with permission matrix and data filtering.

**Key Components:**

#### Enums

**RoleLevel**
- EMPLOYEE = 1
- MANAGER = 2
- HR_GENERALIST = 3
- HR_ADMIN = 4

**DataScope**
- OWN - Only own data
- TEAM - Team members data
- DEPARTMENT - Department data
- ALL - All organization data

#### Permission Matrix
Defines required role for each (agent_type, action) combination:

**Employee Info Permissions:**
- ("employee_info", "view_own") → EMPLOYEE
- ("employee_info", "view_reports") → MANAGER
- ("employee_info", "view_all") → HR_GENERALIST

**Policy Permissions:**
- ("policy", "search") → EMPLOYEE
- ("policy", "compliance_check") → HR_GENERALIST

**Leave Management Permissions:**
- ("leave", "view_own") → EMPLOYEE
- ("leave", "view_team") → MANAGER
- ("leave", "view_all") → HR_GENERALIST
- ("leave", "approve") → MANAGER

**Analytics Permissions:**
- ("analytics", "view_team") → MANAGER
- ("analytics", "view_all") → HR_GENERALIST

**Admin Permissions:**
- ("admin", "configure") → HR_ADMIN
- ("admin", "audit_logs") → HR_ADMIN

#### Helper Functions

**check_permission(user_role, agent_type, action)**
- Returns: bool indicating if permission is granted
- Compares user role level to minimum required role

**get_data_scope(user_role, agent_type)**
- Returns: DataScope enum for the user's access level
- Raises: PermissionDeniedError for invalid role/agent combinations

#### RBACEnforcer Class
Enforces permissions and filters data:

**Methods:**
- `enforce(user_role, agent_type, action)`
  - Raises: PermissionDeniedError if permission denied

- `get_allowed_actions(user_role, agent_type)`
  - Returns: List of allowed actions for user role on agent type

- `filter_employee_data(data, user_role, requesting_user_id)`
  - Removes sensitive fields for non-HR roles
  - Sensitive fields: salary, ssn, bank_account, tax_id, compensation, benefits_cost
  - Managers can view salary for direct reports

- `get_filtered_list(data_list, user_role, requesting_user_id)`
  - Filters list of employee data based on role

- `apply_data_scope_filter(data_list, user_role, agent_type, requesting_user_id, user_department, team_members)`
  - Applies data scope filtering (OWN, TEAM, DEPARTMENT, ALL)
  - Returns only accessible records per user's scope

#### Custom Exceptions
- `PermissionDeniedError` - User lacks required permissions

---

## Integration Points

### Configuration
Both modules use settings from `config/settings.py`:
- `jwt_secret` - Secret key for signing tokens
- `jwt_algorithm` - Algorithm for token encoding (default: HS256)

### Cache Service
AuthService integrates with cache module for token blacklisting:
- Uses `cache.set(key, value, ttl)` to revoke tokens
- Uses `cache.get(key)` to check if token is revoked
- Cache service is optional; revocation disabled if not configured

### Flask Integration
Both decorators are Flask-aware:
- Use `g.current_user` for user context
- Extract tokens from `request.headers`
- Can be stacked on routes: `@require_auth` then `@require_role`

---

## Usage Examples

### Authentication Flow
```python
from src.middleware.auth import AuthService

# Initialize
auth_service = AuthService(cache_service=cache_backend)

# Generate tokens
tokens = auth_service.generate_token(
    user_id="user123",
    email="user@example.com",
    role="manager",
    department="HR"
)
# Returns: {
#     "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#     "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#     "expires_at": "2024-02-06T01:53:00.000000",
#     "token_type": "Bearer"
# }

# Verify token
user_data = auth_service.verify_token(token)
# Returns: {
#     "user_id": "user123",
#     "email": "user@example.com",
#     "role": "manager",
#     "department": "HR",
#     "jti": "uuid-string",
#     "type": "access"
# }

# Refresh expired token
new_tokens = auth_service.refresh_token(refresh_token_str)

# Revoke token
auth_service.revoke_token(jti)

# Check revocation
is_revoked = auth_service.is_revoked(jti)
```

### Flask Route Protection
```python
from flask import Flask, g
from src.middleware.auth import require_auth, require_role

app = Flask(__name__)

@app.route('/employee/<emp_id>')
@require_auth
@require_role('manager')
def view_employee(emp_id):
    # g.current_user contains verified user data
    manager_id = g.current_user['user_id']
    # Only managers and above can access
    ...
```

### RBAC Permission Checking
```python
from src.core.rbac import RBACEnforcer, check_permission, get_data_scope

enforcer = RBACEnforcer()

# Check single permission
if check_permission('manager', 'leave', 'approve'):
    # Manager can approve leave
    ...

# Enforce permission (raises exception if denied)
try:
    enforcer.enforce('employee', 'admin', 'configure')
except PermissionDeniedError as e:
    # Employee cannot configure admin settings
    ...

# Get allowed actions
actions = enforcer.get_allowed_actions('hr_generalist', 'employee_info')
# Returns: ['view_own', 'view_reports', 'view_all']

# Get data scope
scope = get_data_scope('manager', 'leave')
# Returns: DataScope.TEAM

# Filter sensitive data
filtered = enforcer.filter_employee_data(
    employee_data, 
    user_role='employee',
    requesting_user_id='emp123'
)
# Removes: salary, ssn, bank_account, etc.

# Apply scope filtering
team_data = enforcer.apply_data_scope_filter(
    employee_list,
    user_role='manager',
    agent_type='employee_info',
    requesting_user_id='mgr456',
    user_department='HR',
    team_members=['emp1', 'emp2', 'emp3']
)
# Returns only manager and team members
```

---

## Security Features

1. **Token Management**
   - JWT with configurable TTL
   - Unique JTI (JWT ID) for each token
   - Token type tracking (access/refresh)
   - Token revocation via blacklist

2. **Role-Based Access**
   - Hierarchical role levels
   - Action-level permissions
   - Data scope enforcement (OWN, TEAM, DEPARTMENT, ALL)

3. **Data Protection**
   - Sensitive field filtering (salary, SSN, bank account, etc.)
   - Role-based data visibility
   - Manager limited access to direct reports only

4. **Error Handling**
   - Specific exception types for different errors
   - Clear error messages
   - Type hints throughout for safety

---

## Testing Recommendations

1. Test JWT token generation and verification
2. Test token expiration and refresh flow
3. Test token revocation and blacklist checking
4. Test Flask decorators with various token scenarios
5. Test RBAC permission matrix comprehensively
6. Test data filtering with different roles
7. Test scope filtering with team/department configurations
8. Test error handling and custom exceptions


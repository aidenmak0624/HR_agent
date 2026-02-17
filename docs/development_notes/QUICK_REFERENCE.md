# Auth & Security Modules - Quick Reference

## File Structure
```
/src/
├── middleware/
│   ├── __init__.py
│   └── auth.py              # JWT Auth Service + Flask decorators
└── core/
    └── rbac.py              # RBAC system with permissions
```

## Key Classes & Functions

### src/middleware/auth.py

**AuthService**
```python
auth = AuthService(cache_service=None)

# Token operations
tokens = auth.generate_token(user_id, email, role, department)
user_data = auth.verify_token(token)
new_tokens = auth.refresh_token(refresh_token_str)
auth.revoke_token(jti)
is_revoked = auth.is_revoked(jti)
```

**Decorators**
```python
@require_auth
def protected_route():
    user_id = g.current_user['user_id']

@require_role('manager')
def manager_only_route():
    pass
```

**Exceptions**
- AuthError
- TokenExpiredError
- TokenRevokedError
- InvalidTokenError

---

### src/core/rbac.py

**Enums**
```python
RoleLevel.EMPLOYEE (1)
RoleLevel.MANAGER (2)
RoleLevel.HR_GENERALIST (3)
RoleLevel.HR_ADMIN (4)

DataScope.OWN
DataScope.TEAM
DataScope.DEPARTMENT
DataScope.ALL
```

**Functions**
```python
check_permission(user_role, agent_type, action) -> bool
get_data_scope(user_role, agent_type) -> DataScope
```

**RBACEnforcer**
```python
enforcer = RBACEnforcer()

enforcer.enforce(user_role, agent_type, action)
enforcer.get_allowed_actions(user_role, agent_type)
enforcer.filter_employee_data(data, user_role, requesting_user_id)
enforcer.apply_data_scope_filter(data_list, user_role, agent_type, 
                                  requesting_user_id, user_department, team_members)
```

**Exception**
- PermissionDeniedError

---

## Permission Matrix Summary

| Agent Type | Action | Min Role |
|-----------|--------|----------|
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

---

## Token Payload Structure

```json
{
  "user_id": "string",
  "email": "string",
  "role": "employee|manager|hr_generalist|hr_admin",
  "department": "string",
  "iat": "timestamp",
  "exp": "timestamp",
  "jti": "uuid",
  "type": "access|refresh"
}
```

---

## TTLs

| Token Type | TTL |
|-----------|-----|
| Access | 3600 seconds (1 hour) |
| Refresh | 604800 seconds (7 days) |

---

## Sensitive Fields (auto-filtered for non-HR)

- salary
- ssn
- bank_account
- tax_id
- compensation
- benefits_cost

---

## Configuration Requirements

In `config/settings.py`:
```python
class Settings:
    jwt_secret: str  # Secret key for token signing
    jwt_algorithm: str = "HS256"  # Token algorithm
```

---

## Integration with Cache

Token revocation requires cache service with interface:
```python
cache.set(key: str, value: Any, ttl: int) -> None
cache.get(key: str) -> Optional[Any]
```

---

## Data Scope Behavior

| Scope | Returns |
|-------|---------|
| OWN | Only requester's own data |
| TEAM | Requester + team members |
| DEPARTMENT | All department members |
| ALL | All organization data |

---

## Flask Integration Example

```python
from flask import Flask, g
from src.middleware.auth import require_auth, require_role

app = Flask(__name__)

# Public endpoint
@app.route('/login', methods=['POST'])
def login():
    tokens = auth_service.generate_token(...)
    return tokens

# Employee endpoint - any authenticated user
@app.route('/my-info')
@require_auth
def my_info():
    return {"user_id": g.current_user['user_id']}

# Manager endpoint - requires manager+ role
@app.route('/team-info')
@require_auth
@require_role('manager')
def team_info():
    return {"manager_id": g.current_user['user_id']}

# Admin endpoint - requires hr_admin role
@app.route('/admin/config', methods=['POST'])
@require_auth
@require_role('hr_admin')
def admin_config():
    return {"status": "configured"}
```

---

## Error Handling Example

```python
from src.middleware.auth import AuthService, TokenExpiredError, InvalidTokenError
from src.core.rbac import RBACEnforcer, PermissionDeniedError

# Auth errors
try:
    user_data = auth.verify_token(token)
except TokenExpiredError:
    # Token expired, need refresh
    pass
except TokenRevokedError:
    # Token was revoked
    pass
except InvalidTokenError:
    # Malformed or invalid token
    pass

# RBAC errors
try:
    enforcer.enforce('employee', 'admin', 'configure')
except PermissionDeniedError as e:
    # User doesn't have permission
    return {"error": str(e)}, 403
```


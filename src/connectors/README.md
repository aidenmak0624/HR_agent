# HRIS Connectors Module

Unified HRIS (Human Resource Information System) connector framework for the HR multi-agent platform.

## Module Structure

```
src/connectors/
├── __init__.py              # Package initialization
├── hris_interface.py        # (HRIS-001) Abstract interface & data models
├── bamboohr.py             # (HRIS-002) BambooHR REST API connector
├── custom_db.py            # (HRIS-003) External database connector
└── README.md               # This file
```

## Files Overview

### 1. hris_interface.py (HRIS-001)
**Abstract HRIS Connector Interface**

- Abstract base class `HRISConnector` defining the connector interface
- Unified Pydantic data models for:
  - Employee (with 12 fields)
  - LeaveBalance (with 6 fields)
  - LeaveRequest (with 9 fields)
  - OrgNode (recursive hierarchy)
  - BenefitsPlan (with 6 fields)
- Enum types for constraints:
  - EmployeeStatus
  - LeaveType
  - LeaveStatus
  - PlanType
- Exception classes:
  - ConnectorError (base)
  - ConnectionError
  - AuthenticationError
  - NotFoundError
  - RateLimitError
- ConnectorRegistry for dynamic connector management

**File Size:** ~11 KB
**Lines of Code:** ~450
**Key Classes:** 15

### 2. bamboohr.py (HRIS-002)
**BambooHR REST API Connector**

- Full implementation of HRISConnector for BambooHR SaaS platform
- Features:
  - HTTP Basic Authentication
  - Automatic retry with exponential backoff
  - Rate limit (429) handling with Retry-After header support
  - Connection pooling with QueuePool
  - Request/response logging with duration tracking
  - Flexible field mapping from BambooHR to unified models
  - Leave type and plan type conversion

- Methods implemented:
  - get_employee() - Fetch single employee
  - search_employees() - Search with filters
  - get_leave_balance() - Get leave balance by type
  - get_leave_requests() - Get historical requests
  - submit_leave_request() - Create new leave request
  - get_org_chart() - Build org hierarchy
  - get_benefits() - Get employee benefits
  - health_check() - Connection health verification

**API Base URL:** `https://api.bamboohr.com/api/gateway.php/{subdomain}/v1`
**File Size:** ~17 KB
**Lines of Code:** ~550
**Key Methods:** 15 (8 abstract + 7 helper)

### 3. custom_db.py (HRIS-003)
**External Database Connector**

- Implementation of HRISConnector for arbitrary SQL databases
- Features:
  - SQLAlchemy database abstraction (supports PostgreSQL, MySQL, SQLite, Oracle, SQL Server, etc.)
  - READ-ONLY transaction isolation (prevents accidental writes)
  - Parameterized queries (SQL injection protection)
  - Connection pooling (10 pool size + 20 overflow)
  - Flexible schema mapping (maps database columns to unified fields)
  - Recursive CTE for organization hierarchy
  - Automatic database health checks

- Methods implemented:
  - get_employee() - Fetch with parameterized query
  - search_employees() - Dynamic WHERE builder
  - get_leave_balance() - Query leave balance table
  - get_leave_requests() - Query with optional status filter
  - submit_leave_request() - Raises error (read-only)
  - get_org_chart() - Recursive CTE hierarchy
  - get_benefits() - Query benefits table
  - health_check() - SELECT 1 test

**Supported Databases:** PostgreSQL, MySQL, SQLite, SQL Server, Oracle, others via SQLAlchemy
**File Size:** ~20 KB
**Lines of Code:** ~620
**Key Methods:** 15 (8 abstract + 7 helper)

## Quick Start

### Installation

```bash
pip install pydantic requests sqlalchemy urllib3
```

### BambooHR Example

```python
from src.connectors.bamboohr import BambooHRConnector

connector = BambooHRConnector(
    api_key="your-api-key",
    subdomain="company"
)

employee = connector.get_employee("12345")
if employee:
    print(f"{employee.first_name} {employee.last_name}")
    print(f"Department: {employee.department}")
```

### Custom Database Example

```python
from src.connectors.custom_db import CustomDBConnector

connector = CustomDBConnector(
    connection_string="postgresql://user:pass@localhost/hrdb",
    schema_mapping={
        "employee_table": "employees",
        "id_column": "id",
        "first_name_column": "fname",
        # ... other mappings
    }
)

employee = connector.get_employee("EMP001")
```

## Data Models

### Employee
```python
Employee(
    id: str,                      # Internal ID
    hris_id: str,                 # HRIS system ID
    first_name: str,
    last_name: str,
    email: str,
    department: str,
    job_title: str,
    manager_id: Optional[str],
    hire_date: datetime,
    status: EmployeeStatus,
    location: str,
    phone: Optional[str]
)
```

### LeaveBalance
```python
LeaveBalance(
    employee_id: str,
    leave_type: LeaveType,
    total_days: float,
    used_days: float,
    pending_days: float,
    available_days: float
)
```

### LeaveRequest
```python
LeaveRequest(
    id: Optional[str],
    employee_id: str,
    leave_type: LeaveType,
    start_date: datetime,
    end_date: datetime,
    status: LeaveStatus,
    reason: Optional[str],
    approver_id: Optional[str],
    submitted_at: datetime
)
```

### OrgNode (Recursive)
```python
OrgNode(
    employee_id: str,
    name: str,
    title: str,
    department: str,
    direct_reports: List[OrgNode]
)
```

### BenefitsPlan
```python
BenefitsPlan(
    id: str,
    name: str,
    plan_type: PlanType,
    coverage_level: str,
    employee_cost: float,
    employer_cost: float
)
```

## Exception Handling

All connectors raise specific exceptions for different scenarios:

```python
from src.connectors.hris_interface import (
    ConnectorError,         # Base exception
    ConnectionError,        # Connection failures
    AuthenticationError,    # Auth failures (401, 403)
    NotFoundError,          # Resource not found (404)
    RateLimitError         # Rate limited (429)
)

try:
    employee = connector.get_employee("ID")
except NotFoundError:
    print("Employee not found")
except AuthenticationError:
    print("Invalid credentials")
except ConnectionError:
    print("Cannot connect to HRIS")
except RateLimitError:
    print("Rate limited")
except ConnectorError as e:
    print(f"Other error: {e}")
```

## ConnectorRegistry

Register and manage multiple connector implementations:

```python
from src.connectors.hris_interface import ConnectorRegistry
from src.connectors.bamboohr import BambooHRConnector
from src.connectors.custom_db import CustomDBConnector

# Register implementations
ConnectorRegistry.register("bamboohr", BambooHRConnector)
ConnectorRegistry.register("custom_db", CustomDBConnector)

# List available
available = ConnectorRegistry.list_connectors()
# ['bamboohr', 'custom_db']

# Get connector class
ConnectorClass = ConnectorRegistry.get("bamboohr")
connector = ConnectorClass(api_key="...", subdomain="...")
```

## Features Comparison

| Feature | BambooHR | CustomDB |
|---------|----------|----------|
| REST API | Yes | - |
| Database Support | - | PostgreSQL, MySQL, SQLite, Oracle, etc. |
| Auth Method | HTTP Basic | Connection String |
| Rate Limiting Handled | Yes (429) | - |
| Retry Logic | Yes (exponential backoff) | Basic error handling |
| Connection Pooling | Yes | Yes (SQLAlchemy) |
| Read-Only Enforcement | - | Yes (transaction isolation) |
| SQL Injection Protection | - | Yes (parameterized queries) |
| Logging | Yes (duration) | Yes (errors) |
| Health Check | Yes | Yes |

## Logging

All connectors use Python's standard logging module:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("src.connectors")

# Now see connector logs:
# INFO - Making GET request to /employees/12345
# INFO - GET /employees/12345 - 200 (0.45s)
```

## Performance Characteristics

### BambooHR
- Connection pooling: HTTP keep-alive
- Retry backoff: 1s, 2s, 4s
- Request timeout: 30s (default for requests)
- Batch operations: Not supported by REST API

### CustomDB
- Connection pool: 10 connections + 20 overflow
- Query timeout: 10s (configurable)
- Connection timeout: 10s
- Batch operations: Supported via raw SQL

## Security Considerations

### BambooHR
- Uses HTTP Basic Auth (credentials in Authorization header)
- api_key treated as username, 'x' as password
- HTTPS enforced (https://api.bamboohr.com)
- No credentials logged

### CustomDB
- All queries use parameterized statements (prevent SQL injection)
- Read-only transaction isolation (prevent accidental writes)
- Connection strings stored securely (use environment variables)
- No query logging by default

## Testing & Validation

All modules pass Python syntax validation:

```bash
python3 -c "import ast; ast.parse(open('hris_interface.py').read())"
python3 -c "import ast; ast.parse(open('bamboohr.py').read())"
python3 -c "import ast; ast.parse(open('custom_db.py').read())"
```

To test imports (requires dependencies):

```bash
pip install pydantic requests sqlalchemy urllib3
python3 -c "from src.connectors.hris_interface import HRISConnector"
python3 -c "from src.connectors.bamboohr import BambooHRConnector"
python3 -c "from src.connectors.custom_db import CustomDBConnector"
```

## Integration with HR Agents

Example integration with an HR agent:

```python
from src.connectors.bamboohr import BambooHRConnector

class EmployeeAgent:
    def __init__(self, hris_connector):
        self.connector = hris_connector
    
    def get_employee_info(self, emp_id):
        """Get comprehensive employee information"""
        emp = self.connector.get_employee(emp_id)
        leave_balance = self.connector.get_leave_balance(emp_id)
        benefits = self.connector.get_benefits(emp_id)
        
        return {
            "employee": emp,
            "leave": leave_balance,
            "benefits": benefits
        }

# Usage
connector = BambooHRConnector(api_key="...", subdomain="...")
agent = EmployeeAgent(connector)
info = agent.get_employee_info("12345")
```

## Contributing

When adding new HRIS system support:

1. Create new file: `connectors/my_system.py`
2. Inherit from `HRISConnector`
3. Implement all 8 abstract methods
4. Use unified data models from `hris_interface.py`
5. Add field mapping helpers like BambooHR and CustomDB
6. Register in ConnectorRegistry
7. Add logging for debugging
8. Include error handling with specific exceptions

## License

Part of HR Multi-Agent Platform

## Support

See `CONNECTORS_SUMMARY.md` for detailed documentation
See `CONNECTORS_QUICKSTART.md` for quick start guide

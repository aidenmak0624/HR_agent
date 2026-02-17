# HRIS Connector Modules - Implementation Summary

## Overview
Created a complete HRIS Connector framework for the HR multi-agent platform with three modules:
1. **hris_interface.py** (HRIS-001) - Abstract base class and unified data models
2. **bamboohr.py** (HRIS-002) - BambooHR REST API implementation
3. **custom_db.py** (HRIS-003) - External database implementation

## File Locations
- `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/connectors/__init__.py`
- `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/connectors/hris_interface.py` (11KB)
- `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/connectors/bamboohr.py` (17KB)
- `/sessions/beautiful-amazing-lamport/mnt/HR_agent/src/connectors/custom_db.py` (20KB)

---

## Module 1: hris_interface.py (HRIS-001)

### Exception Classes
- `ConnectorError` - Base exception
- `ConnectionError` - Connection failures
- `AuthenticationError` - Auth failures
- `NotFoundError` - Resource not found (404)
- `RateLimitError` - Rate limiting (429)

### Enums
- `EmployeeStatus`: active, inactive, on_leave, terminated
- `LeaveType`: pto, sick, personal, unpaid, other
- `LeaveStatus`: pending, approved, denied, cancelled
- `PlanType`: health, dental, vision, 401k, life_insurance, other

### Pydantic Data Models

#### Employee
```python
Employee(
    id: str                      # Internal ID
    hris_id: str                 # HRIS system ID
    first_name: str
    last_name: str
    email: str
    department: str
    job_title: str
    manager_id: Optional[str]
    hire_date: datetime
    status: EmployeeStatus
    location: str
    phone: Optional[str]
)
```

#### LeaveBalance
```python
LeaveBalance(
    employee_id: str
    leave_type: LeaveType
    total_days: float
    used_days: float
    pending_days: float
    available_days: float
)
```

#### LeaveRequest
```python
LeaveRequest(
    id: Optional[str]
    employee_id: str
    leave_type: LeaveType
    start_date: datetime
    end_date: datetime
    status: LeaveStatus
    reason: Optional[str]
    approver_id: Optional[str]
    submitted_at: datetime
)
```

#### OrgNode (Recursive)
```python
OrgNode(
    employee_id: str
    name: str
    title: str
    department: str
    direct_reports: List[OrgNode]
)
```

#### BenefitsPlan
```python
BenefitsPlan(
    id: str
    name: str
    plan_type: PlanType
    coverage_level: str         # e.g., "Employee", "Family"
    employee_cost: float
    employer_cost: float
)
```

### Abstract Base Class: HRISConnector

**Abstract Methods:**
- `get_employee(employee_id: str) -> Optional[Employee]`
- `search_employees(filters: Dict[str, Any]) -> List[Employee]`
- `get_leave_balance(employee_id: str) -> List[LeaveBalance]`
- `get_leave_requests(employee_id: str, status: Optional[str]=None) -> List[LeaveRequest]`
- `submit_leave_request(request: LeaveRequest) -> LeaveRequest`
- `get_org_chart(department: Optional[str]=None) -> List[OrgNode]`
- `get_benefits(employee_id: str) -> List[BenefitsPlan]`
- `health_check() -> bool`

### ConnectorRegistry
Singleton registry for managing connector implementations:
- `register(name: str, connector_cls: type)` - Register connector
- `get(name: str) -> Optional[type]` - Get connector class
- `list_connectors() -> List[str]` - List registered names

---

## Module 2: bamboohr.py (HRIS-002)

### BambooHRConnector Class

**Features:**
- Full HRISConnector implementation
- BambooHR REST API integration
- Automatic retry with exponential backoff (429 handling)
- HTTP Basic Auth (api_key as username, 'x' as password)
- Connection pooling with QueuePool
- Request logging with duration tracking
- Field mapping from BambooHR to unified models

**Initialization:**
```python
connector = BambooHRConnector(
    api_key="your-api-key",
    subdomain="company"  # for company.bamboohr.com
)
```

**API Endpoints Used:**
- Employee: `GET /employees/{id}/?fields=...`
- Directory: `GET /employees/directory`
- Leave Balance: `GET /employees/{id}/time_off/calculator?end={date}`
- Leave Requests: `GET /time_off/requests/?employeeId={id}&status={status}`
- Submit Leave: `POST /employees/{id}/time_off/request`
- Benefits: `GET /employees/{id}/benefits`

**Field Mapping:**
```
firstName → first_name
lastName → last_name
workEmail → email
jobTitle → job_title
supervisor → manager_id
mobilePhone → phone
```

**Leave Type Mapping:**
- pto, vacation, paid_time_off → LeaveType.PTO
- sick, sick_leave → LeaveType.SICK
- personal, personal_day → LeaveType.PERSONAL
- unpaid → LeaveType.UNPAID

**Plan Type Mapping:**
- health, health_insurance → PlanType.HEALTH
- dental, dental_insurance → PlanType.DENTAL
- vision, vision_insurance → PlanType.VISION
- 401k, retirement → PlanType.FOUR_01K
- life, life_insurance → PlanType.LIFE_INSURANCE

**Retry Strategy:**
- 3 retries for transient errors (429, 500, 502, 503, 504)
- Exponential backoff: 1, 2, 4 seconds
- Respects Retry-After header for rate limits

---

## Module 3: custom_db.py (HRIS-003)

### CustomDBConnector Class

**Features:**
- SQLAlchemy abstraction for multiple DB types
- READ-ONLY operations with transaction isolation
- Parameterized queries (SQL injection protection)
- Connection pooling (10 base, 20 overflow)
- Automatic connection health checks
- Recursive CTE for org hierarchy
- Flexible schema mapping

**Initialization:**
```python
schema_mapping = {
    "employee_table": "hr_employees",
    "id_column": "emp_id",
    "first_name_column": "fname",
    "last_name_column": "lname",
    "email_column": "work_email",
    "department_column": "dept",
    "job_title_column": "title",
    "manager_id_column": "mgr_id",
    "hire_date_column": "hire_date",
    "status_column": "emp_status",
    "location_column": "office",
    "phone_column": "phone_num",
    "leave_balance_table": "leave_balances",
    "leave_requests_table": "leave_requests",
    "benefits_table": "benefits"
}

connector = CustomDBConnector(
    connection_string="postgresql://user:pass@localhost/hrdb",
    schema_mapping=schema_mapping
)
```

**Supported Databases:**
- PostgreSQL
- MySQL
- SQLite
- SQL Server
- Oracle
(Any database supported by SQLAlchemy)

**Features:**

1. **get_employee** - Single employee with parameterized WHERE
2. **search_employees** - Dynamic filter builder with AND conditions
3. **get_leave_balance** - Direct table query
4. **get_leave_requests** - With optional status filter
5. **submit_leave_request** - Raises ConnectorError (read-only)
6. **get_org_chart** - Recursive CTE for manager hierarchy
7. **get_benefits** - Employee benefits lookup
8. **health_check** - SELECT 1 test query

**Read-Only Transactions:**
```sql
SET TRANSACTION ISOLATION LEVEL READ COMMITTED
SET TRANSACTION READ ONLY
```

**Org Chart Recursive CTE (PostgreSQL):**
```sql
WITH RECURSIVE org_tree AS (
    -- Root employees (no manager)
    SELECT ... WHERE manager_id IS NULL
    UNION ALL
    -- Nested employees
    SELECT ... FROM employees
    INNER JOIN org_tree ON employees.manager_id = org_tree.id
)
SELECT * FROM org_tree ORDER BY level, id
```

**Connection Pool Configuration:**
- Pool size: 10
- Max overflow: 20
- Connection timeout: 10 seconds
- Echo: False (no query logging to console)

---

## Key Features Across All Modules

### Type Safety
- Full type hints on all methods and functions
- Pydantic models for data validation
- Enum types for constrained values

### Error Handling
- Specific exception types for different failures
- Proper HTTP status code mapping
- Timeout handling
- Connection pooling with automatic recovery

### Logging
- Structured logging with timestamps
- API call duration tracking
- Request/response logging
- Error context preservation

### Security
- HTTP Basic Auth (BambooHR)
- Parameterized SQL queries (CustomDB)
- Read-only transaction isolation (CustomDB)
- No credentials in logs

### Performance
- Connection pooling with max overflow
- Retry with exponential backoff
- Health checks for proactive failure detection
- Timeout configuration

---

## Usage Examples

### BambooHR Connector
```python
from src.connectors.bamboohr import BambooHRConnector

# Initialize
connector = BambooHRConnector(
    api_key="YOUR_API_KEY",
    subdomain="company"
)

# Get employee
employee = connector.get_employee("12345")

# Search employees
employees = connector.search_employees({
    "department": "Sales",
    "status": "active"
})

# Get leave balance
balances = connector.get_leave_balance("12345")

# Get leave requests
requests = connector.get_leave_requests("12345", status="pending")

# Submit leave
from src.connectors.hris_interface import LeaveRequest, LeaveType, LeaveStatus
from datetime import datetime

new_request = LeaveRequest(
    employee_id="12345",
    leave_type=LeaveType.PTO,
    start_date=datetime(2024, 3, 1),
    end_date=datetime(2024, 3, 5),
    status=LeaveStatus.PENDING,
    reason="Vacation",
    submitted_at=datetime.now()
)
result = connector.submit_leave_request(new_request)

# Get org chart
org = connector.get_org_chart(department="Engineering")

# Get benefits
benefits = connector.get_benefits("12345")

# Health check
is_healthy = connector.health_check()
```

### Custom DB Connector
```python
from src.connectors.custom_db import CustomDBConnector

schema = {
    "employee_table": "employees",
    "id_column": "id",
    "first_name_column": "first_name",
    "last_name_column": "last_name",
    # ... other mappings
}

connector = CustomDBConnector(
    connection_string="postgresql://user:pass@localhost/hrdb",
    schema_mapping=schema
)

# All same methods as BambooHR
employee = connector.get_employee("12345")
employees = connector.search_employees({"department": "HR"})
org = connector.get_org_chart()

# Cleanup when done
connector.close()
```

### Using ConnectorRegistry
```python
from src.connectors.hris_interface import ConnectorRegistry
from src.connectors.bamboohr import BambooHRConnector
from src.connectors.custom_db import CustomDBConnector

# Register connectors
ConnectorRegistry.register("bamboohr", BambooHRConnector)
ConnectorRegistry.register("custom_db", CustomDBConnector)

# List available
available = ConnectorRegistry.list_connectors()
# ['bamboohr', 'custom_db']

# Get connector class
BambooHRClass = ConnectorRegistry.get("bamboohr")
```

---

## Dependencies Required

### For BambooHRConnector
- `requests` - HTTP client
- `urllib3` - Retry logic
- `pydantic` - Data models

### For CustomDBConnector
- `sqlalchemy` - Database abstraction
- `pydantic` - Data models

### For Both
- `python 3.9+` - Type hints and modern features
- `pydantic` - Unified data models

---

## Testing the Modules

All modules have valid Python syntax and are ready for import:

```bash
python3 -c "from src.connectors.hris_interface import HRISConnector"
python3 -c "from src.connectors.bamboohr import BambooHRConnector"
python3 -c "from src.connectors.custom_db import CustomDBConnector"
```

---

## Code Quality

✓ All files pass Python AST syntax validation
✓ Complete type hints throughout
✓ Comprehensive docstrings (module, class, method level)
✓ Error handling with specific exception types
✓ Logging for debugging and monitoring
✓ Clean separation of concerns
✓ DRY principle with helper methods
✓ Parameterized queries for security
✓ Connection pooling for performance


# HRIS Connectors - Quick Start Guide

## Installation

Install required dependencies:

```bash
pip install pydantic requests sqlalchemy urllib3
```

## Basic Setup

### Option 1: BambooHR (SaaS HRIS)

```python
from src.connectors.bamboohr import BambooHRConnector

# Initialize from environment or config
connector = BambooHRConnector(
    api_key=os.getenv("BAMBOOHR_API_KEY"),
    subdomain=os.getenv("BAMBOOHR_SUBDOMAIN")
)

# Check health
if connector.health_check():
    print("Connected to BambooHR")
```

### Option 2: Custom Database

```python
from src.connectors.custom_db import CustomDBConnector

# Define schema mapping for your database
schema = {
    "employee_table": "employees",
    "id_column": "employee_id",
    "first_name_column": "first_name",
    "last_name_column": "last_name",
    "email_column": "email",
    "department_column": "department",
    "job_title_column": "position",
    "manager_id_column": "manager_id",
    "hire_date_column": "start_date",
    "status_column": "employment_status",
    "location_column": "office_location",
    "phone_column": "phone",
    "leave_balance_table": "leave_balances",
    "leave_requests_table": "time_off_requests",
    "benefits_table": "employee_benefits"
}

connector = CustomDBConnector(
    connection_string="postgresql://user:pass@localhost/hrdb",
    schema_mapping=schema
)

if connector.health_check():
    print("Connected to database")
```

## Common Operations

### Get Single Employee

```python
employee = connector.get_employee("EMP123")

if employee:
    print(f"{employee.first_name} {employee.last_name}")
    print(f"Title: {employee.job_title}")
    print(f"Department: {employee.department}")
```

### Search Employees

```python
# Search by department
sales_team = connector.search_employees({
    "department": "Sales"
})

# Search by status
active_employees = connector.search_employees({
    "status": "active"
})

# Multiple filters (AND)
engineers = connector.search_employees({
    "department": "Engineering",
    "status": "active"
})

for emp in engineers:
    print(f"- {emp.first_name} {emp.last_name} ({emp.job_title})")
```

### Check Leave Balance

```python
balances = connector.get_leave_balance("EMP123")

for balance in balances:
    print(f"{balance.leave_type.value.upper()}")
    print(f"  Total: {balance.total_days} days")
    print(f"  Used: {balance.used_days} days")
    print(f"  Available: {balance.available_days} days")
```

### View Leave History

```python
# Get all requests
all_requests = connector.get_leave_requests("EMP123")

# Get only pending requests
pending = connector.get_leave_requests("EMP123", status="pending")

for request in pending:
    print(f"{request.start_date.date()} to {request.end_date.date()}")
    print(f"Type: {request.leave_type.value}")
    print(f"Status: {request.status.value}")
    print(f"Reason: {request.reason}")
```

### Submit Leave Request

```python
from src.connectors.hris_interface import LeaveRequest, LeaveType, LeaveStatus
from datetime import datetime, timedelta

# Create new request
tomorrow = datetime.now().date()
end_date = tomorrow + timedelta(days=4)

new_request = LeaveRequest(
    employee_id="EMP123",
    leave_type=LeaveType.PTO,
    start_date=datetime.combine(tomorrow, datetime.min.time()),
    end_date=datetime.combine(end_date, datetime.min.time()),
    status=LeaveStatus.PENDING,
    reason="Vacation",
    submitted_at=datetime.now()
)

# Submit (BambooHR only - CustomDB is read-only)
result = connector.submit_leave_request(new_request)
print(f"Request ID: {result.id}")
print(f"Status: {result.status.value}")
```

### Get Organization Chart

```python
# Get full organization
org = connector.get_org_chart()

def print_org(nodes, indent=0):
    for node in nodes:
        print("  " * indent + f"- {node.name} ({node.title})")
        print_org(node.direct_reports, indent + 1)

print_org(org)

# Get specific department only
engineering = connector.get_org_chart(department="Engineering")
print_org(engineering)
```

### View Benefits

```python
benefits = connector.get_benefits("EMP123")

for plan in benefits:
    print(f"{plan.name} ({plan.plan_type.value})")
    print(f"  Coverage: {plan.coverage_level}")
    print(f"  Cost: ${plan.employee_cost:.2f} / month (employee)")
    print(f"        ${plan.employer_cost:.2f} / month (employer)")
```

## Error Handling

```python
from src.connectors.hris_interface import (
    NotFoundError,
    ConnectionError,
    AuthenticationError,
    RateLimitError,
)

try:
    employee = connector.get_employee("INVALID")
except NotFoundError:
    print("Employee not found")
except AuthenticationError:
    print("Invalid API credentials")
except RateLimitError as e:
    print(f"Rate limited: {e}")
except ConnectionError:
    print("Connection failed")
```

## Using ConnectorRegistry

Register and switch between connectors dynamically:

```python
from src.connectors.hris_interface import ConnectorRegistry
from src.connectors.bamboohr import BambooHRConnector
from src.connectors.custom_db import CustomDBConnector

# Register connectors
ConnectorRegistry.register("bamboohr", BambooHRConnector)
ConnectorRegistry.register("database", CustomDBConnector)

# List available
available = ConnectorRegistry.list_connectors()
print(f"Available connectors: {available}")

# Get and instantiate
BambooHRClass = ConnectorRegistry.get("bamboohr")
connector = BambooHRClass(api_key="...", subdomain="...")
```

## Configuration Best Practices

### Environment Variables

```python
import os
from src.connectors.bamboohr import BambooHRConnector

# Load from .env
BAMBOOHR_API_KEY = os.getenv("BAMBOOHR_API_KEY")
BAMBOOHR_SUBDOMAIN = os.getenv("BAMBOOHR_SUBDOMAIN")

connector = BambooHRConnector(
    api_key=BAMBOOHR_API_KEY,
    subdomain=BAMBOOHR_SUBDOMAIN
)
```

### Config File

```python
import yaml
from src.connectors.custom_db import CustomDBConnector

with open("connectors/config.yml") as f:
    config = yaml.safe_load(f)

connector = CustomDBConnector(
    connection_string=config["database"]["connection_string"],
    schema_mapping=config["database"]["schema_mapping"]
)
```

## Integration with Agents

Use connectors in your HR agent:

```python
from src.connectors.bamboohr import BambooHRConnector

class EmployeeInfoAgent:
    def __init__(self, hris_connector):
        self.connector = hris_connector
    
    def get_employee_summary(self, employee_id):
        """Get employee information summary"""
        employee = self.connector.get_employee(employee_id)
        if not employee:
            return None
        
        balances = self.connector.get_leave_balance(employee_id)
        benefits = self.connector.get_benefits(employee_id)
        
        return {
            "employee": employee,
            "leave_balances": balances,
            "benefits": benefits
        }

# Usage
connector = BambooHRConnector(api_key="...", subdomain="...")
agent = EmployeeInfoAgent(connector)
info = agent.get_employee_summary("EMP123")
```

## Troubleshooting

### Connection Issues

```python
# Check health
if not connector.health_check():
    print("Cannot connect to HRIS system")
    # Check API key, network, firewall
```

### Authentication Errors

- BambooHR: Verify API key and subdomain
- CustomDB: Check connection string and user permissions

### Rate Limiting (BambooHR)

```python
from src.connectors.hris_interface import RateLimitError
import time

try:
    employees = connector.search_employees({})
except RateLimitError as e:
    print(f"Rate limited: {e}")
    time.sleep(60)  # Wait before retry
```

### Database Errors (CustomDB)

- Check database connection string
- Verify schema mapping table/column names
- Ensure database user has SELECT permissions
- CustomDB is read-only; write operations will raise errors


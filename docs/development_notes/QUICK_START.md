# Quick Start Guide - HR Multi-Agent Platform

## Installation

```bash
# Install dependencies
pip install sqlalchemy>=2.0 pydantic-settings>=2.0 redis>=4.0

# Optional for enhanced features
pip install aiosqlite python-json-logger redis[asyncio]
```

## Initialize the Platform

```python
# 1. Configure settings
from config.settings import get_settings

settings = get_settings()
print(f"Database: {settings.DATABASE_URL}")
print(f"Debug: {settings.DEBUG}")
print(f"Port: {settings.PORT}")

# 2. Initialize database
from src.core.database import init_db

init_db(settings.get_database_url())

# 3. Setup logging
from src.core.logging_config import setup_logging, get_logger

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)
logger.info("Platform initialized")

# 4. Initialize cache
from src.core.cache import get_cache_manager

cache = get_cache_manager(settings.get_redis_url())
cache_status = cache.health_check()
logger.info(f"Cache available: {cache_status}")
```

## Database Operations

```python
from src.core.database import get_db, Employee
from datetime import datetime

# Get session
session = get_db()

# Create employee
emp = Employee(
    hris_id="EMP001",
    hris_source="bamboohr",
    first_name="John",
    last_name="Doe",
    email="john@company.com",
    department="Engineering",
    role_level="employee",
    hire_date=datetime.now(),
    status="active"
)
session.add(emp)
session.commit()

# Query employees
employees = session.query(Employee).filter(
    Employee.status == "active"
).all()

for emp in employees:
    print(f"{emp.first_name} {emp.last_name} - {emp.role_level}")

session.close()
```

## Caching Operations

```python
from src.core.cache import get_cache_manager

cache = get_cache_manager()

# Basic caching
cache.set("user:123", {"name": "John", "role": "manager"}, ttl=3600)
user = cache.get("user:123")

# Session management
cache.store_session("session_abc123", {
    "user_id": 123,
    "role": "manager",
    "permissions": ["read", "write"]
})
session_data = cache.get_session("session_abc123")

# Rate limiting
allowed, remaining = cache.check_rate_limit("user:123", limit=60, window=60)
if not allowed:
    print(f"Rate limited. Try again in 60 seconds.")
else:
    print(f"Requests remaining: {remaining}")

# HRIS caching
hris_data = {"employee_id": "E001", "salary": 100000}
cache.cache_hris_response("E001", hris_data)
cached = cache.get_hris_cache("E001")

# Response caching
import hashlib
query = "What is my salary?"
query_hash = hashlib.md5(query.encode()).hexdigest()
cache.cache_response(query_hash, "employee", {"answer": "100k"})
response = cache.get_cached_response(query_hash, "employee")
```

## Logging Operations

```python
from src.core.logging_config import setup_logging, get_logger, log_performance

# Setup
setup_logging("INFO")
logger = get_logger(__name__)

# Basic logging
logger.info("User login attempt", extra={"user_id": 123})
logger.warning("Slow query detected", extra={"duration_ms": 5000})
logger.error("Database error", exc_info=True)

# Performance tracking
with log_performance("database_query", logger):
    # Perform operation
    result = session.query(Employee).all()

# In Flask app
from flask import Flask
from src.core.logging_config import RequestLogger

app = Flask(__name__)
request_logger = RequestLogger(logger)
before_req, after_req = request_logger.create_middleware(logger)

@app.before_request
def before():
    before_req()

@app.after_request
def after(response):
    return after_req(response)
```

## Configuration Management

```python
from config.settings import get_settings
import os

# Load from environment
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/hrdb"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["DEBUG"] = "True"

# Get settings (cached singleton)
settings = get_settings()

# Access settings
db_url = settings.DATABASE_URL
async_db_url = settings.get_async_database_url()
redis_url = settings.get_redis_url()
is_prod = settings.is_production()
cors_origins = settings.get_cors_origins()

print(f"Running in {'production' if is_prod else 'development'} mode")
```

## Health Checks

```python
from src.core.database import health_check as db_health
from src.core.cache import get_cache_manager

# Database health
db_ok = db_health()
print(f"Database: {'OK' if db_ok else 'FAILED'}")

# Cache health
cache = get_cache_manager()
cache_ok = cache.health_check()
print(f"Cache: {'OK' if cache_ok else 'FAILED'}")
```

## Async Operations (FastAPI)

```python
from fastapi import FastAPI
from src.core.database import init_async_engine, get_async_db
from config.settings import get_settings

app = FastAPI()
settings = get_settings()

@app.on_event("startup")
async def startup():
    await init_async_engine(settings.get_async_database_url())

@app.get("/employees")
async def list_employees():
    async for session in get_async_db():
        employees = await session.execute(select(Employee))
        return employees.scalars().all()
```

## Common Patterns

### Audit Logging
```python
from src.core.database import AuditLog, get_db
from datetime import datetime

session = get_db()
audit = AuditLog(
    user_id=123,
    action="update",
    resource_type="employee",
    resource_id="456",
    details={"changed_fields": ["salary", "department"]},
    ip_address="192.168.1.1"
)
session.add(audit)
session.commit()
```

### Conversation Tracking
```python
from src.core.database import Conversation, ConversationMessage
import datetime

conv = Conversation(
    user_id=123,
    agent_type="benefits",
    query="What are my health insurance options?",
    response_summary="Listed 3 available plans",
    confidence_score=0.95,
    tools_used=["benefits_api", "employee_db"],
    started_at=datetime.datetime.now(),
    resolved=True
)

msg = ConversationMessage(
    conversation_id=conv.id,
    role="assistant",
    content="Here are your options...",
    timestamp=datetime.datetime.now()
)
```

### Rate Limit Enforcement
```python
from src.core.cache import get_cache_manager
from flask import request, jsonify

cache = get_cache_manager()

@app.before_request
def check_rate_limit():
    user_id = get_current_user_id()
    allowed, remaining = cache.check_rate_limit(user_id, limit=100, window=60)
    
    if not allowed:
        return jsonify({"error": "Rate limit exceeded"}), 429
```

## Environment Template (.env)

```
# Database
DATABASE_URL=sqlite:///hr_platform.db

# Cache
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET=your-very-secure-secret-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# External APIs
GOOGLE_API_KEY=your-google-api-key
BAMBOOHR_API_KEY=your-bamboohr-key
BAMBOOHR_SUBDOMAIN=yourcompany
LLM_API_KEY=your-openai-key

# Configuration
HRIS_PROVIDER=bamboohr
LOG_LEVEL=INFO
DEBUG=False
PORT=5050
LLM_DEFAULT_MODEL=gpt-4
LLM_FAST_MODEL=gpt-3.5-turbo
CONFIDENCE_THRESHOLD=0.7
MAX_ITERATIONS=5
PII_ENABLED=True
RATE_LIMIT_PER_MINUTE=60
```

## Common Issues & Solutions

**Redis connection failed?**
- Cache operations will gracefully fail and return None
- Application continues working without caching
- Check Redis is running: `redis-cli ping`

**Database connection timeout?**
- Verify DATABASE_URL is correct
- Check network connectivity
- Pool pre-ping will handle stale connections

**Logging not outputting JSON?**
- Install python-json-logger: `pip install python-json-logger`
- Falls back to custom JSONFormatter if unavailable

**Import errors?**
- Ensure files are in Python path
- Add to sys.path: `sys.path.insert(0, '/path/to/HR_agent')`
- Use: `from src.core.database import Employee`

---

For more details, see CREATED_FILES_SUMMARY.md and VERIFICATION_REPORT.md

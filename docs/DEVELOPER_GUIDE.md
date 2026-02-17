# Developer Guide - HR Multi-Agent Intelligence Platform

## Getting Started

This guide covers everything needed to set up, develop, test, and deploy the HR Multi-Agent Intelligence Platform.

---

## Prerequisites

### Required
- **Python 3.10+** - https://www.python.org/downloads/
- **Node.js 20+** - https://nodejs.org/
- **PostgreSQL 14+** (for production) - https://www.postgresql.org/
- **Git** - https://git-scm.com/

### Optional (Recommended)
- **Docker & Docker Compose** - https://www.docker.com/products/docker-desktop
- **VS Code** - https://code.visualstudio.com/
- **Postman** - https://www.postman.com/ (for API testing)

### System Requirements
- **RAM:** 8GB minimum (16GB recommended)
- **Disk:** 20GB for databases and node_modules
- **Network:** Internet access for OpenAI API calls

---

## Quick Start

### Step 1: Clone Repository
```bash
git clone https://github.com/your-company/hr-multi-agent.git
cd hr-multi-agent
```

### Step 2: Set Up Python Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### Step 3: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Install Node Dependencies
```bash
npm install
```

### Step 5: Configure Environment Variables
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# Required variables:
# - OPENAI_API_KEY
# - DATABASE_URL (for production)
# - JWT_SECRET_KEY
```

### Step 6: Initialize Database
```bash
# Run migrations
alembic upgrade head

# Seed with sample data
python scripts/seed_database.py
```

### Step 7: Start Development Server
```bash
# Terminal 1: Start Flask backend
python run.py

# Terminal 2: Start React frontend (if developing UI)
npm start
```

**Access Application:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:5000/api/v2
- API Docs: http://localhost:5000/api

---

## Environment Variables Reference

### Essential Configuration

```bash
# Flask Configuration
FLASK_ENV=development          # development, staging, production
FLASK_DEBUG=True              # Enable debug mode
FLASK_APP=src/app_v2.py       # Main app file
SECRET_KEY=your-secret-key    # Flask session secret

# Database Configuration
DATABASE_URL=sqlite:///hr_platform.db    # SQLite (dev)
# DATABASE_URL=postgresql://user:pass@localhost:5432/hr_platform  # PostgreSQL (prod)

# Authentication
JWT_SECRET_KEY=your-jwt-secret-key      # JWT signing key
JWT_EXPIRATION_HOURS=1                  # Token expiration
JWT_REFRESH_HOURS=24                    # Refresh token validity

# OpenAI API
OPENAI_API_KEY=sk-...                   # Your OpenAI API key
OPENAI_MODEL=gpt-4                      # LLM model to use
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# ChromaDB Configuration
CHROMADB_PERSIST_DIRECTORY=./chromadb_hr # Vector DB location
CHROMADB_HOST=localhost                 # For remote ChromaDB
CHROMADB_PORT=8000

# Redis Configuration (Optional)
REDIS_URL=redis://localhost:6379/0      # Cache backend
REDIS_PASSWORD=                         # Redis password

# Email Configuration
SMTP_HOST=smtp.gmail.com                # Email provider
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=noreply@company.com

# Slack Integration
SLACK_BOT_TOKEN=xoxb-...                # Slack bot token
SLACK_SIGNING_SECRET=...                # Slack signing secret

# Microsoft Teams Integration
TEAMS_BOT_APP_ID=...
TEAMS_BOT_PASSWORD=...

# External HRIS Systems
BAMBOOHR_API_KEY=...                    # BambooHR API key
WORKDAY_TENANT_ID=...                   # Workday tenant
WORKDAY_CLIENT_ID=...
WORKDAY_CLIENT_SECRET=...

# Logging Configuration
LOG_LEVEL=INFO                          # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                         # json or text
SENTRY_DSN=                             # Error tracking (optional)

# Rate Limiting
RATE_LIMIT_REQUESTS=60                  # Requests per minute
RATE_LIMIT_WINDOW=60                    # Time window in seconds

# Feature Flags
ENABLE_AI_QUERY=True                    # Enable AI query endpoint
ENABLE_DOCUMENT_GENERATION=True         # Enable document generation
ENABLE_ANALYTICS_EXPORT=True            # Enable CSV exports
FEATURE_BETA_ANALYTICS=False            # Beta features

# Application URLs
FRONTEND_URL=http://localhost:3000      # Frontend URL
API_BASE_URL=http://localhost:5000      # API base URL
```

### For Testing
```bash
# Test Database
DATABASE_URL=sqlite:///:memory:         # In-memory DB for tests

# Test Email
SMTP_HOST=localhost                     # Use MailHog (docker run -p 1025:1025 mailhog)
```

---

## Docker Setup (Recommended)

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f app

# Stop services
docker-compose down

# Rebuild images
docker-compose build --no-cache
```

### Services Included
- **Flask App** (port 5000)
- **PostgreSQL** (port 5432)
- **ChromaDB** (port 8000)
- **Redis** (port 6379)
- **Nginx** (port 80/443)

### Docker Development Commands
```bash
# Interactive Python shell
docker-compose exec app python

# Run migrations
docker-compose exec app alembic upgrade head

# Seed database
docker-compose exec app python scripts/seed_database.py

# Run tests
docker-compose exec app pytest

# Access PostgreSQL
docker-compose exec db psql -U postgres -d hr_platform
```

---

## Running Tests

### Unit Tests
```bash
# Run all unit tests
pytest tests/unit -v

# Run specific test file
pytest tests/unit/test_auth.py -v

# Run with coverage
pytest tests/unit --cov=src --cov-report=html
```

### Integration Tests
```bash
# Run integration tests
pytest tests/integration -v

# Run against specific database
DATABASE_URL=sqlite:///:memory: pytest tests/integration -v
```

### End-to-End Tests (Playwright)
```bash
# Run all E2E tests
pytest tests/e2e -v

# Run in headed mode (see browser)
pytest tests/e2e -v --headed

# Run specific browser
pytest tests/e2e -v --chromium  # or --firefox, --webkit

# Debug mode
pytest tests/e2e -v --debug
```

### Test Coverage Report
```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html tests/

# Open report
open htmlcov/index.html  # macOS
# or your preferred browser
```

---

## Database Migrations

### Creating New Migrations

```bash
# Auto-generate migration (detects model changes)
alembic revision --autogenerate -m "Add new_column to employees"

# Manual migration
alembic revision -m "Custom migration description"
```

### Applying Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Upgrade to specific version
alembic upgrade 2026_02_14_001_initial_schema

# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade 2026_02_13_001_previous_schema

# Check current version
alembic current

# See migration history
alembic history
```

### Migration Best Practices
1. Always test migrations locally first
2. Write both upgrade and downgrade paths
3. Use descriptive names
4. Keep migrations small and focused
5. Never modify historical migrations
6. Test rollback scenarios

---

## Project Structure Explanation

```
src/
├── app.py / app_v2.py         Main Flask application
├── agents/                      AI agents implementation
│   ├── router_agent.py         Main orchestrator
│   ├── leave_agent.py          Leave operations
│   ├── policy_agent.py         Policy lookup
│   └── ...
├── api/                         REST API endpoints
│   ├── admin_routes.py
│   ├── export_routes.py
│   └── routes/
├── core/                        Core services
│   ├── database.py             SQLAlchemy models
│   ├── cache.py                Caching
│   ├── rag_system.py           RAG implementation
│   └── ...
├── middleware/                  Request middleware
│   ├── auth.py
│   ├── sanitizer.py
│   └── rate_limiter.py
├── repositories/                Data access
├── services/                    Business logic
└── platform_services/           Platform features

tests/
├── unit/                        Unit tests
├── integration/                 Integration tests
└── e2e/                         End-to-end tests

config/
├── settings.py                 Base configuration
├── settings_dev.py             Development config
└── settings_prod.py            Production config

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   └── App.tsx
└── package.json

migrations/                      Database migrations
scripts/                         Utility scripts
docs/                           Documentation
```

---

## Adding New Endpoints

### 1. Create Route Handler

**File:** `src/api/routes/new_routes.py`
```python
from flask import Blueprint, jsonify, request, g
from src.core.database import Session
from src.repositories.base_repository import BaseRepository

new_bp = Blueprint('new', __name__, url_prefix='/api/v2')

@new_bp.route('/resource', methods=['GET'])
def get_resources():
    """Get all resources.
    
    Response:
        {
            "success": true,
            "resources": [...]
        }
    """
    session = Session()
    try:
        # Your logic here
        return jsonify({
            "success": True,
            "resources": []
        }), 200
    finally:
        session.close()

@new_bp.route('/resource/<int:resource_id>', methods=['PUT'])
def update_resource(resource_id):
    """Update a specific resource."""
    data = request.get_json()
    # Validation
    if not data.get('name'):
        return jsonify({
            "success": False,
            "error": "name is required"
        }), 400
    
    # Logic
    return jsonify({
        "success": True,
        "message": "Resource updated"
    }), 200
```

### 2. Register Blueprint in Main App

**File:** `src/app_v2.py`
```python
from src.api.routes.new_routes import new_bp

app.register_blueprint(new_bp)
```

### 3. Add Tests

**File:** `tests/unit/test_new_routes.py`
```python
import pytest
from src.app_v2 import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_resources(client):
    response = client.get('/api/v2/resource')
    assert response.status_code == 200
    assert response.json['success'] == True
```

---

## Adding New Agents

### 1. Extend BaseAgent

**File:** `src/agents/custom_agent.py`
```python
from src.agents.base_agent import BaseAgent
from typing import Dict, Any

class CustomAgent(BaseAgent):
    """Custom agent for specific HR operations."""
    
    def __init__(self):
        super().__init__()
        self.agent_type = "custom"
        self.description = "Handles custom HR operations"
    
    def can_handle(self, query: str) -> bool:
        """Determine if agent can handle query."""
        keywords = ["custom", "operation", "specific"]
        return any(keyword in query.lower() for keyword in keywords)
    
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process the query."""
        # Your agent logic here
        response = self.llm_call(
            prompt=self._build_prompt(query, context),
            functions=self._get_functions()
        )
        
        return {
            "response": response,
            "agent": self.agent_type,
            "confidence": 0.95
        }
    
    def _build_prompt(self, query: str, context: Dict) -> str:
        """Build LLM prompt."""
        return f"""
        You are a helpful HR assistant.
        
        Query: {query}
        Context: {context}
        
        Please provide a helpful response.
        """
    
    def _get_functions(self) -> list:
        """Define functions the agent can call."""
        return [
            {
                "name": "get_custom_data",
                "description": "Get custom HR data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "data_type": {"type": "string"}
                    }
                }
            }
        ]
```

### 2. Register Agent in Router

**File:** `src/agents/router_agent.py`
```python
from src.agents.custom_agent import CustomAgent

self.agents = [
    # ... existing agents
    CustomAgent(),
]
```

### 3. Add Tests

**File:** `tests/unit/test_custom_agent.py`
```python
from src.agents.custom_agent import CustomAgent

def test_can_handle():
    agent = CustomAgent()
    assert agent.can_handle("Tell me about custom operation")
    assert not agent.can_handle("Leave request")

def test_process():
    agent = CustomAgent()
    result = agent.process("What's the status?", {})
    assert result['agent'] == 'custom'
```

---

## Database Model Changes

### 1. Modify Model

**File:** `src/core/database.py`
```python
class Employee(Base, TimestampMixin):
    __tablename__ = "employees"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    # ... existing fields ...
    
    # New field
    remote_status: Mapped[str] = mapped_column(
        String(50), 
        default="onsite",
        nullable=False
    )
```

### 2. Create Migration

```bash
# Auto-generate migration
alembic revision --autogenerate -m "Add remote_status to employees"

# Review generated migration in migrations/versions/
```

### 3. Test Migration

```bash
# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Run migrations
alembic upgrade head
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing (`pytest`)
- [ ] Code linting (`flake8 src/`)
- [ ] Type checking (`mypy src/`)
- [ ] Security scan (`bandit -r src/`)
- [ ] Database migrations reviewed
- [ ] Environment variables configured
- [ ] API documentation updated

### Staging Deployment
```bash
# Build Docker image
docker build -t hr-platform:latest .

# Tag for registry
docker tag hr-platform:latest registry.example.com/hr-platform:v1.0.0

# Push to registry
docker push registry.example.com/hr-platform:v1.0.0

# Deploy to staging
kubectl apply -f k8s/staging/

# Verify deployment
kubectl get pods -n staging
kubectl logs -n staging deployment/hr-platform
```

### Production Deployment
```bash
# Create backup
pg_dump $DATABASE_URL > backup.sql

# Deploy (blue-green deployment)
kubectl apply -f k8s/production/

# Monitor rollout
kubectl rollout status deployment/hr-platform -n production

# Check health
curl https://api.hr-platform.com/api/v2/health

# Verify data
# - Check key metrics in dashboard
# - Run smoke tests
# - Monitor error rates
```

### Post-Deployment
- [ ] Health checks passing
- [ ] Monitor error rates (should be <0.1%)
- [ ] Check response times (p99 < 2s)
- [ ] Database connections normal
- [ ] Logs clean (no errors)
- [ ] Notify stakeholders

---

## Development Tools

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/ --max-line-length=120

# Type checking
mypy src/ --ignore-missing-imports

# All checks
./scripts/check_code_quality.sh
```

### Debugging

```bash
# Start debugger
python -m pdb src/app_v2.py

# Or with VS Code
# 1. Set breakpoints with red dot
# 2. Run Debug → Start Debugging
# 3. Use Debug Console
```

### API Testing

```bash
# Using curl
curl -H "Authorization: Bearer $TOKEN" \
     -X GET http://localhost:5000/api/v2/profile

# Using HTTPie
http GET http://localhost:5000/api/v2/profile \
    Authorization:"Bearer $TOKEN"

# Using Postman
# Import postman-collection.json
# Set environment variables
# Run requests
```

### Database Inspection

```bash
# SQLite
sqlite3 hr_platform.db

# PostgreSQL
psql -U postgres -d hr_platform

# SQLAlchemy ORM
python
>>> from src.core.database import Session, Employee
>>> session = Session()
>>> employees = session.query(Employee).all()
>>> print(employees)
```

---

## Common Development Tasks

### Creating a New Feature

1. Create feature branch: `git checkout -b feature/feature-name`
2. Add/modify code
3. Write tests
4. Test locally: `pytest`
5. Format and lint: `black src/ && flake8 src/`
6. Commit: `git commit -m "Add feature description"`
7. Push: `git push origin feature/feature-name`
8. Open Pull Request

### Debugging Agent Responses

```python
# In your code
from src.agents.router_agent import RouterAgent

router = RouterAgent()
result = router.process("User query", {})

print("Agent Selection:", result.get('agent'))
print("Response:", result.get('response'))
print("Confidence:", result.get('confidence'))
print("Tools Used:", result.get('tools'))
```

### Inspecting RAG Pipeline

```python
from src.core.rag_system import RAGSystem

rag = RAGSystem()

# Retrieve documents
documents = rag.retrieve("policy query", top_k=5)
for doc in documents:
    print(f"Document: {doc['title']}")
    print(f"Relevance: {doc['score']}")
    print(f"Content: {doc['text'][:200]}...")
```

---

## Performance Optimization

### Database Query Optimization

```python
# Bad: N+1 queries
employees = session.query(Employee).all()
for emp in employees:
    print(emp.manager.name)  # Extra query per employee!

# Good: Use eager loading
from sqlalchemy.orm import joinedload
employees = session.query(Employee).options(
    joinedload(Employee.manager)
).all()
```

### Caching

```python
from src.core.cache import Cache

cache = Cache()

# Set cache
cache.set("key", value, ttl=300)

# Get cache
value = cache.get("key")

# Delete cache
cache.delete("key")
```

### Response Optimization

```python
# Limit fields in response
response = {
    "id": emp.id,
    "email": emp.email,
    "first_name": emp.first_name
    # Don't include large objects like password_hash
}
```

---

## Troubleshooting

### Common Issues

**Issue:** `ModuleNotFoundError: No module named 'src'`
```bash
# Solution: Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Issue:** Port 5000 already in use
```bash
# Solution: Find and kill process
lsof -i :5000  # macOS/Linux
tasklist | findstr PYTHON  # Windows
kill -9 <PID>
```

**Issue:** Database locked error
```bash
# Solution: Remove lock file
rm hr_platform.db-shm
rm hr_platform.db-wal
```

**Issue:** ChromaDB connection refused
```bash
# Solution: Start ChromaDB service
docker run -p 8000:8000 chromadb/chroma

# Or check if already running
curl http://localhost:8000/
```

**Issue:** OpenAI API rate limiting
```bash
# Solution: Add retry logic
import time
from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=2, max=10))
def call_openai_api():
    # Your API call
    pass
```

---

## IDE Setup

### VS Code Extensions
- Python (Microsoft)
- Pylance (Microsoft)
- Flask Snippets
- Thunder Client (API testing)
- Git Graph

### VS Code Settings (.vscode/settings.json)
```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
    "[python]": {
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": true
        }
    }
}
```

### PyCharm Setup
1. Open project
2. Configure interpreter: Preferences → Project → Python Interpreter → Add → Existing Environment → venv/bin/python
3. Enable Django integration: Preferences → Languages & Frameworks → Django
4. Configure test runner: Preferences → Tools → Python Integrated Tools → Default test runner → pytest

---

## Resources

- API Docs: `/docs/API_REFERENCE.md`
- Architecture: `/docs/ARCHITECTURE.md`
- User Guide: `/docs/USER_GUIDE.md`
- OpenAI Documentation: https://platform.openai.com/docs
- ChromaDB Documentation: https://docs.trychroma.com
- Flask Documentation: https://flask.palletsprojects.com
- SQLAlchemy Documentation: https://docs.sqlalchemy.org
- Alembic Documentation: https://alembic.sqlalchemy.org


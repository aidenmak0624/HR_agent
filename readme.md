# Multi-Agent HR Intelligence Platform

Enterprise-grade multi-agent AI system for autonomous HR operations, powered by LangGraph and OpenAI GPT-4.

**Status:** Production Ready
**Version:** 1.0.0
**Development Iterations:** 8
**Production Modules:** 101
**Unit Tests:** 1,909

## Overview

The Multi-Agent HR Intelligence Platform is a sophisticated AI-driven system designed to automate and enhance HR operations across organizations. Built with Python, Flask, and LangGraph, it orchestrates multiple specialized AI agents to handle complex HR tasks while maintaining strict compliance with global data protection regulations.

### Key Features

- **Multi-Agent Orchestration**: 8 specialized agents (Policy, Benefits, Leave, Employee, Onboarding, Performance, Compliance, Analytics)
- **Enterprise HRIS Integration**: Native connectors for Workday, BambooHR, and custom HR systems
- **Global Compliance**: GDPR, CCPA, HIPAA, and multi-jurisdiction support
- **Intelligent RAG**: Retrieval-Augmented Generation for policy-aware responses
- **Real-time Notifications**: Slack and Microsoft Teams channel adapters
- **Advanced Security**: PII detection, rate limiting, encryption, audit logging
- **Production Observability**: Prometheus metrics, Grafana dashboards, LangSmith tracing
- **Scalable Architecture**: Containerized with Docker, async processing, Redis caching

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend UI                              │
│                  (Web Dashboard + Chat Interface)                │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                      REST API Gateway                            │
│         (Health Checks, Chat, Admin, Export Routes)             │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                      Router Agent                                │
│                  (Request Classification)                        │
└──┬─┬────┬────┬────┬────┬────┬───────────────────────────────────┘
   │ │    │    │    │    │    │
┌──▼─▼─┐┌──▼─┐┌──▼─┐┌──▼─┐┌──▼─┐┌──▼───┐┌──────────┐
│Policy││Bene││Leave││Empl││Onbo││Perfo││Complian-│
│Agent ││fits││Agent││oyee││ardi││rmance││ce Agent │
│      ││Agnt││     ││Agent││ng A││Agent │└──────────┘
└──┬───┘└────┘└─────┘└────┘└────┘└──────┘
   │
┌──▼─────────────────────────────────────────────────────────────┐
│                    Core Services Layer                          │
├──────────────────────────────────────────────────────────────┤
│  • RAG Engine (ChromaDB + Sentence Transformers)            │
│  • LLM Gateway (OpenAI GPT-4 + Gemini Fallback)             │
│  • HRIS Connectors (Workday, BambooHR, Custom DB)           │
│  • Compliance Engine (GDPR, CCPA, Multi-Jurisdiction)       │
│  • PII Detector & Masker                                     │
│  • Bias Audit Logger                                         │
│  • Document Generator (Jinja2 + Templates)                  │
└──┬───────────────────────────────────────────────────────────┘
   │
┌──▼──────────────────────────────────────────────────────────────┐
│                  Persistence & Infrastructure                   │
├───────────────────────────────────────────────────────────────┤
│  PostgreSQL (Employee Data, Conversations, Audit Logs)       │
│  Redis (Caching, Session Management)                         │
│  ChromaDB (Vector Embeddings for RAG)                        │
│  Prometheus (Metrics Collection)                             │
│  Grafana (Dashboard & Visualization)                         │
└────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
HR_agent/
├── src/                              # Production source code
│   ├── agent/                        # Original LangGraph agent core
│   ├── agents/                       # Multi-agent system (8 specialized agents)
│   ├── api/                          # REST API routes (admin, health, export, chat)
│   ├── channels/                     # Slack/Teams channel adapters
│   ├── connectors/                   # HRIS integrations (Workday, BambooHR, payroll)
│   ├── core/                         # Core services (RAG, LLM, compliance, security)
│   ├── integrations/                 # Slack/Teams bot implementations
│   ├── middleware/                   # Security middleware (rate limiting, PII, auth)
│   ├── platform/                     # Platform services (dashboard, SLA, audit, costs)
│   ├── repositories/                 # Data access layer (users, conversations, etc.)
│   └── services/                     # Business logic (agent orchestration, LLM)
│
├── tests/                            # Test suite (1,909 unit tests)
│   ├── unit/                         # Unit tests by iteration
│   ├── integration/                  # Integration tests
│   └── fixtures/                     # Test data and mocks
│
├── config/                           # Configuration management
│   ├── settings.py                   # Pydantic settings with validation
│   └── logging.py                    # Structured logging configuration
│
├── scripts/                          # Automation and utility scripts
│   ├── setup.sh                      # Initial environment setup
│   ├── system_demo.py                # Demonstration of all agents
│   ├── generate_schema_docs.py       # API documentation generator
│   └── db_migrate.sh                 # Database migration runner
│
├── frontend/                         # Web UI and templates
│   ├── templates/                    # HTML/Jinja2 templates
│   └── static/                       # CSS, JavaScript, assets
│
├── migrations/                       # Alembic database migrations
│   └── versions/                     # Migration scripts by version
│
├── docs/                             # Project documentation
│   ├── API.md                        # Complete API reference
│   ├── AGENTS.md                     # Agent specifications and workflows
│   ├── COMPLIANCE.md                 # Regulatory compliance details
│   └── DEPLOYMENT.md                 # Deployment and infrastructure guide
│
├── iteration_1-8/                    # Development iteration records
│   ├── iteration_1_foundation/       # Auth, RBAC, 7 core agents, RAG
│   ├── iteration_2_advanced/         # Leave workflows, GDPR, bias audit
│   ├── iteration_3_persistence/      # Database layer, Flask integration
│   ├── iteration_4_llm/              # OpenAI gateway, multi-model support
│   ├── iteration_5_devops/           # CI/CD, Slack/Teams bots, memory
│   ├── iteration_6_security/         # Rate limiting, PII stripping, metrics
│   ├── iteration_7_compliance/       # CCPA, multi-jurisdiction, WebSocket
│   └── iteration_8_platform/         # Admin API, health checks, audit reports
│
├── legacy_human_rights_edu/          # Original chatbot (preserved for reference)
│
├── docker-compose.yml                # Multi-container orchestration
├── Dockerfile                        # Production image definition
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment template
└── README.md                         # This file
```

## Features by Iteration

### Iteration 1: Foundation (Authentication & Core Agents)
- User authentication and JWT token management
- Role-based access control (RBAC) with 5 permission levels
- 7 specialized agents with tool-based action execution
- RAG system with ChromaDB and policy document indexing
- HRIS connectors (Workday, BambooHR) with sync capabilities
- Basic conversation logging

### Iteration 2: Advanced (Workflows & Compliance)
- Leave request workflows with multi-level approval chains
- GDPR compliance framework (data subject rights, audit trails)
- Bias audit logging for agent decision transparency
- Policy violation detection
- Employee lifecycle management (onboarding, offboarding)
- Email notification system

### Iteration 3: Persistence (Database Layer)
- PostgreSQL schema with 15+ tables
- SQLAlchemy ORM models and repositories
- Alembic migration framework
- Flask integration with database session management
- Full conversation history and audit logging
- Frontend UI rebuild with modern JavaScript

### Iteration 4: LLM (Model Gateway & Multi-Model Support)
- OpenAI GPT-4 integration as primary model
- Google Gemini fallback for resilience
- Model cost tracking and usage analytics
- Streaming response support
- Token counting and cost estimation
- LangSmith integration for agent tracing

### Iteration 5: DevOps (Containerization & Integrations)
- Docker and docker-compose setup
- GitHub Actions CI/CD pipeline
- Slack bot with /hr slash commands
- Microsoft Teams bot with adaptive cards
- Conversation memory with Redis caching
- Environment-specific configurations

### Iteration 6: Security (PII & Metrics)
- PII detection and automatic masking (names, SSNs, emails)
- API rate limiting (default 60 req/min per user)
- Security headers and CORS policies
- Request/response encryption
- Prometheus metrics collection
- Grafana dashboard visualization

### Iteration 7: Compliance (CCPA & Multi-Jurisdiction)
- CCPA (California Consumer Privacy Act) implementation
- Multi-jurisdiction support (US, EU, Canada, Australia)
- Data localization enforcement
- Right to erasure automation
- WebSocket support for real-time updates
- Redis-based response caching

### Iteration 8: Platform (Admin & Enterprise Features)
- Admin API for user and system management
- Health checks (/health/live, /health/ready)
- Feature flags for gradual rollouts
- SLA monitoring and reporting
- Comprehensive audit reports with export
- Data backup and disaster recovery
- Comprehensive feedback system

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Docker & Docker Compose** (for containerized deployment)
- **PostgreSQL 13+** (can use Docker Compose)
- **Redis 6+** (can use Docker Compose)
- **OpenAI API Key** (for GPT-4 models)

### Installation & Setup

**1. Clone the repository:**
```bash
git clone <repository-url>
cd HR_agent
```

**2. Run the setup script:**
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

This script will:
- Verify Python 3.10+ is installed
- Create a virtual environment
- Install all dependencies
- Create necessary directories
- Copy `.env.example` to `.env`

**3. Configure environment variables:**
```bash
# Edit .env with your settings
nano .env

# Key variables to set:
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://user:password@localhost:5432/hr_platform
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

**4. Initialize the database:**
```bash
source venv/bin/activate
cd migrations && alembic upgrade head && cd ..
```

**5. Run the application:**
```bash
# Development mode
python src/app_v2.py

# Production mode (gunicorn)
gunicorn --bind 0.0.0.0:5050 --workers 4 src.app_v2:app
```

The application will be available at `http://localhost:5050`

### Docker Deployment

**Quick start with Docker Compose:**
```bash
# Create .env file with your configuration
cp .env.example .env
nano .env  # Update with your API keys

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Run database migrations (one-time)
docker-compose exec app alembic upgrade head

# Stop all services
docker-compose down
```

Services started:
- PostgreSQL on port 5432
- Redis on port 6379
- Application on port 5050

## Configuration

All configuration is managed via environment variables. See `.env.example` for complete reference.

### Core Settings

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/hr_platform

# Cache
REDIS_URL=redis://localhost:6379/0

# Security
JWT_SECRET=your-generated-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# LLM Configuration
OPENAI_API_KEY=sk-your-api-key
LLM_DEFAULT_MODEL=gpt-4o-mini
LLM_PREMIUM_MODEL=gpt-4o
LLM_TEMPERATURE=0.1

# HRIS Integration
HRIS_PROVIDER=bamboohr
BAMBOOHR_API_KEY=your-api-key
BAMBOOHR_SUBDOMAIN=your-company

# Feature Flags
PII_ENABLED=true
BIAS_AUDIT_ENABLED=true
DOCUMENT_GENERATION_ENABLED=true

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60

# Application
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production
PORT=5050
```

## API Reference

### Core Endpoints

**Chat & Messages**
```
POST /api/v2/chat
  Request a message from the HR agent system
  Body: { "message": "...", "user_id": "..." }
  Response: { "response": "...", "agent": "...", "confidence": 0.95 }

GET /api/v2/conversations/{conversation_id}
  Retrieve conversation history

DELETE /api/v2/conversations/{conversation_id}
  Delete a conversation and its data
```

**Health & Monitoring**
```
GET /health
  Quick health check (200 OK)

GET /health/live
  Liveness probe (readiness check)

GET /health/ready
  Readiness probe (dependencies check)

GET /metrics
  Prometheus metrics endpoint
```

**Admin Operations**
```
GET /api/v2/admin/users
  List all users (admin only)

POST /api/v2/admin/users
  Create new user (admin only)

GET /api/v2/admin/audit
  Retrieve audit log (admin only)

POST /api/v2/admin/feature-flags
  Manage feature flags (admin only)
```

**Data Export**
```
POST /api/v2/export
  Export data (conversations, audit logs, etc.)
  Body: { "data_type": "conversations", "format": "csv" }
```

For complete API documentation, see `/docs/API.md`

## Testing

### Run All Tests
```bash
# Activate virtual environment
source venv/bin/activate

# Run all unit tests with coverage
python -m pytest tests/unit/ -v --cov=src --cov-report=html

# Run specific iteration tests
python -m pytest tests/unit/test_iteration_7_ccpa.py -v

# Run integration tests
python -m pytest tests/integration/ -v

# Run system demonstration
python scripts/system_demo.py
```

### Test Organization

Tests are organized by iteration matching development history:
- `test_iteration_1_foundation.py` - Auth, agents, RAG
- `test_iteration_2_advanced.py` - Leave workflows, GDPR
- `test_iteration_3_persistence.py` - Database operations
- `test_iteration_4_llm.py` - Model gateway, streaming
- `test_iteration_5_devops.py` - Docker, CI/CD
- `test_iteration_6_security.py` - PII, rate limiting
- `test_iteration_7_compliance.py` - CCPA, multi-jurisdiction
- `test_iteration_8_platform.py` - Admin API, audit reports

## Monitoring & Observability

### Prometheus Metrics

Access metrics at `http://localhost:5050/metrics`

Key metrics:
- `hr_agent_requests_total` - Total API requests
- `hr_agent_request_duration_seconds` - Request latency
- `hr_agent_llm_tokens_used_total` - LLM token consumption
- `hr_agent_cache_hits_total` - Cache hit rate
- `hr_agent_pii_detections_total` - PII instances detected

### Grafana Dashboards

Pre-built dashboards in `grafana/` directory:
- System Performance Dashboard
- Agent Activity Dashboard
- Compliance & Audit Dashboard
- Cost Analysis Dashboard
- Error & Anomaly Detection

### LangSmith Integration (Optional)

Enable agent tracing for debugging:
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=hr-multi-agent
```

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Language** | Python | 3.10+ |
| **Web Framework** | Flask | 3.0.0 |
| **Agent Framework** | LangGraph | 0.2.16 |
| **LLM Provider** | OpenAI | 1.58.1 |
| **Vector DB** | ChromaDB | 0.4.22 |
| **SQL ORM** | SQLAlchemy | 2.0.23 |
| **Database** | PostgreSQL | 15+ |
| **Cache** | Redis | 7+ |
| **Monitoring** | Prometheus | Latest |
| **Visualization** | Grafana | Latest |
| **Container** | Docker | 20.10+ |
| **Orchestration** | Docker Compose | 2.0+ |

## Deployment

### Production Checklist

- [ ] Set `DEBUG=false` in environment
- [ ] Generate secure JWT secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Configure PostgreSQL with backups enabled
- [ ] Set up Redis with persistence (AOF)
- [ ] Configure CORS origins for your domain
- [ ] Enable HTTPS/TLS for all connections
- [ ] Set up monitoring and alerting
- [ ] Configure log aggregation (ELK, Datadog, etc.)
- [ ] Enable LangSmith tracing for debugging
- [ ] Test disaster recovery procedures

### Scaling Considerations

- **Horizontal**: Use multiple gunicorn workers (default 4)
- **Vertical**: Increase CPU/memory for agent processing
- **Database**: Enable PostgreSQL replication for high availability
- **Cache**: Use Redis Cluster for distributed caching
- **Load Balancing**: Deploy behind Nginx or cloud load balancer

## License

MIT License - See LICENSE file for details

## Support & Documentation

- **API Documentation**: `/docs/API.md`
- **Agent Specifications**: `/docs/AGENTS.md`
- **Compliance Guide**: `/docs/COMPLIANCE.md`
- **Deployment Guide**: `/docs/DEPLOYMENT.md`
- **Development**: See `iteration_1-8/` for historical development records

## Contributing

Please follow these guidelines:
1. Create feature branches from `main`
2. Write tests for all new functionality
3. Ensure all tests pass: `pytest tests/ -v`
4. Follow PEP 8 style guide: `flake8 src/`
5. Format code with Black: `black src/`
6. Submit pull request with description

---

**Last Updated:** February 2025
**Maintained By:** HR Intelligence Team

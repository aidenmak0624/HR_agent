# Multi-Agent HR Intelligence Platform

Enterprise-grade multi-agent AI system for autonomous HR operations, powered by LangGraph and OpenAI GPT-4.

**Status:** Production Ready &nbsp;|&nbsp; **Version:** 1.0.0 &nbsp;|&nbsp; **Modules:** 101 &nbsp;|&nbsp; **Unit Tests:** 1,909

---

## Showcase

> Open these HTML files in your browser to see the platform in action:

| Demo | Description |
|------|-------------|
| [**Business Case**](showcase/showcase_business.html) | ROI analysis, 24/7 global coverage, compliance value, cost savings breakdown |
| [**Developer Showcase**](showcase/showcase_developer.html) | Architecture deep-dive, tech stack, code quality metrics, testing strategy |
| [**Vibe Coding Journey**](showcase/showcase_vibe_coding.html) | AI-assisted development story — Claude Code + Copilot workflow, build timeline, learnings |
| [**Architecture Report**](showcase/Agent_Architecture_Report.html) | Visual multi-agent system design and data flows |
| [**Platform Comparison**](showcase/HR_Agent_Comparison_Report.html) | Competitive analysis against leading HR AI platforms |
| [**Test Report (PDF)**](showcase/Playwright_Testing_Report.pdf) | End-to-end browser testing results with screenshots |

---

## Overview

The Multi-Agent HR Intelligence Platform orchestrates 8 specialized AI agents to automate HR operations — from policy Q&A and leave management to compliance auditing and workforce analytics. Built with Python, Flask, and LangGraph, it maintains strict compliance with GDPR, CCPA, and HIPAA across multiple jurisdictions.

### Key Features

- **Multi-Agent Orchestration** — 8 specialized agents (Policy, Benefits, Leave, Employee, Onboarding, Performance, Compliance, Analytics)
- **Enterprise HRIS Integration** — Native connectors for Workday, BambooHR, and custom HR systems
- **Global Compliance** — GDPR, CCPA, HIPAA, and multi-jurisdiction support
- **Intelligent RAG** — Retrieval-Augmented Generation with ChromaDB for policy-aware responses
- **Real-time Notifications** — Slack and Microsoft Teams channel adapters
- **Advanced Security** — PII detection & masking, rate limiting, encryption, audit logging
- **Production Observability** — Prometheus metrics, Grafana dashboards, LangSmith tracing
- **Scalable Architecture** — Containerized with Docker, async processing, Redis caching

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Frontend UI                             │
│               (Web Dashboard + Chat Interface)               │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                    REST API Gateway                          │
│        (Health Checks, Chat, Admin, Export Routes)           │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                     Router Agent                             │
│                (Request Classification)                      │
└──┬────┬────┬────┬────┬────┬────┬─────────────────────────────┘
   │    │    │    │    │    │    │
   ▼    ▼    ▼    ▼    ▼    ▼    ▼
 Policy Benefits Leave Employee Onboard Perform Compliance
 Agent   Agent  Agent  Agent    Agent   Agent    Agent
   │
┌──▼───────────────────────────────────────────────────────────┐
│                   Core Services Layer                        │
├──────────────────────────────────────────────────────────────┤
│  RAG Engine (ChromaDB + Sentence Transformers)               │
│  LLM Gateway (OpenAI GPT-4 + Gemini Fallback)               │
│  HRIS Connectors (Workday, BambooHR, Custom DB)              │
│  Compliance Engine (GDPR, CCPA, Multi-Jurisdiction)          │
│  PII Detector & Masker  ·  Bias Audit Logger                 │
│  Document Generator (Jinja2 + Templates)                     │
└──┬───────────────────────────────────────────────────────────┘
   │
┌──▼───────────────────────────────────────────────────────────┐
│               Persistence & Infrastructure                   │
├──────────────────────────────────────────────────────────────┤
│  PostgreSQL · Redis · ChromaDB · Prometheus · Grafana         │
└──────────────────────────────────────────────────────────────┘
```

## Project Structure

```
HR_agent/
├── showcase/                    ★ Demo reports — open in browser
│   ├── HR_AI_Business_Showcase.html
│   ├── Agent_Architecture_Report.html
│   ├── HR_Agent_Comparison_Report.html
│   └── Playwright_Testing_Report.pdf
│
├── src/                         Application source code
│   ├── agents/                    8 specialized AI agents
│   ├── api/                       REST API routes
│   ├── core/                      RAG, LLM, compliance, security
│   ├── connectors/                HRIS integrations (Workday, BambooHR)
│   ├── middleware/                Rate limiting, PII, auth
│   ├── platform_services/         Dashboard, SLA, audit, costs
│   ├── repositories/              Data access layer
│   └── services/                  Business logic & orchestration
│
├── frontend/                    Web UI
│   ├── templates/                 HTML/Jinja2 templates
│   └── static/                    CSS, JavaScript
│
├── tests/                       Test suite (1,909 unit tests)
│   ├── unit/                      Unit tests by iteration
│   ├── integration/               Integration tests
│   ├── playwright/                Browser E2E tests
│   └── e2e/                       End-to-end tests
│
├── docs/                        Documentation
│   ├── guides/                    Setup & deployment guides
│   ├── planning/                  Feature specs & implementation
│   ├── testing/                   Test reports & verification
│   ├── development-history/       Iteration-by-iteration progress
│   ├── ARCHITECTURE.md            System architecture deep-dive
│   ├── API_REFERENCE.md           Complete API reference
│   ├── DEVELOPER_GUIDE.md         Developer onboarding guide
│   └── USER_GUIDE.md              End-user guide
│
├── config/                      Configuration management
├── scripts/                     Utility & automation scripts
├── deploy/                      Cloud deployment configs (AWS, GCP)
├── data/                        Knowledge base & HR policies
├── migrations/                  Alembic database migrations
├── reports/                     Engineering reports
├── grafana/                     Grafana dashboard definitions
│
├── docker-compose.yml           Multi-container orchestration
├── Dockerfile                   Production image
├── Makefile                     Common dev commands
├── requirements.txt             Python dependencies
└── .env.example                 Environment variable template
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- OpenAI API Key

### Option 1: Docker (Recommended)

```bash
git clone <repository-url>
cd HR_agent
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

docker-compose up -d
# App available at http://localhost:5050
```

### Option 2: Local Development

```bash
git clone <repository-url>
cd HR_agent
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Configure environment
cp .env.example .env
nano .env  # Set OPENAI_API_KEY, DATABASE_URL, etc.

# Initialize database & run
source venv/bin/activate
alembic upgrade head
python src/app_v2.py
# App available at http://localhost:5050
```

### Default Login Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@company.com | admin123 |
| HR Manager | hr@company.com | hr123 |
| Employee | employee@company.com | emp123 |

## Testing

```bash
# All unit tests with coverage
python -m pytest tests/unit/ -v --cov=src --cov-report=html

# Integration tests
python -m pytest tests/integration/ -v

# Browser E2E tests (requires Playwright)
npx playwright test

# System demonstration
python scripts/system_demo.py
```

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Web Framework | Flask 3.0 |
| Agent Framework | LangGraph 0.2 |
| LLM | OpenAI GPT-4 (+ Gemini fallback) |
| Vector DB | ChromaDB |
| SQL ORM | SQLAlchemy 2.0 |
| Database | PostgreSQL 15+ |
| Cache | Redis 7+ |
| Monitoring | Prometheus + Grafana |
| Containers | Docker + Docker Compose |
| E2E Testing | Playwright |

## Development History

This platform was built across 8 iterative development cycles:

1. **Foundation** — Auth, RBAC, 7 core agents, RAG system, HRIS connectors
2. **Workflows** — Leave approval chains, GDPR framework, bias audit logging
3. **Persistence** — PostgreSQL schema, SQLAlchemy ORM, Flask integration
4. **LLM Gateway** — OpenAI GPT-4, Gemini fallback, cost tracking, streaming
5. **DevOps** — Docker, CI/CD, Slack/Teams bots, conversation memory
6. **Security** — PII detection/masking, rate limiting, Prometheus metrics
7. **Compliance** — CCPA, multi-jurisdiction, data localization, WebSocket
8. **Platform** — Admin API, health checks, feature flags, SLA monitoring

See [`docs/development-history/`](docs/development-history/) for detailed iteration records.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design and component overview
- [API Reference](docs/API_REFERENCE.md) — Complete REST API documentation
- [Developer Guide](docs/DEVELOPER_GUIDE.md) — Setup, coding standards, contribution guide
- [User Guide](docs/USER_GUIDE.md) — End-user documentation
- [Deployment Guide](docs/guides/DEPLOYMENT.md) — Production deployment instructions

## License

MIT License — See LICENSE file for details.

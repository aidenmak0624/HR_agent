# Multi-Agent HR Intelligence Platform

> Enterprise-grade multi-agent AI system for autonomous HR operations — built with LangGraph, GPT-4, and a whole lot of vibe coding.

**[Live Demo](https://hr-platform-837558695367.us-central1.run.app)** · **Python 77.6%** · **101 Modules** · **1,909 Tests** · **8 AI Agents**

---

## What Is This?

An AI-powered HR platform that orchestrates **8 specialized agents** to handle policy Q&A, leave management, benefits enrollment, compliance auditing, workforce analytics, and more. Each agent owns a domain, and a router agent classifies incoming requests and delegates to the right specialist.

Built almost entirely through **AI-assisted "vibe coding"** with Claude Code and GitHub Copilot — then hardened with 1,909 unit tests, Playwright E2E testing, and production deployment on Google Cloud Run.

### Architecture

```
                         ┌─────────────────┐
                         │   Web UI / Chat  │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │   REST API GW   │
                         └────────┬────────┘
                                  │
                         ┌────────▼────────┐
                         │  Router Agent   │
                         └──┬──┬──┬──┬──┬─┘
                            │  │  │  │  │
              ┌─────────────┼──┼──┼──┼──┼─────────────┐
              ▼             ▼  ▼  ▼  ▼  ▼             ▼
           Policy      Benefits Leave Employee   Compliance
           Agent        Agent  Agent   Agent       Agent
              │             │              │
              └─────────────┴──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │     Core Services Layer     │
              │  RAG · LLM GW · PII Mask  │
              │  HRIS · Compliance · Docs  │
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  PostgreSQL · Redis · Chroma │
              └────────────────────────────┘
```

## Key Features

- **Multi-Agent Orchestration** — 8 specialized agents via LangGraph with intelligent routing
- **Enterprise HRIS Integration** — Workday, BambooHR, and custom system connectors
- **Global Compliance** — GDPR, CCPA, HIPAA, multi-jurisdiction support
- **RAG-Powered Responses** — ChromaDB + Sentence Transformers for policy-aware answers
- **PII Detection & Masking** — Automatic sensitive data protection across all agent responses
- **Production Observability** — Prometheus metrics, Grafana dashboards, LangSmith tracing
- **Real-time Notifications** — Slack and Microsoft Teams channel adapters

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.10+, Flask 3.0, LangGraph 0.2 |
| **AI/ML** | OpenAI GPT-4, Gemini fallback, ChromaDB, Sentence Transformers |
| **Data** | PostgreSQL 15+, Redis 7+, SQLAlchemy 2.0, Alembic |
| **Frontend** | HTML/CSS/JS, Jinja2 templates |
| **Infrastructure** | Docker, Google Cloud Run, Nginx, Prometheus, Grafana |
| **Testing** | Pytest (1,909 tests), Playwright E2E |
| **Dev Tools** | Claude Code, GitHub Copilot, Black, Ruff |

## Quick Start

```bash
# Clone and configure
git clone https://github.com/aidenmak0624/HR_agent.git
cd HR_agent
cp .env.example .env    # Set your OPENAI_API_KEY

# Docker (recommended)
docker-compose up -d    # → http://localhost:5050

# Or local dev
pip install -r requirements.txt
python src/app_v2.py    # → http://localhost:5050
```

**Demo credentials:** `admin@company.com` / `admin123`

## Project Structure

```
├── src/                    Application source code
│   ├── agents/               8 specialized AI agents
│   ├── api/                  REST API routes
│   ├── core/                 RAG, LLM gateway, compliance, security
│   ├── connectors/           HRIS integrations
│   ├── middleware/            Rate limiting, PII masking, auth
│   └── services/             Business logic & orchestration
├── frontend/               Web UI (templates + static assets)
├── tests/                  Test suite (1,909 unit + E2E tests)
├── docs/                   Documentation & development history
├── showcase/               Interactive HTML demo reports
├── config/                 Configuration management
├── deploy/                 Cloud deployment configs
├── scripts/                Utility & automation scripts
└── grafana/                Dashboard definitions
```

## Development Story

This platform was built across **8 iterative development cycles** using AI-assisted development:

1. **Foundation** — Auth, RBAC, 7 core agents, RAG system, HRIS connectors
2. **Workflows** — Leave approval chains, GDPR framework, bias audit logging
3. **Persistence** — PostgreSQL schema, SQLAlchemy ORM, Flask integration
4. **LLM Gateway** — OpenAI GPT-4, Gemini fallback, cost tracking, streaming
5. **DevOps** — Docker, CI/CD, Slack/Teams bots, conversation memory
6. **Security** — PII detection/masking, rate limiting, Prometheus metrics
7. **Compliance** — CCPA, multi-jurisdiction, data localization, WebSocket
8. **Platform** — Admin API, health checks, feature flags, SLA monitoring

See [`docs/iterations/`](docs/iterations/) for detailed records of each cycle.

## Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](docs/ARCHITECTURE.md) | System design and component overview |
| [API Reference](docs/API_REFERENCE.md) | Complete REST API docs |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | Setup, coding standards, contribution guide |

## The Vibe Coding Story

This project started as an experiment in AI-assisted development. Nearly all code was written through conversational pair-programming with **Claude Code** and **GitHub Copilot** — from initial scaffolding to agent logic, test suites, and deployment configs.

Want the full story? Check out the [Vibe Coding Journey](showcase/showcase_vibe_coding.html) showcase, or come see the live demo at **[AI Tinkerers Toronto](https://toronto.aitinkerers.org)**.

## License

MIT

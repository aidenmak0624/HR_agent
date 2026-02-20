# CLAUDE.md — HR Multi-Agent Intelligence Platform

## Quick Reference

- **Language:** Python 3.10+ (CI uses 3.11)
- **Framework:** Flask 3.0 + LangGraph 0.2
- **LLM:** OpenAI GPT-4 (primary), Google Gemini (fallback)
- **Vector DB:** ChromaDB 0.4+
- **Database:** PostgreSQL 15+ (prod), SQLite (dev)
- **ORM:** SQLAlchemy 2.0 with Alembic migrations
- **Cache:** Redis 7+
- **Protocol:** MCP (Model Context Protocol) via FastMCP

## Common Commands

```bash
# Development
make dev              # Flask dev server with hot reload (localhost:5050)
make up               # Docker Compose full stack (localhost:80)
make down             # Stop Docker services

# Testing
make test             # Unit + integration tests (pytest)
make e2e              # Playwright browser tests
pytest tests/unit/ -v --tb=short          # Unit tests only
pytest tests/integration/ -v --tb=short   # Integration tests only
npx playwright test                       # E2E tests directly

# Code Quality
make lint             # Black check + Flake8
black --line-length 100 src/ tests/       # Auto-format
flake8 src/ --max-line-length 100 --ignore E501,W503

# Database
make migrate          # alembic upgrade head
make seed             # Populate test data

# Docker
make build            # Build image
make clean            # Remove containers, volumes, caches
```

## Code Style

- **Formatter:** Black, line-length 100
- **Linter:** Flake8, max-line-length 100, ignores E501,W503
- **Type checker:** MyPy (--ignore-missing-imports --no-strict-optional), non-blocking in CI
- **Naming:** snake_case for functions/variables, PascalCase for classes
- **Imports:** stdlib -> third-party -> local, with `TYPE_CHECKING` guards for circular deps
- **Docstrings:** Google-style with Args/Returns sections

## Project Structure

```
src/
├── app_v2.py              # Main Flask app entry point (create_app)
├── app.py                 # Legacy entry point
├── agents/                # 8 AI agents (router + 7 specialists)
├── api/                   # REST API v2 routes (/api/v2/*)
├── core/                  # RAG engine, LLM gateway, compliance, security
├── connectors/            # HRIS integrations (BambooHR, Workday, custom DB)
├── middleware/             # Auth, rate limiting, PII masking, sanitizer
├── platform_services/     # Dashboard, SLA, audit, cost tracking
├── repositories/          # Data access layer (repository pattern)
├── services/              # Business logic orchestration
├── mcp/                   # MCP server (FastMCP + custom tools)
└── integrations/          # Slack & Teams chat bots
```

## Key Entry Points

- `run.py` — Gunicorn WSGI entry, calls `create_app()`
- `src/app_v2.py` — Main Flask app factory with middleware, blueprints, background init
- `run_mcp.py` — Standalone MCP server (stdio, SSE, streamable-http)

## Architecture Patterns

- **Multi-agent orchestration:** RouterAgent classifies intent and dispatches to specialist agents
- **Lazy LLM init:** OpenAI/Google imports deferred to background threads to avoid blocking startup
- **Singleton services:** AgentService, SettingsGetter use `__new__` or `@lru_cache` for single instance
- **Background init:** Services initialize in daemon threads; health check endpoints respond immediately
- **Static fallback:** When LLM is unavailable, agents return pre-written knowledge base responses
- **Repository pattern:** Data access layer abstracts DB operations behind base repositories

## API Response Format

```json
{
  "success": true,
  "data": {},
  "error": null,
  "request_id": "uuid",
  "execution_time_ms": 123.4
}
```

## Environment Variables

Key variables (see `.env.example` for full list):

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Primary LLM provider |
| `GOOGLE_API_KEY` | Fallback LLM provider |
| `DATABASE_URL` | PostgreSQL connection string (or SQLite path) |
| `REDIS_URL` | Cache connection string |
| `JWT_SECRET` | Auth token signing key |
| `HRIS_PROVIDER` | HRIS connector: `bamboohr`, `workday`, or `database` |
| `PII_ENABLED` | Enable PII detection/masking |
| `PORT` | Server port (default 5050) |

## Testing

- **1,900+ unit tests** across `tests/unit/`
- **Integration tests** in `tests/integration/`
- **14 Playwright specs** in `tests/playwright/`
- **Coverage threshold:** 40% minimum in CI
- Test env vars: set `OPENAI_API_KEY=test-key`, `JWT_SECRET=test-secret`

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`):
1. **Lint** — Black 26.1.0 + Flake8 + MyPy
2. **Unit tests** — With Postgres 15 + Redis 7 services
3. **Coverage** — pytest-cov, 40% minimum
4. **Playwright** — Browser E2E tests
5. **Docker build** — Push to GHCR on main
6. **Deploy** — Cloud Run auto-deploy from main

## Known Quirks

- `TYPE_CHECKING` imports are required in several modules to avoid circular dependency issues (e.g., Blueprint imports in route files)
- Flake8 in CI uses a broad ignore list — check `.github/workflows/ci.yml` for the full set
- Background service init means agents/RAG/LLM may not be ready immediately on startup; the health endpoint handles this gracefully
- `make test` appends `|| true` so it never fails the make target — check pytest exit code directly for CI

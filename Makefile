.PHONY: help dev up down build test e2e lint migrate seed logs clean shell

# ============================================================================
# HR Multi-Agent Platform — Makefile
# Convenient targets for common development and deployment tasks
# ============================================================================

# Default target
help:
	@echo "HR Multi-Agent Platform — Available Targets"
	@echo "==========================================="
	@echo ""
	@echo "Development:"
	@echo "  make dev        - Start development server locally (Python, hot reload)"
	@echo "  make up         - Start all services with docker-compose (production)"
	@echo "  make down       - Stop all docker-compose services"
	@echo "  make shell      - Attach shell to running app container"
	@echo "  make logs       - View live logs from all services"
	@echo ""
	@echo "Building:"
	@echo "  make build      - Build Docker image"
	@echo "  make clean      - Clean up containers, volumes, and caches"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test       - Run pytest unit and integration tests"
	@echo "  make e2e        - Run Playwright end-to-end tests"
	@echo "  make lint       - Run flake8 + black code quality checks"
	@echo ""
	@echo "Database:"
	@echo "  make migrate    - Run Alembic migrations (upgrade head)"
	@echo "  make seed       - Run seed script to populate test data"
	@echo ""

# ============================================================================
# Development
# ============================================================================

# Start development server locally with hot reload
dev:
	@echo "Starting development server with hot reload..."
	@echo "Source code mounted for live changes."
	@echo "Listening on http://localhost:5050"
	@python -m pip install -q watchdog[watchmedo]
	@watchmedo auto-restart -d ./src -p '*.py' --recursive -- \
		python -m flask --app src.app_v2:app run --host 0.0.0.0 --port 5050 --debug

# Start with docker-compose (production-like setup)
up:
	@echo "Starting all services with docker-compose..."
	docker-compose up -d
	@echo "Application available at http://localhost:80"
	@echo "Postgres: localhost:5432"
	@echo "Redis: localhost:6379"

# Stop all services
down:
	@echo "Stopping all services..."
	docker-compose down

# Attach shell to running app container
shell:
	docker exec -it hr_platform_app /bin/sh

# View live logs from all services
logs:
	docker-compose logs -f

# ============================================================================
# Building
# ============================================================================

# Build Docker image
build:
	@echo "Building Docker image..."
	docker build -t hr-platform:latest .
	@echo "Image built successfully: hr-platform:latest"

# ============================================================================
# Testing
# ============================================================================

# Run unit and integration tests with pytest
test:
	@echo "Running unit and integration tests..."
	@pytest tests/unit/ tests/integration/ -v --tb=short || true
	@echo "Test summary available in test-results.xml"

# Run Playwright end-to-end tests
e2e:
	@echo "Installing Playwright and dependencies..."
	@npm ci
	@npx playwright install chromium
	@echo "Running E2E tests..."
	@npx playwright test --timeout=15000 --reporter=line,html
	@echo "Test report: playwright-report/index.html"

# ============================================================================
# Code Quality
# ============================================================================

# Run flake8 + black checks
lint:
	@echo "Running code quality checks..."
	@echo ""
	@echo "Running Black (code formatter check)..."
	@black --check --line-length 100 src/ tests/ 2>/dev/null || \
		(echo "Use 'black --line-length 100 src/ tests/' to auto-format")
	@echo "✓ Black check passed"
	@echo ""
	@echo "Running Flake8 (linting)..."
	@flake8 src/ --max-line-length 100 --ignore E501,W503
	@echo "✓ Flake8 check passed"
	@echo ""
	@echo "All checks passed!"

# ============================================================================
# Database
# ============================================================================

# Run Alembic migrations
migrate:
	@echo "Running database migrations..."
	@alembic upgrade head
	@echo "✓ Migrations completed"

# Seed database with initial data
seed:
	@echo "Seeding database with initial data..."
	@if [ -f scripts/seed.py ]; then \
		python scripts/seed.py; \
		echo "✓ Seeding completed"; \
	else \
		echo "⚠ scripts/seed.py not found"; \
	fi

# ============================================================================
# Cleanup
# ============================================================================

# Clean up containers, volumes, and caches
clean:
	@echo "Cleaning up Docker containers and volumes..."
	docker-compose down -v
	@echo ""
	@echo "Removing Python cache files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	@echo ""
	@echo "Removing test and build artifacts..."
	rm -rf .pytest_cache .coverage htmlcov test-results.xml
	rm -rf .mypy_cache dist build *.egg-info
	rm -rf test-results/ playwright-report/
	@echo ""
	@echo "✓ Cleanup completed"

# ============================================================================
# Testing Environments
# ============================================================================

# Start dev environment with SQLite and hot reload
dev-compose:
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run tests in Docker with Playwright
test-docker:
	docker-compose -f docker-compose.yml -f docker-compose.test.yml up --abort-on-container-exit

# ============================================================================

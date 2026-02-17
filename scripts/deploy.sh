#!/bin/bash
# ─────────────────────────────────────────────────────────
# HR Platform — Deploy Script
# Usage:  ./scripts/deploy.sh [up|down|logs|migrate|status]
# ─────────────────────────────────────────────────────────
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
PROJECT="hr-platform"

case "${1:-up}" in
  up)
    echo "Starting HR Platform..."
    docker compose -f $COMPOSE_FILE -p $PROJECT up -d --build
    echo ""
    echo "Waiting for health check..."
    sleep 10
    curl -s http://localhost/api/v2/health | python3 -m json.tool 2>/dev/null || echo "Still starting..."
    echo ""
    echo "HR Platform is running at http://localhost"
    ;;

  down)
    echo "Stopping HR Platform..."
    docker compose -f $COMPOSE_FILE -p $PROJECT down
    ;;

  logs)
    docker compose -f $COMPOSE_FILE -p $PROJECT logs -f --tail=100 ${2:-app}
    ;;

  migrate)
    echo "Running database migrations..."
    docker compose -f $COMPOSE_FILE -p $PROJECT exec app \
      alembic upgrade head
    echo "Seeding demo data..."
    docker compose -f $COMPOSE_FILE -p $PROJECT exec app \
      python -c "from src.core.database import seed_demo_data; seed_demo_data()"
    ;;

  status)
    docker compose -f $COMPOSE_FILE -p $PROJECT ps
    echo ""
    echo "Health check:"
    curl -s http://localhost/api/v2/health | python3 -m json.tool 2>/dev/null || echo "Unavailable"
    ;;

  restart)
    echo "Restarting app container..."
    docker compose -f $COMPOSE_FILE -p $PROJECT restart app nginx
    ;;

  *)
    echo "Usage: $0 [up|down|logs|migrate|status|restart]"
    exit 1
    ;;
esac

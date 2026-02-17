#!/usr/bin/env bash
# ============================================
# GCP Cloud Run — One-Click Deploy Script
# HR Intelligence Platform
# ============================================
#
# Prerequisites:
#   1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install
#   2. Run: gcloud auth login
#   3. Run: gcloud config set project YOUR_PROJECT_ID
#   4. Enable required APIs (script does this automatically)
#
# Usage:
#   chmod +x deploy/gcp/deploy.sh
#   ./deploy/gcp/deploy.sh
#
# ============================================

set -euo pipefail

# ── Configuration (override via environment) ──
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${GCP_SERVICE_NAME:-hr-platform}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Cloud SQL (optional — set to "skip" to use SQLite)
DB_INSTANCE="${GCP_DB_INSTANCE:-hr-platform-db}"
DB_NAME="${GCP_DB_NAME:-hr_platform}"
DB_USER="${GCP_DB_USER:-hr_user}"
DB_PASSWORD="${GCP_DB_PASSWORD:-}"

# ── Colors ────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ── Preflight checks ─────────────────────────
echo ""
echo "============================================"
echo "  GCP Cloud Run — Deployment"
echo "  Project: ${PROJECT_ID}"
echo "  Region:  ${REGION}"
echo "  Service: ${SERVICE_NAME}"
echo "============================================"
echo ""

[ -z "$PROJECT_ID" ] && fail "No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"

# Verify gcloud is authenticated
gcloud auth print-access-token &>/dev/null || fail "Not authenticated. Run: gcloud auth login"

# ── Step 1: Enable required APIs ──────────────
info "Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    containerregistry.googleapis.com \
    cloudbuild.googleapis.com \
    sqladmin.googleapis.com \
    secretmanager.googleapis.com \
    --project="$PROJECT_ID" --quiet
ok "APIs enabled"

# ── Step 2: Build & push Docker image ─────────
info "Building Docker image with Cloud Build..."
cd "$(dirname "$0")/../.."   # Navigate to project root

gcloud builds submit \
    --tag "${IMAGE_NAME}:latest" \
    --project="$PROJECT_ID" \
    --timeout=1800s \
    --quiet

ok "Image pushed to ${IMAGE_NAME}:latest"

# ── Step 3: Create Cloud SQL (optional) ───────
if [ "${DB_INSTANCE}" != "skip" ]; then
    # Check if instance already exists
    if gcloud sql instances describe "$DB_INSTANCE" --project="$PROJECT_ID" &>/dev/null; then
        info "Cloud SQL instance '${DB_INSTANCE}' already exists, skipping creation"
    else
        info "Creating Cloud SQL PostgreSQL instance..."

        # Generate a password if not provided
        if [ -z "$DB_PASSWORD" ]; then
            DB_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
            warn "Generated DB password. Save this: ${DB_PASSWORD}"
        fi

        gcloud sql instances create "$DB_INSTANCE" \
            --database-version=POSTGRES_15 \
            --tier=db-f1-micro \
            --region="$REGION" \
            --storage-size=10GB \
            --storage-auto-increase \
            --project="$PROJECT_ID" \
            --quiet

        gcloud sql users set-password postgres \
            --instance="$DB_INSTANCE" \
            --password="$DB_PASSWORD" \
            --project="$PROJECT_ID" \
            --quiet

        gcloud sql databases create "$DB_NAME" \
            --instance="$DB_INSTANCE" \
            --project="$PROJECT_ID" \
            --quiet

        ok "Cloud SQL instance created"
    fi

    # Get connection name for Cloud Run
    DB_CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE" \
        --project="$PROJECT_ID" --format='value(connectionName)')
    DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"
else
    warn "Skipping Cloud SQL — app will use SQLite"
    DATABASE_URL="sqlite:///hr_platform.db"
fi

# ── Step 4: Store secrets ─────────────────────
info "Storing secrets in Secret Manager..."

JWT_SECRET="${JWT_SECRET:-$(openssl rand -base64 32)}"

# Helper to create/update a secret
store_secret() {
    local name="$1" value="$2"
    if gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null; then
        echo -n "$value" | gcloud secrets versions add "$name" --data-file=- --project="$PROJECT_ID" --quiet
    else
        echo -n "$value" | gcloud secrets create "$name" --data-file=- --project="$PROJECT_ID" --quiet
    fi
}

store_secret "hr-database-url" "$DATABASE_URL"
store_secret "hr-jwt-secret" "$JWT_SECRET"

if [ -n "${OPENAI_API_KEY:-}" ]; then
    store_secret "hr-openai-key" "$OPENAI_API_KEY"
fi

ok "Secrets stored"

# ── Step 5: Deploy to Cloud Run ───────────────
info "Deploying to Cloud Run..."

DEPLOY_ARGS=(
    --image "${IMAGE_NAME}:latest"
    --region "$REGION"
    --platform managed
    --port 5050
    --memory 1Gi
    --cpu 1
    --min-instances 0
    --max-instances 3
    --timeout 300
    --allow-unauthenticated
    --set-env-vars "WORKERS=2,TIMEOUT=120,LOG_LEVEL=INFO,ENVIRONMENT=production"
    --update-secrets "DATABASE_URL=hr-database-url:latest,JWT_SECRET=hr-jwt-secret:latest"
    --project "$PROJECT_ID"
)

# Add Cloud SQL connection if using managed DB
if [ "${DB_INSTANCE}" != "skip" ]; then
    DEPLOY_ARGS+=(--add-cloudsql-instances "$DB_CONNECTION_NAME")
fi

# Add OpenAI key if stored
if [ -n "${OPENAI_API_KEY:-}" ]; then
    DEPLOY_ARGS+=(--update-secrets "OPENAI_API_KEY=hr-openai-key:latest")
fi

gcloud run deploy "$SERVICE_NAME" "${DEPLOY_ARGS[@]}" --quiet

ok "Deployed to Cloud Run!"

# ── Step 6: Get URL ───────────────────────────
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" --project="$PROJECT_ID" \
    --format='value(status.url)')

echo ""
echo "============================================"
echo -e "  ${GREEN}Deployment complete!${NC}"
echo ""
echo "  URL: ${SERVICE_URL}"
echo "  Service: ${SERVICE_NAME}"
echo "  Region: ${REGION}"
echo ""
echo "  Test it:"
echo "    curl ${SERVICE_URL}/api/v2/health"
echo ""
echo "  View logs:"
echo "    gcloud run services logs read ${SERVICE_NAME} --region=${REGION}"
echo ""
echo "  Update later:"
echo "    ./deploy/gcp/deploy.sh"
echo "============================================"

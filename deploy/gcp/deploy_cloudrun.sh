#!/usr/bin/env bash
# ============================================
# GCP Cloud Run — Deploy Script (Supabase DB)
# HR Intelligence Platform
# ============================================
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated
#   2. OPENAI_API_KEY set in environment or .env
#   3. DATABASE_URL set in environment or .env (Supabase)
#
# Usage:
#   chmod +x deploy/gcp/deploy_cloudrun.sh
#   ./deploy/gcp/deploy_cloudrun.sh
#
# ============================================

set -euo pipefail

# ── Colors ────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[  OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ── Load .env if present ─────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ -f "$PROJECT_ROOT/.env" ]; then
    info "Loading .env file..."
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# ── Configuration ─────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${GCP_SERVICE_NAME:-hr-platform}"
AR_REPO="${GCP_AR_REPO:-cloud-run-source-deploy}"     # Artifact Registry repo
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}"

echo ""
echo "============================================"
echo "  GCP Cloud Run — Deployment"
echo "  Project: ${PROJECT_ID}"
echo "  Region:  ${REGION}"
echo "  Service: ${SERVICE_NAME}"
echo "============================================"
echo ""

# ── Preflight checks ─────────────────────────
[ -z "$PROJECT_ID" ] && fail "No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
gcloud auth print-access-token &>/dev/null || fail "Not authenticated. Run: gcloud auth login"

# Check required env vars
[ -z "${DATABASE_URL:-}" ] && fail "DATABASE_URL not set. Export it or add to .env"
[ -z "${OPENAI_API_KEY:-}" ] && fail "OPENAI_API_KEY not set. Export it or add to .env"

# ── Step 1: Enable APIs ──────────────────────
info "Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    --project="$PROJECT_ID" --quiet
ok "APIs enabled"

# ── Step 2: Store secrets ─────────────────────
info "Storing secrets in Secret Manager..."

JWT_SECRET="${JWT_SECRET:-$(openssl rand -base64 32)}"

store_secret() {
    local name="$1" value="$2"
    if gcloud secrets describe "$name" --project="$PROJECT_ID" &>/dev/null 2>&1; then
        echo -n "$value" | gcloud secrets versions add "$name" \
            --data-file=- --project="$PROJECT_ID" --quiet 2>/dev/null
    else
        echo -n "$value" | gcloud secrets create "$name" \
            --data-file=- --replication-policy=automatic \
            --project="$PROJECT_ID" --quiet
    fi
}

store_secret "hr-database-url" "$DATABASE_URL"
store_secret "hr-jwt-secret"   "$JWT_SECRET"
store_secret "hr-openai-key"   "$OPENAI_API_KEY"

# Grant Cloud Run service account access to secrets
SA_EMAIL="$(gcloud iam service-accounts list \
    --project="$PROJECT_ID" \
    --filter='email~compute@developer' \
    --format='value(email)' 2>/dev/null | head -1)"

if [ -n "$SA_EMAIL" ]; then
    for secret in hr-database-url hr-jwt-secret hr-openai-key; do
        gcloud secrets add-iam-policy-binding "$secret" \
            --member="serviceAccount:$SA_EMAIL" \
            --role="roles/secretmanager.secretAccessor" \
            --project="$PROJECT_ID" --quiet 2>/dev/null || true
    done
    ok "Secret access granted to $SA_EMAIL"
else
    warn "Could not find default compute SA — secrets may need manual IAM binding"
fi

ok "Secrets stored"

# ── Step 3: Build & push image ────────────────
info "Building Docker image with Cloud Build..."
cd "$PROJECT_ROOT"

gcloud builds submit \
    --tag "${IMAGE}:latest" \
    --project="$PROJECT_ID" \
    --timeout=1800s \
    --machine-type=e2-highcpu-8 \
    --quiet

ok "Image pushed to ${IMAGE}:latest"

# ── Step 4: Deploy to Cloud Run ───────────────
info "Deploying to Cloud Run..."

gcloud run deploy "$SERVICE_NAME" \
    --image "${IMAGE}:latest" \
    --region "$REGION" \
    --platform managed \
    --port 5050 \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 0 \
    --max-instances 5 \
    --timeout 300 \
    --concurrency 80 \
    --cpu-boost \
    --allow-unauthenticated \
    --set-env-vars "WORKERS=1,TIMEOUT=300,LOG_LEVEL=INFO,ENVIRONMENT=production,PORT=5050" \
    --update-secrets "DATABASE_URL=hr-database-url:latest,JWT_SECRET=hr-jwt-secret:latest,OPENAI_API_KEY=hr-openai-key:latest" \
    --project "$PROJECT_ID" \
    --quiet

ok "Deployed to Cloud Run!"

# ── Step 5: Verify ────────────────────────────
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" --project="$PROJECT_ID" \
    --format='value(status.url)')

echo ""
info "Waiting for service to become healthy (this may take 30-60s on first deploy)..."
for i in $(seq 1 12); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/api/v2/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        ok "Health check passed!"
        curl -s "$SERVICE_URL/api/v2/health" | python3 -m json.tool 2>/dev/null || true
        break
    fi
    echo -n "."
    sleep 10
done

echo ""
echo "============================================"
echo -e "  ${GREEN}Deployment complete!${NC}"
echo ""
echo "  URL:     ${SERVICE_URL}"
echo "  Service: ${SERVICE_NAME}"
echo "  Region:  ${REGION}"
echo ""
echo "  Test:"
echo "    curl ${SERVICE_URL}/api/v2/health"
echo ""
echo "  Logs:"
echo "    gcloud run services logs read ${SERVICE_NAME} --region=${REGION}"
echo ""
echo "  Console:"
echo "    https://console.cloud.google.com/run/detail/${REGION}/${SERVICE_NAME}/logs?project=${PROJECT_ID}"
echo "============================================"

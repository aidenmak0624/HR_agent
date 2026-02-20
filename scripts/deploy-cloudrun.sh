#!/bin/bash
# ─────────────────────────────────────────────────────────
# HR Platform — Google Cloud Run Deploy Script
# Usage:  ./scripts/deploy-cloudrun.sh [deploy|status|logs|env|destroy]
#
# Prerequisites:
#   1. gcloud CLI installed & authenticated:  gcloud auth login
#   2. Set your project:  gcloud config set project YOUR_PROJECT_ID
#   3. Enable required APIs:
#        gcloud services enable \
#          run.googleapis.com \
#          artifactregistry.googleapis.com \
#          cloudbuild.googleapis.com \
#          secretmanager.googleapis.com
# ─────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration (override via env vars) ───────────────
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-hr-platform}"
REPO_NAME="${ARTIFACT_REPO:-hr-platform}"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"

# Cloud Run service settings
MEMORY="${CLOUD_RUN_MEMORY:-1Gi}"
CPU="${CLOUD_RUN_CPU:-1}"
MIN_INSTANCES="${CLOUD_RUN_MIN_INSTANCES:-0}"
MAX_INSTANCES="${CLOUD_RUN_MAX_INSTANCES:-3}"
TIMEOUT="${CLOUD_RUN_TIMEOUT:-300}"
CONCURRENCY="${CLOUD_RUN_CONCURRENCY:-80}"

echo "╔══════════════════════════════════════════════════╗"
echo "║  HR Agent Platform — Cloud Run Deployment        ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Project:  ${PROJECT_ID}"
echo "║  Region:   ${REGION}"
echo "║  Service:  ${SERVICE_NAME}"
echo "╚══════════════════════════════════════════════════╝"
echo ""

ensure_artifact_registry() {
  echo "→ Ensuring Artifact Registry repo exists..."
  gcloud artifacts repositories describe "${REPO_NAME}" \
    --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --description="HR Agent Platform Docker images"
  echo "  ✓ Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
}

build_and_push() {
  echo "→ Building Docker image..."
  TAG="${IMAGE_NAME}:$(git rev-parse --short HEAD 2>/dev/null || echo latest)"
  LATEST="${IMAGE_NAME}:latest"

  # Authenticate Docker with Artifact Registry
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

  docker build -t "${TAG}" -t "${LATEST}" .
  echo "→ Pushing image to Artifact Registry..."
  docker push "${TAG}"
  docker push "${LATEST}"
  echo "  ✓ Pushed: ${TAG}"
}

deploy() {
  ensure_artifact_registry
  build_and_push

  echo ""
  echo "→ Deploying to Cloud Run..."
  gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_NAME}:latest" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --platform=managed \
    --allow-unauthenticated \
    --port=5050 \
    --memory="${MEMORY}" \
    --cpu="${CPU}" \
    --min-instances="${MIN_INSTANCES}" \
    --max-instances="${MAX_INSTANCES}" \
    --timeout="${TIMEOUT}" \
    --concurrency="${CONCURRENCY}" \
    --set-env-vars="PORT=5050,WORKERS=1,TIMEOUT=${TIMEOUT}" \
    --update-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest,JWT_SECRET=JWT_SECRET:latest,DATABASE_URL=DATABASE_URL:latest" \
    --quiet

  echo ""
  echo "✓ Deployed successfully!"
  URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')
  echo "  URL: ${URL}"
  echo ""
  echo "→ Testing health endpoint..."
  curl -sf "${URL}/api/v2/health" | python3 -m json.tool 2>/dev/null || echo "  Service is starting up, may take a minute..."
}

setup_secrets() {
  echo "→ Setting up secrets in Secret Manager..."
  echo "  (You'll be prompted for values if secrets don't exist)"
  echo ""

  for SECRET_NAME in OPENAI_API_KEY JWT_SECRET DATABASE_URL BAMBOOHR_API_KEY BAMBOOHR_SUBDOMAIN; do
    if gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
      echo "  ✓ ${SECRET_NAME} already exists"
    else
      echo "  Creating ${SECRET_NAME}..."
      read -sp "    Enter value for ${SECRET_NAME}: " SECRET_VALUE
      echo ""
      echo -n "${SECRET_VALUE}" | gcloud secrets create "${SECRET_NAME}" \
        --data-file=- \
        --project="${PROJECT_ID}" \
        --replication-policy="automatic"
      echo "  ✓ ${SECRET_NAME} created"
    fi
  done

  echo ""
  echo "→ Granting Cloud Run access to secrets..."
  PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
  SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

  for SECRET_NAME in OPENAI_API_KEY JWT_SECRET DATABASE_URL BAMBOOHR_API_KEY BAMBOOHR_SUBDOMAIN; do
    gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
      --member="serviceAccount:${SA}" \
      --role="roles/secretmanager.secretAccessor" \
      --project="${PROJECT_ID}" --quiet 2>/dev/null || true
  done
  echo "  ✓ Secret access granted"
}

status() {
  echo "→ Service status:"
  gcloud run services describe "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format="table(status.url, status.conditions.type, status.conditions.status)"
  echo ""
  echo "→ Recent revisions:"
  gcloud run revisions list \
    --service="${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --limit=5
}

logs() {
  echo "→ Streaming logs (Ctrl+C to stop)..."
  gcloud run services logs tail "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}"
}

destroy() {
  echo "⚠ This will delete the Cloud Run service: ${SERVICE_NAME}"
  read -p "  Are you sure? (yes/no): " CONFIRM
  if [ "${CONFIRM}" = "yes" ]; then
    gcloud run services delete "${SERVICE_NAME}" \
      --region="${REGION}" \
      --project="${PROJECT_ID}" \
      --quiet
    echo "  ✓ Service deleted"
  else
    echo "  Cancelled."
  fi
}

case "${1:-deploy}" in
  deploy)   deploy ;;
  secrets)  setup_secrets ;;
  status)   status ;;
  logs)     logs ;;
  destroy)  destroy ;;
  *)
    echo "Usage: $0 [deploy|secrets|status|logs|destroy]"
    echo ""
    echo "Commands:"
    echo "  deploy   Build, push, and deploy to Cloud Run (default)"
    echo "  secrets  Set up secrets in GCP Secret Manager"
    echo "  status   Show service status and recent revisions"
    echo "  logs     Stream live logs"
    echo "  destroy  Delete the Cloud Run service"
    exit 1
    ;;
esac

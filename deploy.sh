#!/bin/bash
# HR Platform — Build & Deploy to Cloud Run
# Usage: ./deploy.sh

set -e

PROJECT="hr-intelligence-app"
IMAGE="gcr.io/${PROJECT}/hr-platform:latest"
REGION="us-central1"
SERVICE="hr-platform"

echo "🔨 Building image..."
gcloud builds submit --tag "$IMAGE" --project "$PROJECT"

echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --platform managed \
  --port 5050 \
  --memory 1Gi \
  --min-instances 1 \
  --allow-unauthenticated \
  --set-env-vars "WORKERS=2,TIMEOUT=120,LOG_LEVEL=INFO,ENVIRONMENT=production" \
  --update-secrets "OPENAI_API_KEY=hr-openai-key:latest,DATABASE_URL=hr-database-url:latest,JWT_SECRET=hr-jwt-secret:latest" \
  --add-cloudsql-instances "${PROJECT}:${REGION}:hr-platform-db" \
  --project "$PROJECT"

echo ""
echo "✅ Deployed! Testing health endpoint..."
sleep 5
curl -s "https://hr-platform-837558695367.${REGION}.run.app/api/v2/health" | python3 -m json.tool

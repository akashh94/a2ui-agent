#!/usr/bin/env bash

set -euo pipefail

# Resolve this project's root and run from there regardless of the cwd.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Office environment config (self-contained): PROJECT_ID / REGION / AGENT_MODEL /
# SERVICE_NAME / IMAGE / secrets all come from a2ui.deploy.env — the single
# source of truth for the office deployment.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/a2ui.deploy.env"

gcloud config set project "$PROJECT_ID"

# Deploy the single project (agent embedded in the FastAPI server) as a
# public Cloud Run service. Cloud Run injects PORT; the Dockerfile runs
# uvicorn on it. The service runs as SERVICE_ACCOUNT (SA + ADC auth for
# Vertex AI) with no API-key secrets.
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --service-account "$SERVICE_ACCOUNT" \
  --no-secrets \
  --set-env-vars "AGENT_MODEL=${AGENT_MODEL},MODEL_LOCATION=${MODEL_LOCATION},ALLOW_ORIGINS=${ALLOW_ORIGINS}" \
  --min-instances 1 \
  --max-instances 1

echo "Deployed. Service URL: https://${SERVICE_NAME}-${PROJECT_ID_HASH}.${REGION}.run.app"

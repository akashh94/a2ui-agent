#!/usr/bin/env bash

set -euo pipefail

# Resolve this project's root and run from there regardless of the cwd.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Office environment config (self-contained): PROJECT_ID / REGION / SERVICE_NAME /
# IMAGE / secrets all come from a2ui.deploy.env — the single source of truth for
# the office deployment.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/a2ui.deploy.env"

gcloud config set project "$PROJECT_ID"

# Deploy the a2ui-server (catalog + chat facade) as a public Cloud Run
# service. The agent itself runs on Vertex AI Agent Engine; this service
# serves /etcatalog statically and proxies /chat to the deployed agent.
# Cloud Run injects PORT; the Dockerfile runs uvicorn on it. The service
# runs as SERVICE_ACCOUNT (SA + ADC auth for the Agent Engine client) with
# no API-key secrets.
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "AGENT_ENGINE_RESOURCE=${AGENT_ENGINE_RESOURCE},ALLOW_ORIGINS=${ALLOW_ORIGINS},CATALOG_URL=${CATALOG_URL}" \
  --min-instances 1 \
  --max-instances 1

echo "Deployed. Service URL: https://${SERVICE_NAME}-${PROJECT_ID_HASH}.${REGION}.run.app"

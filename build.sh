#!/usr/bin/env bash
#
# Build (Cloud Build) for the a2ui-agent A2A service — office env.
# Builds and pushes the container image to Artifact Registry; no local Docker
# required. Deploy it with ./deploy.sh.

set -euo pipefail

# Resolve this project's root.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Office environment config (self-contained): PROJECT_ID / REGION /
# ARTIFACT_REGISTRY / ARTIFACT_REGION / SERVICE_NAME / APP_URL / ALLOW_ORIGINS
# all come from a2ui.deploy.env — the single source of truth for the office
# deployment.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/a2ui.deploy.env"

gcloud config set project "$PROJECT_ID"

# Ensure the Artifact Registry repository exists in the deploy region.
echo "Ensuring Artifact Registry repository '${ARTIFACT_REGISTRY}' in ${ARTIFACT_REGION}..."
gcloud artifacts repositories describe "$ARTIFACT_REGISTRY" \
  --location "$ARTIFACT_REGION" >/dev/null 2>&1 || {
  echo "Repository not found; creating..."
  gcloud artifacts repositories create "$ARTIFACT_REGISTRY" \
    --repository-format docker \
    --location "$ARTIFACT_REGION"
}

# Build + push the agent image to the office project's Artifact Registry.
IMAGE="${ARTIFACT_REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REGISTRY}/a2ui-agent-office:$(git rev-parse --short HEAD)"
echo "$IMAGE"
gcloud builds submit . --tag "$IMAGE" --project "$PROJECT_ID"

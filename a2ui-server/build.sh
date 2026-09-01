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

echo "Building and pushing image ${IMAGE}..."
gcloud builds submit --tag "$IMAGE"

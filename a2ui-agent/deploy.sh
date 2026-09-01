#!/usr/bin/env bash

set -euo pipefail

# Resolve this project's root (where agents-cli-manifest.yaml lives) and run
# agents-cli from there, so the manifest and pyproject.toml are found
# regardless of the cwd.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# uv resolves the project environment from VIRTUAL_ENV if set. When this
# script runs from a shell where a venv in a parent directory is active,
# uv complains that the interpreter is "outside the project directory".
# Unset it so uv uses the project-local .venv instead.
unset VIRTUAL_ENV

# Office environment config (self-contained): PROJECT_ID / REGION / AGENT_MODEL /
# MODEL_LOCATION / CATALOG_URL all come from a2ui.deploy.env — the single
# source of truth for the office deployment.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/a2ui.deploy.env"

# "agent_runtime" is the target that maps to the Vertex AI Agent Engine /
# Reasoning Engine resource that a2ui-server/server.js proxies to. The
# manifest (agents-cli-manifest.yaml) drives create/update; env vars are
# passed to the deployed engine via --update-env-vars. No service account is
# passed — agents-cli provisions one (Vertex AI User on the project), and the
# a2ui-server must grant it roles/run.invoker so get_a2ui_catalog can fetch
# the catalog with its ID token.
agents-cli deploy \
  --deployment-target agent_runtime \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --update-env-vars "AGENT_MODEL=${AGENT_MODEL},MODEL_LOCATION=${MODEL_LOCATION},CATALOG_URL=${CATALOG_URL}" \
  --min-instances 1 \
  --max-instances 1 \
  --no-confirm-project

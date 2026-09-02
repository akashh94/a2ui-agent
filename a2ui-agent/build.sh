#!/usr/bin/env bash
#
# Build (lint + smoke import) for the a2ui-agent A2A service — office env.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

unset VIRTUAL_ENV

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv sync --dev --extra lint
uv run ruff check .
uv run ruff format . --check
uv run codespell
uv run ty check .

# Smoke import (builds the agent + inference format).
uv run python -c "import app.fast_api_app; import app.agent; print('imports OK')"

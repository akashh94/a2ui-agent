FROM python:3.12-slim

WORKDIR /app

# Install from uv.lock, not a fresh resolve of pyproject: resolving fresh
# pulls a newer a2ui-agent-sdk (0.8.0 vs the locked 0.5.0), which removed
# A2uiCatalog and makes app/agent.py fail to import at startup.
COPY pyproject.toml uv.lock ./
COPY app/ app/
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080
# Shell form (not exec form) so bash expands ${PORT:-8080}.
CMD uvicorn app.fast_api_app:app --host 0.0.0.0 --port "${PORT:-8080}"

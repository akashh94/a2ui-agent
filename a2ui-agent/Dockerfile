FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml .
COPY app/ app/
COPY agents-cli-manifest.yaml .

RUN pip install --no-cache-dir .

# Agent Engine (agent_runtime) serves the deployed agent over HTTP; the
# container runs the ADK FastAPI app on PORT (Cloud Run / Agent Engine injects it).
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.fast_api_app:app --host 0.0.0.0 --port ${PORT}"]

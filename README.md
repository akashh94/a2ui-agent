# a2ui-agent

A single-project agent + server: an ADK `LlmAgent` (Google Search + an A2UI
catalog tool) embedded in a FastAPI server, exposed over two HTTP endpoints,
deployed as **one Cloud Run service**.

- `POST /chat` — SSE stream of the agent's text reply. General questions are
  answered via `google_search`; A2UI/`etcatalog` questions are answered from
  the catalog data the `get_a2ui_catalog` tool returns.
- `GET /etcatalog` — the project's A2UI catalog as JSON, in the official
  A2UI v0.9 JSON Schema catalog format (same shape as `@a2ui/lit`'s
  published basic catalog).

The catalog is data the agent reads via the `get_a2ui_catalog` tool — the
model never authors component JSON itself.

## How the two tools split the work

- **`google_search`** — general web questions ("what is the capital of
  France?").
- **`get_a2ui_catalog`** — returns the in-memory catalog (loaded from
  `catalog.json`), so the agent answers A2UI/`etcatalog` questions from the
  same catalog `/etcatalog` serves. No HTTP round-trip needed — the agent and
  server share one process.

## Setup (local)

```bash
pip install -r requirements.txt
cp .env.example .env
```

Authentication is via **Application Default Credentials (ADC)** — no API keys:

```bash
gcloud auth application-default login
```

The model runs on **Vertex AI** (`Gemini(vertexai=True)`, same as geap-agent),
so ADC (and the Vertex AI API being enabled) is all that's needed — for both
the model and the `google_search` tool (search rides on the model's grounding).

## Run (local)

```bash
uvicorn server:app --reload
```

Each SSE frame is `data: <json>`; text deltas stream as they are generated
and the stream ends with `data: [DONE]`.

Catalog:

```bash
curl http://localhost:8000/etcatalog
```

Chat — general question (agent calls `google_search`):

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is the capital of France?"}'
```

Chat — A2UI question (agent calls `get_a2ui_catalog`):

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what A2UI components are available?"}'
```

## Deploy to Cloud Run (single service)

The whole project — agent + server — is one container. Two environments are
supported, following the geap-agent convention:

- **Office** — `./build.sh` then `./deploy.sh`, config from `a2ui.deploy.env`.
- **Personal** — `./build.personal.sh` then `./deploy.personal.sh`, config
  from `deploy.personal.env`.

Each env file defines `PROJECT_ID`, `REGION`, `SERVICE_NAME`, `IMAGE`,
`AGENT_MODEL`, `MODEL_LOCATION`, `SERVICE_ACCOUNT`, and `ALLOW_ORIGINS` — the
same style of variable names the geap-agent deploy envs use. The service runs
as `SERVICE_ACCOUNT` (SA + ADC), so **no API-key secrets are needed**.

1. Make sure the service account in the env file has the **Vertex AI User**
   role (`roles/aiplatform.user`) on the project, and the **Vertex AI API** is
   enabled.

2. Edit the env file you plan to use: set `PROJECT_ID`, `REGION`, and after
   first deploy the `PROJECT_ID_HASH` (the short hash in the printed service
   URL).

3. Build and deploy:

   ```bash
   # office
   ./build.sh
   ./deploy.sh

   # or personal
   ./build.personal.sh
   ./deploy.personal.sh
   ```

The service listens on the `PORT` env var Cloud Run injects; the Dockerfile
runs `uvicorn` with it. The client hits `https://<service-url>/etcatalog`
and `https://<service-url>/chat` — one URL for everything.

## Project layout

```
agent.py        ADK LlmAgent: google_search + get_a2ui_catalog
catalog.json    A2UI catalog, official v0.9 JSON Schema format
server.py       FastAPI app: POST /chat (SSE), GET /etcatalog
Dockerfile      Container image for Cloud Run (PORT-aware)
build.sh        Office: build + push the container image
deploy.sh       Office: deploy to Cloud Run
build.personal.sh  Personal: build + push the container image
deploy.personal.sh Personal: deploy to Cloud Run
a2ui.deploy.env Office deployment config (project, region, service, secrets)
deploy.personal.env Personal deployment config
```

The server runs the agent with the base `Runner` and `auto_create_session=True`
(the same pattern geap-agent's `fast_api_app.py` uses), with lightweight
in-memory session/artifact/memory services — no cloud dependencies.

## Deliberately out of scope

No frontend/renderer, no A2UI envelope builder, no validation layer, no DB,
auth, or session persistence across restarts. A future client can consume
`/etcatalog` + `/chat` directly.

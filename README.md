# a2ui-agent

A single-repo, two-service project: an ADK `LlmAgent` (Google Search + an A2UI
catalog tool) deployed on **Vertex AI Agent Engine**, and a **Cloud Run**
catalog + chat facade that serves the A2UI catalog and streams `/chat`
responses to the deployed agent.

```
Browser / client
   │  HTTPS (public)
   ▼
a2ui-server (Cloud Run) ── GET /etcatalog (static catalog.json)
   │                       ── POST /chat (SSE proxy)
   │                             │
   │                             │ Vertex AI API (SA/ADC, gRPC)
   ▼                             ▼
                         a2ui-agent (Agent Engine)
                               │
                               │ ID-token auth (RestApiTool, audience=catalog URL)
                               ▼
                         a2ui-server /etcatalog (private, IAM-only)
```

- **a2ui-server/** — Cloud Run. Serves `GET /etcatalog` (the A2UI catalog as
  JSON, official v0.9 JSON Schema format, same shape as `@a2ui/lit`'s
  published basic catalog) and `POST /chat`, which streams the agent's reply
  as SSE. `/chat` is a thin proxy: it forwards the message to the deployed
  Agent Engine and relays streamed events back to the client.
- **a2ui-agent/** — Agent Engine. The ADK `LlmAgent` with two tools:
  `google_search` for general web questions, and `get_a2ui_catalog`, a REST
  tool that fetches the catalog from the a2ui-server over HTTP using a
  service-account **ID token** (audience = the catalog URL). The model decides
  *when* to call the catalog tool; it never authors component JSON itself.

The catalog is data the agent fetches from the a2ui-server — the model
never authors component JSON itself, and the agent has no local copy.

## How the two tools split the work

- **`google_search`** — general web questions ("what is the capital of
  France?").
- **`get_a2ui_catalog`** — calls `GET <a2ui-server>/etcatalog` via a
  `RestApiTool` (from an `OpenAPIToolset`), authenticated with the Agent
  Engine service account's ID token. Same catalog `/etcatalog` serves.

## Setup (local)

Each service is self-contained; install and run them separately.

```bash
# a2ui-server (FastAPI + vertexai client)
cd a2ui-server
pip install -r requirements.txt
cp .env.example .env   # (see below)

# a2ui-agent (ADK agent)
cd a2ui-agent
uv sync   # or: pip install -e .
```

Authentication is via **Application Default Credentials (ADC)** — no API keys:

```bash
gcloud auth application-default login
```

## Run (local)

### a2ui-server

```bash
cd a2ui-server
uvicorn server:app --reload
```

Each SSE frame is `data: <json>`; text deltas stream as they are generated
and the stream ends with `data: [DONE]`.

Catalog:

```bash
curl http://localhost:8000/etcatalog
```

Chat — the local `/chat` proxies to the Agent Engine identified by
`AGENT_ENGINE_PROJECT` / `AGENT_ENGINE_LOCATION` / `AGENT_ENGINE_ID` (set them
to your deployed agent):

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is the capital of France?"}'
```

### a2ui-agent

```bash
cd a2ui-agent
python -c "from agent import agent; print(agent.name)"   # smoke test
```

## Deploy (two services)

Deploy **a2ui-server first**, then **a2ui-agent** (the agent needs the catalog
URL + the a2ui-server must be up to answer the catalog tool).

Each service has office/personal variants following the geap-agent convention
(`./build.sh` then `./deploy.sh`, or `./build.personal.sh` then
`./deploy.personal.sh`), with config from `a2ui.deploy.env` / `deploy.personal.env`.

### 1. a2ui-server → Cloud Run

1. Edit `a2ui-server/a2ui.deploy.env` (or `deploy.personal.env`): set
   `PROJECT_ID`, `REGION`, and after first deploy `PROJECT_ID_HASH` (the short
   hash in the printed service URL) and `CATALOG_URL`.
2. Build and deploy:

   ```bash
   cd a2ui-server
   ./build.sh && ./deploy.sh        # office
   # or ./build.personal.sh && ./deploy.personal.sh
   ```

3. Give the **a2ui-agent service account** `roles/run.invoker` on this
   Cloud Run service (so the agent's catalog tool can call `/etcatalog` with
   its ID token). agents-cli provisions the engine's service account; find
   its email with `gcloud iam service-accounts list`. Example:

   ```bash
   gcloud run services add-iam-policy-binding a2ui-server \
     --region us-central1 --member serviceAccount:SA_EMAIL \
     --role roles/run.invoker
   ```

### 2. a2ui-agent → Agent Engine

Deployment is driven by `agents-cli` (the same flow as geap-agent): the
manifest `agents-cli-manifest.yaml` defines the Agent Engine target, and
`deploy.sh`/`deploy.personal.sh` pass the runtime env vars via
`--update-env-vars`. No service account is passed — agents-cli provisions one
(Vertex AI User on the project).

1. Edit `a2ui-agent/a2ui.deploy.env` (or `deploy.personal.env`): set
   `PROJECT_ID`, `REGION`, and `CATALOG_URL` to the deployed a2ui-server URL.
2. Build and deploy:

   ```bash
   cd a2ui-agent
   ./build.sh && ./deploy.sh        # office
   # or ./build.personal.sh && ./deploy.personal.sh
   ```

   `build.sh` runs `agents-cli install` + `agents-cli lint`; `deploy.sh` runs
   `agents-cli deploy --deployment-target agent_runtime` (creates or updates
   the engine, and pushes the container to Artifact Registry).

3. Give the **a2ui-server service account** `roles/aiplatform.user` on the
   project so its `/chat` proxy can call the Agent Engine.

### 3. Point the facade at the agent

Set `AGENT_ENGINE_PROJECT` / `AGENT_ENGINE_LOCATION` / `AGENT_ENGINE_ID` (the
engine's project, region, and `reasoningEngines/<id>` from the deploy output)
in `a2ui-server`'s env file and redeploy the a2ui-server (or update the env
vars in the Cloud Run console). Then the public `/chat` endpoint streams from
your deployed agent.

## IAM / service accounts at a glance

| Direction | Identity | Grant |
|---|---|---|
| a2ui-server → Agent Engine (`/chat`) | Cloud Run SA | `roles/aiplatform.user` on the project |
| Agent Engine → a2ui-server `/etcatalog` (catalog tool) | Agent Engine SA (provisioned by agents-cli) | `roles/run.invoker` on the a2ui-server |

No API-key secrets anywhere — everything rides on ADC + service accounts.

## Project layout

```
a2ui-server/         Cloud Run: catalog.json + server.py (catalog + chat SSE proxy)
  server.py          FastAPI app: GET /etcatalog, POST /chat (SSE)
  catalog.json       A2UI catalog, official v0.9 JSON Schema format
  Dockerfile         Container image for Cloud Run (PORT-aware)
  build.sh / deploy.sh            Office: build + deploy to Cloud Run
  build.personal.sh / deploy.personal.sh  Personal variants
  a2ui.deploy.env / deploy.personal.env   Deployment config
a2ui-agent/          Agent Engine: the ADK agent + agents-cli deployment
  agent.py           ADK LlmAgent: google_search + get_a2ui_catalog (RestApiTool)
  agents-cli-manifest.yaml  Manifest for agents-cli (Agent Engine target)
  pyproject.toml     Package metadata (agents-cli installs the agent)
  build.sh / deploy.sh            Office: build + deploy to Agent Engine
  build.personal.sh / deploy.personal.sh  Personal variants
  a2ui.deploy.env / deploy.personal.env   Deployment config
```

## Deliberately out of scope

No frontend/renderer, no A2UI envelope builder, no validation layer, no DB or
auth on the a2ui-server (public demo). Session persistence is handled by
Agent Engine's managed session/memory services. A future client can consume
`/etcatalog` + `/chat` directly.

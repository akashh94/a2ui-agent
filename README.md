# a2ui-agent

A single-service A2A + A2UI agent on **Cloud Run**, following the official
[A2UI agent-development](https://a2ui.org/guides/agent-development/) flow.

> **New here?** Read the beginner docs:
> [docs/README.md](docs/README.md) → [01-overview](docs/01-overview.md) →
> [02-architecture](docs/02-architecture.md) → [03-flow](docs/03-flow.md) →
> [04-catalog](docs/04-catalog.md) → [05-glossary](docs/05-glossary.md) →
> [06-troubleshooting](docs/06-troubleshooting.md).

The service hosts an ADK `LlmAgent` over **A2A** (AgentCard + JSON-RPC). The
card advertises the **A2UI extension** with `supportedCatalogIds` pointing at
this service's custom catalog (`/catalog.json`). When a client that can render
that catalog sends the A2UI extension, the agent generates A2UI v0.9 messages
(as A2A `DataPart`s, mime `application/json+a2ui`) from **only the components
in that catalog**. Without the extension, it answers in plain text via
`google_search`.

```
a2ui-client (separate repo, own Cloud Run)     a2ui-agent (Cloud Run)
   │  GET /catalog.json  ──────────────────►  GET  /catalog.json   (custom catalog JSON)
   │  GET /.well-known/agent-card.json ─────► GET /.well-known/agent-card.json
   │                                          (card advertises A2UI ext + catalogId)
   │  POST /a2a/a2ui_agent  ◄──────────────►  POST /a2a/a2ui_agent
   │   JSON-RPC message/send                  (executor negotiates extension/catalog,
   │   extensions:[a2ui v0.9]                    runs LlmAgent, returns A2A parts)
   ▼   clientCapabilities
  renders DataParts (createSurface / updateComponents)
```

## What each piece does

- **`a2ui-agent/app/agent.py`** — the ADK `LlmAgent`. Tools:
  - `google_search` (sub-agent) for general/fact questions — the plain-text path.
  - `SendA2uiToClientToolset` — the A2UI tool path. Enabled only when the A2UI
    extension was negotiated for the session; its schema/examples come from
    session state (populated by the executor). The model calls
    `send_a2ui_json_to_client` with the A2UI message list.
- **`a2ui-agent/app/catalog.json`** — **the custom catalog** (single source of
  truth). `catalogId` = `https://<APP_URL>/catalog.json`. Components: Text,
  Button, Row, Column, Card. Loaded into `DirectJsonFormat` at build time
  (schema goes in the LLM request) **and** served at `/catalog.json` for
  clients to register renderers under the same `catalogId`.
- **`a2ui-agent/app/agent_executor.py`** — `A2aAgentExecutor` subclass (modeled
  on the official rizzcharts sample): per request it runs
  `try_activate_a2ui_extension` (extension present → A2UI path), resolves the
  catalog via `get_selected_catalog(clientCapabilities)`, and writes
  `system:a2ui_*` into session state. `A2uiEventConverter` turns the agent's
  `send_a2ui_json_to_client` responses into A2A `DataPart`s.
- **`a2ui-agent/app/app_utils/a2a.py`** — attaches the A2A routes using the
  `a2a-sdk` line that `a2ui-agent-sdk` pins (`a2a-sdk <0.4`): card at
  `/.well-known/agent-card.json`, JSON-RPC at `/a2a/a2ui_agent`
  (`A2AFastAPIApplication`).
- **`a2ui-agent/app/fast_api_app.py`** — FastAPI app (planner-style): lifespan
  builds the agent + `Runner` and attaches A2A routes; serves `/catalog.json`
  and `/`. (The demo client is no longer served here — see **a2ui-client**.)
- **a2ui-client (separate repo)** — a minimal **demo client** (static HTML/JS,
  deployed to its own Cloud Run service). It fetches the card + catalog,
  registers the 5 components as renderers, sends A2A `message/send` with the
  A2UI extension, and renders the returned `DataPart`s. The agent's base URL
  is configurable (`AGENT_URL` / `?agent=`); the agent must list the client's
  origin in `ALLOW_ORIGINS`.

## How the agent is constrained to the catalog

1. **Schema injection**: `DirectJsonFormat` renders the catalog schema +
   validated examples into the LLM request (via the toolset) whenever A2UI is
   active.
2. **Catalog-aware validation**: `SendA2uiToClientToolset` validates the
   model's payload against the catalog (`A2uiValidator`) before returning it;
   invalid payloads error back to the model, which retries.
3. **`createSurface.catalogId`**: the agent must echo the catalogId; a
   conforming renderer only renders components whose catalogId it registered.

## When the agent produces A2UI vs text (two gates)

- **Protocol gate (executor)**: the client's message carries
  `extensions: ["https://a2ui.org/a2a-extension/a2ui/v0.9"]` →
  `try_activate_a2ui_extension` activates A2UI. No extension → plain text
  (google_search) path.
- **Model gate (prompt)**: with A2UI active, the instruction tells the model
  to build a UI (`send_a2ui_json_to_client`) for UI-worthy requests and answer
  normally otherwise.

## Deploy (Cloud Run)

Prereqs: `gcloud` + `docker` on PATH. The service runs as the default Cloud Run
service account, which needs `roles/aiplatform.user` on the project to call
Gemini via Vertex (grant once if missing).

```bash
# personal (adk-tut-499512 / us-central1)
cd a2ui-agent
./build.personal.sh      # lint + smoke import
./deploy.personal.sh     # docker build + push + gcloud run deploy

# office (labs-gcp-msls-16495-1782829337 / us-east1) — same with ./build.sh ./deploy.sh
```

`deploy.personal.env` sets `PROJECT_ID`, `REGION`, `ARTIFACT_REGISTRY`,
`SERVICE_NAME`, `APP_URL` (= the public service URL — the card + catalogId
advertise it), `AGENT_MODEL`, `MODEL_LOCATION`, `ALLOW_ORIGINS` (the
separately-deployed a2ui-client's origin, so the browser client can call the
agent cross-origin).

Endpoints after deploy:

| Endpoint | Purpose |
|---|---|
| `GET /catalog.json` | the custom catalog (register renderers under its `catalogId`) |
| `GET /.well-known/agent-card.json` | A2A card (A2UI extension + `supportedCatalogIds`) |
| `POST /a2a/a2ui_agent` | A2A JSON-RPC (`message/send`, `message/sendStreaming`) |

## Try it

```bash
# card (shows the A2UI extension + supportedCatalogIds)
curl https://a2ui-agent-personal-947331501288.us-central1.run.app/.well-known/agent-card.json

# catalog
curl https://a2ui-agent-personal-947331501288.us-central1.run.app/catalog.json

# text path (no extension)
curl -X POST https://a2ui-agent-personal-947331501288.us-central1.run.app/a2a/a2ui_agent \
  -H 'Content-Type: application/json' \
  -d '{"id":"1","jsonrpc":"2.0","method":"message/send","params":{"message":{"messageId":"m1","role":"user","parts":[{"text":"what is the capital of France?"}]}}}'

# A2UI path (extension + clientCapabilities) -> application/json+a2ui DataParts
curl -X POST https://a2ui-agent-personal-947331501288.us-central1.run.app/a2a/a2ui_agent \
  -H 'Content-Type: application/json' \
  -d '{"id":"2","jsonrpc":"2.0","method":"message/send","params":{"message":{"messageId":"m2","role":"user","extensions":["https://a2ui.org/a2a-extension/a2ui/v0.9"],"metadata":{"a2uiClientCapabilities":{"supportedCatalogIds":["https://a2ui-agent-personal-947331501288.us-central1.run.app/catalog.json"]}},"parts":[{"text":"show me an A2UI demo with a button and some text"}]}}}'
```

Open the **a2ui-client** repo's deployed page in a browser for the rendered
demo, or run its static files locally and point them at this agent with
`?agent=<this service URL>`.

## Customizing components

To add/change components, edit `app/catalog.json` (JSON Schema per component:
`component` const, `required`, props; keep `$defs.anyComponent.oneOf` in sync)
and add example message lists under `app/examples/`. Redeploy. The renderers
in the a2ui-client repo's `client.js` must implement each component name you
add.

## Notes / gotchas

- `a2ui-agent-sdk` pins `a2a-sdk <0.4` — the A2A serving helpers
  (`A2AFastAPIApplication`, `DefaultRequestHandler`, old client) come from
  that line, NOT the planner's `a2a-sdk 1.x`. Keep the pin in `pyproject.toml`.
- `CatalogConfig.from_path` mangles Windows drive paths — the code uses
  `FileSystemCatalogProvider` with an absolute path instead.
- Cloud Run needs `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_LOCATION` (injected via
  `--update-env-vars`) and `APP_URL` as the public https URL (the card/catalog
  advertise it).
- Session/memory are in-memory (per instance). Fine for a demo; use managed
  services for multi-instance production.

## Project layout

```
a2ui-agent/            the whole project (this repo)
├── a2ui-agent/        Cloud Run: A2A + A2UI agent (single service)
│   ├── app/           agent code + catalog
│   │   ├── agent.py           LlmAgent: google_search + SendA2uiToClientToolset
│   │   ├── agent_executor.py  A2aAgentExecutor subclass (extension/catalog negotiation)
│   │   ├── fast_api_app.py    FastAPI: lifespan + A2A routes + /catalog.json
│   │   ├── app_utils/a2a.py   A2A route attach (A2AFastAPIApplication)
│   │   ├── catalog.json       Custom catalog (source of truth, served at /catalog.json)
│   │   └── examples/          Validated A2UI few-shot examples
│   ├── Dockerfile
│   ├── build.sh / deploy.sh            Office: build + deploy to Cloud Run
│   ├── build.personal.sh / deploy.personal.sh  Personal variants
│   └── a2ui.deploy.env / deploy.personal.env   Deployment config
├── docs/              beginner docs (see the reading order above)
└── README.md          this file

a2ui-client/           (SEPARATE repo) the browser demo client, deployed to
                       its own Cloud Run service; points at this agent via
                       AGENT_URL / ?agent=
```

## Deliberately out of scope

The a2ui-client demo renders only the 5 catalog components with minimal CSS.
This agent has no DB, auth, or multi-user session persistence (in-memory
session/memory per instance). It is a public demo, like the financial
planner.

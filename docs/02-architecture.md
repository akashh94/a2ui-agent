# 02 — Architecture

## Big picture

```
┌────────────── Browser (serves the a2ui-client repo) ─────────────┐
│                                                                  │
│   a2ui-client/  (SEPARATE repo, own Cloud Run service)           │
│     index.html + client.js                                        │
│       • fetches the agent card  (what can the agent do?)          │
│       • fetches the catalog    (which components can render?)     │
│       • registers the 5 components as "renderers"                 │
│       • sends A2A messages (with the A2UI extension)              │
│       • renders returned A2UI DataParts into the page             │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTPS (JSON-RPC + SSE) — cross-origin,
                               │ allowed by the agent's ALLOW_ORIGINS
                               ▼
┌──────────────────── Cloud Run: the a2ui-agent service ───────────────┐
│                                                                      │
│  FastAPI app (app/fast_api_app.py)                                   │
│   ├─ GET  /catalog.json                 → the catalog JSON           │
│   ├─ GET  /.well-known/agent-card.json  → the agent card            │
│   └─ POST /a2a/a2ui_agent               → A2A JSON-RPC              │
│                                                                      │
│  A2A layer (app/app_utils/a2a.py)                                    │
│   └─ builds AgentCard, wires JSON-RPC to the executor               │
│                                                                      │
│  Executor (app/agent_executor.py)                                    │
│   └─ A2aAgentExecutor subclass                                        │
│      • checks the A2UI extension (Gate 1)                           │
│      • negotiates the catalog from client capabilities               │
│      • stores catalog + examples in session state                    │
│      • converts agent output into A2A DataParts (via A2uiEventConverter)│
│                                                                      │
│  The agent (app/agent.py)                                            │
│   └─ ADK LlmAgent: Gemini via Vertex AI                              │
│      tools: google_search  +  send_a2ui_json_to_client (toolset)     │
│      (schema/examples injected from session state when A2UI active)  │
│                                                                      │
│  Catalog (app/catalog.json + app/examples/)                          │
│   └─ the whitelist of components the agent may emit                  │
└──────────────────────────────────────────────────────────────────────┘
```

## The four roles (get these straight first)

| Role | What it is | Where |
|---|---|---|
| **Agent** | The AI that decides what to say / what UI to build | `app/agent.py` (an ADK `LlmAgent`) |
| **Catalog** | A JSON schema whitelisting UI components + their properties | `app/catalog.json` |
| **Server / host** | The process that exposes the agent over HTTP and serves the card + catalog | `app/fast_api_app.py` + `app/app_utils/a2a.py` |
| **Client** | A program (browser page) that can render the catalog's components | the separate **a2ui-client** repo |

> Confusion alert: "server" here is NOT a separate machine from the agent.
> It is the FastAPI container that *hosts* the agent and exposes it over A2A.
> The "client" is the browser page that renders UI — it lives in its own repo
> (`a2ui-client`) and its own Cloud Run service, and talks to the agent
> cross-origin. A human user talks to the client; the client talks to the
> server/agent.

## Files, one by one

### `app/fast_api_app.py` — the web service (entry point)

- Creates the FastAPI app (via `get_fast_api_app` from ADK, planner-style).
- On startup (`lifespan`) it:
  1. builds the agent (`app.agent.build_agent()`),
  2. wraps it in an ADK `Runner` with in-memory session/artifact/memory,
  3. attaches the A2A routes (`attach_a2a_routes`).
- Serves `GET /catalog.json` (reads the file) and answers `/` with pointers.
  The demo client is **not** served here — it lives in the separate
  a2ui-client repo.

Env vars it needs: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `APP_URL`
(the public https URL — used to build card URLs and the catalogId),
`ALLOW_ORIGINS` (the a2ui-client's origin, so the browser can call this agent
cross-origin).

### `app/app_utils/a2a.py` — A2A route attachment

- Builds the **AgentCard** (`AgentCardBuilder`): name, version, and
  **capabilities** = the ADK executor extension **plus the A2UI extension**.
- The A2UI extension advertises:
  - `acceptsInlineCatalogs: true`
  - `supportedCatalogIds: ["https://<APP_URL>/catalog.json"]`
- Constructs the custom executor and mounts the JSON-RPC endpoint at
  `/a2a/a2ui_agent` using `A2AFastAPIApplication` (from the `a2a-sdk` line
  that `a2ui-agent-sdk` requires — `a2a-sdk < 0.4`).

### `app/agent.py` — the LLM agent definition

- `build_agent()` returns an ADK `LlmAgent` named `a2ui_agent` with two tools:
  - **`google_search`** (a sub-agent) — general questions.
  - **`SendA2uiToClientToolset`** — provides the `send_a2ui_json_to_client`
    tool that appears **only when A2UI is enabled for the session**.
- The instruction (system prompt) tells the model:
  - UI request → call `send_a2ui_json_to_client` with a valid A2UI message
    list built from the catalog.
  - Otherwise → plain text (+ google_search for facts).
- `build_inference_format()` builds the `DirectJsonFormat` (from
  `a2ui-agent-sdk`) over `app/catalog.json` + `app/examples/`. This object is
  what renders the catalog schema into the prompt and validates output.
- Three module-level functions (`a2ui_enabled_provider`, `a2ui_catalog_provider`,
  `a2ui_examples_provider`) read **session state** — the toolset uses them to
  decide whether the A2UI tool exists and what schema/examples to inject.

### `app/agent_executor.py` — the glue between A2A and the agent

Subclasses ADK's `A2aAgentExecutor`. On every request it overrides
`_prepare_session`:

1. `try_activate_a2ui_extension(context, agent_card)` — **Gate 1**.
   Reads the client's message `extensions`; if it contains the A2UI URI, A2UI
   is active (returns the version, e.g. "0.9"), else `None`.
2. Creates the session (via the parent class).
3. Seeds session state: `expression` and `base_url` (mirrors the official
   sample).
4. If A2UI is active: reads the client's capabilities from message metadata
   (`a2uiClientCapabilities.supportedCatalogIds`), resolves the catalog via
   `inference_format.get_selected_catalog(...)`, loads validated examples, and
   stores `system:a2ui_enabled/catalog/examples` in session state (as an ADK
   event). The toolset + converter pick those up per-session.

The executor is configured with **`A2uiEventConverter`** — the piece that
watches the agent's streamed events and converts `send_a2ui_json_to_client`
tool responses into **A2A `DataPart`s** with mime `application/json+a2ui` (and
passes plain text through).

### `app/catalog.json` — the custom catalog (single source of truth)

A JSON Schema document. Top-level keys:

- `$schema`, `$id`, `title`, `description`
- **`catalogId`** = `https://<APP_URL>/catalog.json` — the identity clients
  and the agent agree on.
- **`components`** — one JSON Schema per component: `Text`, `Button`, `Row`,
  `Column`, `Card`.
- **`$defs`** — shared sub-schemas (`CatalogComponentCommon`, `anyComponent`
  = the union of all components, `anyFunction`).

Each component schema uses `allOf` to mix in shared "common" props (from the
A2UI spec's `common_types.json`) with its own `properties`, and `required`.
See [04-catalog.md](04-catalog.md) for how to read/add them.

### `app/examples/` — few-shot examples

JSON files, each a full valid A2UI message list (e.g. a hello demo, a card
demo, a row of buttons). Loaded and **validated** at startup; injected into
the LLM request as examples when A2UI is active. This is how the model learns
the *shape* of good output without hallucinating.

### a2ui-client (SEPARATE repo) — the demo client (renders the UI)

`index.html` + `client.js`, pure static files, deployed to its own Cloud Run
service. Its agent base URL is configurable (`AGENT_URL` in `client.js`, or
`?agent=<agent-url>` per page).

- On load: fetches the card, confirms the A2UI extension, fetches
  `/catalog.json`, and "registers" a renderer function for each component
  name (Text → a `<div>`, Button → a `<button>`, Row/Column → flex
  containers, Card → a bordered box).
- `sendMessage(text)`: builds an A2A JSON-RPC `message/send` request with:
  - `extensions: ["https://a2ui.org/a2a-extension/a2ui/v0.9"]`,
  - metadata `a2uiClientCapabilities: {supportedCatalogIds: [catalogId]}`.
- On the JSON result, it walks the returned parts; `text` parts are shown in
  the chat log, `data` parts (A2UI messages) are rendered:
  - `createSurface` → creates the surface container.
  - `updateComponents` → registers component elements by id, finds the root,
    and mounts it.

### Deploy files (not Python)

- `Dockerfile` — builds the container (`pip install .`, runs uvicorn).
- `build.personal.sh` / `build.sh` — lint + format + type-check + smoke
  import (via `uv`).
- `deploy.personal.sh` / `deploy.sh` — `docker build` + `gcloud run deploy`
  with env vars (`AGENT_MODEL`, `MODEL_LOCATION`, `GOOGLE_CLOUD_PROJECT`,
  `GOOGLE_CLOUD_LOCATION`, `APP_URL`, `ALLOW_ORIGINS`).
- `deploy.personal.env` / `a2ui.deploy.env` — the actual values (personal vs
  office project/region/service name, plus the a2ui-client origin for CORS).

## What is NOT here (deliberately)

- No database, no auth, no multi-user sessions (in-memory only; fine for a
  demo/single instance).
- No client code — the demo client lives in the separate **a2ui-client** repo
  and renders only the 5 catalog components with minimal CSS (no full-featured
  renderer like `@a2ui/lit`).

## Data flow in one sentence

Client discovers card → client advertises the A2UI extension + its supported
catalog → executor activates A2UI and stores the negotiated catalog in session
state → the agent (prompted with that catalog's schema + examples) emits
`send_a2ui_json_to_client` tool calls → `A2uiEventConverter` turns them into
A2A `DataPart`s → client renders.

Next: [03-flow.md](03-flow.md) for the minute-by-minute walkthrough.

# 05 — Glossary

Simple definitions of every term you will meet in this project. Roughly in the
order you meet them.

## Concepts

| Term | Definition |
|---|---|
| **Agent** | An AI program that decides what to say or do. Here: an ADK `LlmAgent` using Gemini. |
| **LLM / model** | The large language model (Gemini) that does the actual "thinking". |
| **ADK** (Agent Development Kit) | Google's Python framework for building agents. Gives us `LlmAgent`, `Runner`, tools, sessions. |
| **Tool** | A function an agent can call (e.g. web search, or "send this UI to the client"). |
| **Session** | A conversation. ADK keeps per-session memory/state (in-memory here). |
| **Runner** | The ADK object that executes an agent given a session and a message, yielding events. |
| **A2A** (Agent-to-Agent) | A protocol for agents to talk to each other (and to agent-capable apps) over JSON-RPC. Includes the **agent card** for discovery. |
| **Agent card** | A JSON "business card" at `/.well-known/agent-card.json`: name, description, and **capabilities** (extensions it supports). |
| **Extension** | A declared capability on the card / requested by the client. A2UI is one such extension. |
| **A2UI** | "Agent-to-User Interface": the JSON format agents use to describe UIs (create a surface, add components, update data). |
| **Catalog** | A JSON Schema whitelist of UI components an agent may use and a client can render. |
| **`catalogId`** | The unique URL/ID of a catalog. Both agent and client reference it to agree on components. |
| **Component** | One UI building block (Text, Button, Row, Column, Card…), defined as a JSON Schema in the catalog. |
| **Surface** | A renderable screen/panel. A2UI messages create/update surfaces by `surfaceId`. |
| **Renderer** | Client-side code that turns a component description into a real DOM element. |
| **DataPart** | An A2A message part carrying structured data (here: one A2UI message) with a `mimeType`. |
| **JSON-RPC** | The message protocol A2A uses: `{jsonrpc, id, method, params}`. Methods here: `message/send`, `message/sendStreaming`. |
| **ClientCapabilities** | Metadata a client sends to say which catalogs / features it supports (`a2uiClientCapabilities.supportedCatalogIds`). |
| **`DirectJsonFormat`** | The `a2ui-agent-sdk` object that holds the catalog(s), renders their schema into LLM instructions, and validates output. |
| **`SendA2uiToClientToolset`** | An ADK toolset that provides the `send_a2ui_json_to_client` tool (enabled only when A2UI is active). |
| **`A2uiEventConverter`** | Converts the agent's tool responses / output into A2A `DataPart`s (with mime `application/json+a2ui`). |
| **Executor** | The bridge between the A2A HTTP layer and the ADK agent. Ours is `A2uiAgentExecutor`. |
| **Cloud Run** | Google's serverless container platform where this service runs. |
| **Vertex AI** | Google's AI platform; provides Gemini models + project-scoped credentials. |
| **ADC** (Application Default Credentials) | The ambient credentials Cloud Run / gcloud use to call Google APIs. |

## A2UI message types (v0.9) used here

| Message | Purpose | Example payload shape |
|---|---|---|
| `createSurface` | Start a new renderable surface, naming its `catalogId`. | `{ "surfaceId": "s1", "catalogId": "https://…/catalog.json" }` |
| `updateComponents` | Add/replace the component tree on a surface. | `{ "surfaceId": "s1", "components": [ … ] }` |
| `updateDataModel` | Push data the components can bind to. | (not used by the 5-component demo) |
| `deleteSurface` | Remove a surface. | (not used by the demo) |

## Components in our catalog

| Component | What it renders (client) | Key properties |
|---|---|---|
| `Text` | a `<div>` with text | `text` (required), `variant` (h1…body) |
| `Button` | a `<button>` | `child` (id of a Text label), `action.event.name`, `variant` |
| `Row` | a horizontal flex container | `children` (array of component ids), `justify`, `align` |
| `Column` | a vertical flex container | `children`, `justify`, `align` |
| `Card` | a bordered box with optional title | `child` (single id), `title` |

## Key files → what they are

| File | Role |
|---|---|
| `app/fast_api_app.py` | Web server (FastAPI), startup wiring, static routes |
| `app/app_utils/a2a.py` | Builds the card, attaches A2A JSON-RPC |
| `app/agent.py` | Defines the LLM agent + inference format + session-state providers |
| `app/agent_executor.py` | Extension/catalog negotiation + event conversion |
| `app/catalog.json` | The custom catalog (source of truth) |
| `app/examples/*.json` | Validated few-shot A2UI examples |
| (separate repo) `a2ui-client/index.html` + `client.js` | Demo client (renders the UIs) |
| `deploy.personal.sh` | Build + push + deploy to Cloud Run (personal env) |

Next: [06-troubleshooting.md](06-troubleshooting.md).

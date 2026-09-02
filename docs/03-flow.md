# 03 — Step-by-step flow

This page walks through exactly what happens, in order, when someone uses the
demo. There are two journeys:

1. [Page load / discovery](#1-page-load--discovery)
2. [A plain-text question](#2-a-plain-text-question-eg-what-is-the-capital-of-france)
3. [An A2UI request](#3-an-a2ui-request-eg-show-me-a-demo-with-a-button-and-text)

We use the live service URL `https://a2ui-agent-personal-947331501288.us-central1.run.app`
in the examples; replace it with your deployed URL.

---

## 1. Page load / discovery

When you open `https://<service>/client`:

1. The browser loads `index.html` + `client.js` (static files served by the
   same FastAPI app).
2. `client.js` calls **`GET /.well-known/agent-card.json`** and receives the
   agent card:

```json
{
  "name": "a2ui_agent",
  "capabilities": {
    "extensions": [
      { "uri": "https://google.github.io/adk-docs/a2a/a2a-extension/" },
      {
        "uri": "https://a2ui.org/a2a-extension/a2ui/v0.9",
        "params": {
          "acceptsInlineCatalogs": true,
          "supportedCatalogIds": [
            "https://<service>/catalog.json"
          ]
        }
      }
    ]
  }
}
```

   The client checks: *"Does the agent advertise the A2UI extension I know
   how to render?"* → yes.

3. `client.js` calls **`GET /catalog.json`** and reads `catalogId` +
   `components`. It registers a renderer for each component name
   (`Text`, `Button`, `Row`, `Column`, `Card`). Now the client can render
   anything the agent produces **from that catalog**.

> This is the "agreement": the agent advertises `supportedCatalogIds` in its
> card; the client confirms it can render that exact `catalogId`.

---

## 2. A plain-text question (e.g. "what is the capital of France?")

### What the user does

Types the question in the demo page and clicks Send.

### What the client sends

`client.js` builds an A2A JSON-RPC request. For a plain chat box that cannot
render A2UI, it would send **no** `extensions`:

```json
POST /a2a/a2ui_agent
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "m-…",
      "role": "user",
      "parts": [{ "text": "what is the capital of France?" }]
    }
  }
}
```

> In the bundled demo client the A2UI extension is always attached (the page
> *can* render), but the executor logic is the same: the **model gate** decides
> a UI is not needed, so the answer is text.

### Server-side steps

4. The FastAPI JSON-RPC handler (`/a2a/a2ui_agent`) receives the request and
   hands it to the **executor** (`A2uiAgentExecutor`).
5. `_prepare_session` runs `try_activate_a2ui_extension(...)`.
   - Extension present → A2UI active (UI path).
   - Absent → A2UI inactive.
   For this question (no extension or the model later judges text is fine),
   it continues on the plain path.
6. A session is created and stored in the in-memory session service.
7. The ADK `Runner` runs the `LlmAgent` with the user's message.
8. The agent's prompt says: *general/fact question → use `google_search`*.
   Gemini calls the `google_search_agent` sub-agent.
9. The search tool returns grounded text ("The capital of France is Paris.").
10. ADK emits the final model event; the executor's `A2uiEventConverter` sees
    a plain `text` part and passes it through unchanged.

### What the client receives & shows

```json
{
  "result": {
    "status": { "state": "completed" },
    "artifacts": [{
      "parts": [{ "kind": "text", "text": "The capital of France is Paris." }]
    }]
  }
}
```

`client.js` sees a `text` part → appends it to the chat log. No UI is
rendered. Done.

---

## 3. An A2UI request (e.g. "show me a demo with a button and text")

### What the client sends

```json
POST /a2a/a2ui_agent
{
  "jsonrpc": "2.0",
  "method": "message/send",
  "params": {
    "message": {
      "messageId": "m-…",
      "role": "user",
      "extensions": ["https://a2ui.org/a2a-extension/a2ui/v0.9"],
      "metadata": {
        "a2uiClientCapabilities": {
          "supportedCatalogIds": ["https://<service>/catalog.json"]
        }
      },
      "parts": [{ "text": "show me an A2UI demo with a button and text" }]
    }
  }
}
```

Note the two additions vs the text case:
- **`extensions`** — the client declares "I can render A2UI v0.9" (**Gate 1**).
- **`metadata.a2uiClientCapabilities.supportedCatalogIds`** — the client
  declares which catalog(s) it has registered.

### Server-side steps

11. `_prepare_session` → `try_activate_a2ui_extension(...)` sees the A2UI URI
    in `extensions` → **A2UI is active**.
12. It reads `a2uiClientCapabilities` from message metadata.
13. `inference_format.get_selected_catalog(capabilities)` picks the catalog
    both sides support — ours, since the client listed its ID.
14. It loads + validates the few-shot examples
    (`inference_format.load_examples(...)`).
15. It writes session state (as an ADK event):
    - `system:a2ui_enabled = true`
    - `system:a2ui_catalog = <the A2uiCatalog object>`
    - `system:a2ui_examples = "<validated example strings>"`
16. The `Runner` runs the agent. Because A2UI is enabled, the toolset's
    `get_tools()` returns the **`send_a2ui_json_to_client`** tool, and its
    `process_llm_request()` **injects the catalog schema + examples into the
    LLM request** (from session state).
17. Gemini reads the prompt: *UI request → build components from the catalog
    and call `send_a2ui_json_to_client`*. The model produces something like:

```json
[
  { "version": "v0.9",
    "createSurface": { "surfaceId": "demo_surface",
                       "catalogId": "https://<service>/catalog.json" } },
  { "version": "v0.9",
    "updateComponents": { "surfaceId": "demo_surface",
      "components": [
        { "id": "root", "component": "Column", "children": ["header_text", "body_text", "action_button"], "justify": "start", "align": "start" },
        { "id": "header_text", "component": "Text", "text": "Hello from A2UI", "variant": "h2" },
        { "id": "body_text", "component": "Text", "text": "This is a demo of an agent-driven UI." },
        { "id": "action_button", "component": "Button", "child": "action_button_label", "variant": "primary", "action": { "event": { "name": "demo_button_click" } } },
        { "id": "action_button_label", "component": "Text", "text": "Click Me" }
      ] } }
]
```

18. **Validation:** `send_a2ui_json_to_client` validates this payload against
    the catalog (`A2uiValidator`) before accepting it. If the model used a
    component not in the catalog (e.g. `Chart`) or missed a required field,
    the tool returns an error and the model is expected to retry with a fixed
    payload.
19. On success the tool returns the validated JSON
    (`skip_summarization` is set so the model does not narrate it).
20. The **`A2uiEventConverter`** (configured on the executor) sees the tool
    response, reads the catalog from session state, and converts each A2UI
    message into an **A2A `DataPart`**:

```json
{
  "kind": "data",
  "data": { "version": "v0.9", "createSurface": { "surfaceId": "demo_surface", "catalogId": "https://<service>/catalog.json" } },
  "metadata": { "mimeType": "application/json+a2ui" }
}
```

### What the client receives & renders

The JSON-RPC result contains the A2A parts (both the task history and
`artifacts[].parts`):

```json
{ "result": {
    "status": { "state": "completed" },
    "artifacts": [{
      "parts": [
        { "kind": "data", "data": { "version": "v0.9", "createSurface": { … } },
          "metadata": { "mimeType": "application/json+a2ui" } },
        { "kind": "data", "data": { "version": "v0.9", "updateComponents": { … } },
          "metadata": { "mimeType": "application/json+a2ui" } }
      ]
    }]
} }
```

`client.js`:
21. sees `createSurface` → creates a fresh surface `<div>`.
22. sees `updateComponents` → for each component registers an element by `id`
    (root Column first, then children), finds the root, and mounts it.
23. The user now sees a real rendered column with a heading, body text, and a
    primary button labelled "Click Me". Clicking fires the button's
    `action.event.name` (logged in the demo).

---

## Sequence diagram (A2UI path)

```
User          client.js            FastAPI/executor        agent (Gemini)
 │  clicks Send │                        │                       │
 │─────────────>│  POST message/send     │                       │
 │              │  extensions:[a2ui]     │                       │
 │              │  capabilities:[catId]  │                       │
 │              │───────────────────────>│                       │
 │              │                        │ try_activate_a2ui_ext │
 │              │                        │  → "0.9"              │
 │              │                        │ get_selected_catalog  │
 │              │                        │ store system:a2ui_*    │
 │              │                        │──────────────────────>│
 │              │                        │  (run agent)           │
 │              │                        │  schema+examples →     │
 │              │                        │  model                 │
 │              │                        │  ← send_a2ui_json call │
 │              │                        │  validate vs catalog   │
 │              │                        │  A2uiEventConverter    │
 │              │  JSON result           │  → DataParts           │
 │              │<───────────────────────│                       │
 │  render UI   │                        │                       │
 │<─────────────│                        │                       │
```

## Where the two paths split (summary)

| | Text path | A2UI path |
|---|---|---|
| Client sends `extensions:[a2ui]` | no | yes |
| `system:a2ui_enabled` | false | true |
| `send_a2ui_json_to_client` tool | hidden | present |
| Schema + examples injected | no | yes |
| Agent output | text | A2UI DataParts |
| Client shows | chat log text | rendered components |

Next: [04-catalog.md](04-catalog.md) — the catalog in depth.

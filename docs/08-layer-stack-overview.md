# 08 — Layer stack & concept map

A map of the whole runtime stack, plus a concept menu for deep dives. Keep this
open when studying the codebase: §4 is a checklist — pick a number, we go deep,
tick it off.

Complements [02-architecture.md](02-architecture.md) (the pieces and files) and
[07-flow-component-diagram.md](07-flow-component-diagram.md) (the runtime
hand-offs for one request). This doc is the *vertical* view: one process, top to
bottom, and which layer owns what.

## 1. The layer stack — one process, top to bottom

```
                         ▲ OUTBOUND (events → JSON)
                         │
┌────────────────────────┴─────────────────────────────────────────────┐
│  a2ui-client  (SEPARATE repo, its own Cloud Run)                     │
│  browser page: fetches card + catalog, sends A2A, renders DataParts  │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  HTTPS · JSON-RPC 2.0 (+ SSE for streaming)
                         ▼ INBOUND (JSON → events)
╔══════════════════════════════════════════════════════════════════════╗
║  Cloud Run · a2ui-agent  — ONE ASGI process                          ║
║                                                                      ║
║  [1] FastAPI app (get_fast_api_app)      bytes ⇄ Python objects      ║
║      POST /a2a/a2ui_agent   GET /catalog.json   GET /.well-known/... ║
║  ─────────────────────────────────────────────────────────────────   ║
║  [2] A2AFastAPIApplication               HTTP routes + agent card    ║
║      (add_routes_to_app — not an app itself)                         ║
║  ─────────────────────────────────────────────────────────────────   ║
║  [3] JSONRPCHandler                      method ⇄ handler + envelope ║
║      message/send · message/stream · tasks/get · tasks/cancel · ...  ║
║  ─────────────────────────────────────────────────────────────────   ║
║  [4] DefaultRequestHandler               ORCHESTRATION               ║
║      TaskManager · EventQueue · producer task · ResultAggregator     ║
║      owns: task lifecycle, streaming, cancel, resubscribe            ║
║  ═════════════════════════════════════════════════════════════════   ║
║  [5] A2uiAgentExecutor  ◄── THE SEAM (A2A ⇄ ADK)                     ║
║      _prepare_session override = GATE 1 + catalog negotiation        ║
║      A2uiEventConverter = tool result → DataPart                     ║
║  ═════════════════════════════════════════════════════════════════   ║
║  [6] Runner (ADK)                        session · state · memory    ║
║      run_async() → stream of ADK Events                              ║
║  ─────────────────────────────────────────────────────────────────   ║
║  [7] LlmAgent "a2ui_agent" (Gemini)      reasoning + tools           ║
║      google_search · send_a2ui_json_to_client                        ║
╚══════════════════════════════════════════════════════════════════════╝
```

## 2. The round trip — where each conversion happens

```
client                                            server
  │                                                   │
  │ message/send                                      │
  │  extensions: [.../a2ui/v0.9]                      │
  │  metadata.a2uiClientCapabilities ─────────────►  [1][2][3]
  │                                                       │
  │                                        [4] TaskManager → EventQueue
  │                                            spawn producer task
  │                                                       │
  │                                        [5] _prepare_session   ◄ GATE 1
  │                                            banner: A2UI v0.9?
  │                                            pick catalog from capabilities
  │                                            ──writes─► session.state
  │                                                       │
  │                                        [6] Runner.run_async
  │                                                       │
  │                                        [7] Gemini decides: plain text?
  │                                            or call send_a2ui_json_to_client
  │                                                       │
  │                                        [5] A2uiEventConverter
  │                                            tool result → DataPart
  │                                            mime application/json+a2ui
  │  ◄──── JSON-RPC result / SSE events ───── [4][3][2][1]
  │
  │ renders catalog components from DataParts
```

## 3. The shared substrate (no single layer owns it)

```
   session.state  ──────────────────────────────────────────────
     system:a2ui_enabled   ← written by [5] _prepare_session
     system:a2ui_catalog   ←   read by [7] toolset  (schema injection)
     system:a2ui_examples  ←   read by [5] converter (to validate/convert)
   ──────────────────────────────────────────────────────────────
   app/catalog.json + app/examples/     the whitelist (single source of truth)
   InMemoryTaskStore / InMemory*        all ephemeral, process-local
```

## 4. Who ships which layer

| # | Object | Ships in | Job | Where in this repo |
|---|---|---|---|---|
| 1 | FastAPI app | ADK + this repo | HTTP host; mounts everything on one port | `app/fast_api_app.py:81` |
| 2 | `A2AFastAPIApplication` | a2a-sdk | installs protocol routes + card endpoints | `app/app_utils/a2a.py:91` |
| 3 | `JSONRPCHandler` | a2a-sdk | method routing, envelopes, capability checks | built inside [2] |
| 4 | `DefaultRequestHandler` | a2a-sdk | tasks, queues, streaming, cancel | `app/app_utils/a2a.py:86` |
| 5 | `A2uiAgentExecutor` | ADK base + this repo | A2A ⇄ ADK seam; all local policy | `app/agent_executor.py` |
| 6 | `Runner` | ADK | sessions/state, drives the agent | `app/fast_api_app.py:58` |
| 7 | `LlmAgent` | ADK + this repo | model, prompt, tools | `app/agent.py` |

The A2A spec defines the contract → `a2a-sdk` implements transport / JSON-RPC /
task plumbing → ADK bridges A2A ⇄ agent → **this repo supplies only the domain
glue** (agent, catalog, A2UI negotiation, part conversion).

## 5. Concept menu (deep-dive checklist)

- [ ] 1. **Transport / ASGI** — why one app; `add_routes_to_app()` vs `build()`
- [ ] 2. **Agent Card** — discovery, capabilities, extensions, catalog advertising
- [ ] 3. **JSON-RPC binding** — methods, envelopes, `@validate`, error codes
- [ ] 4. **`RequestHandler` / task lifecycle** — TaskStore, queues, producer, terminal states
- [ ] 5. **`AgentExecutor` seam** — converters both directions; why it pushes to a queue
- [ ] 6. **`Runner` + session state** — why the negotiated context lives there
- [ ] 7. **Gate 1** — A2UI extension negotiation (`try_activate_a2ui_extension`)
- [ ] 8. **Catalog negotiation** — `a2uiClientCapabilities` → `get_selected_catalog`
- [ ] 9. **Gate 2 + toolset** — schema/examples injection, `send_a2ui_json_to_client`
- [ ] 10. **Event conversion** — ADK `Event` → A2A `Task`/`Artifact`/`Status` + `DataPart`
- [ ] 11. **Streaming** — SSE vs unary, `message/stream`, `tasks/resubscribe`
- [ ] 12. **Failure modes** — in-memory state, multi-instance, missing catalogId

## 6. Established so far

Conclusions already reached, so a later session doesn't have to re-derive them.

- **No Campfire anywhere in this repo.** Campfire is a Gemini Enterprise search
  *data store* connector — unrelated to A2A/A2UI. Nothing here references it.
- **Only ONE FastAPI app at runtime.** `A2AFastAPIApplication` is *not* a FastAPI
  subclass; it is a `JSONRPCApplication` (a plain ABC helper) that installs route
  handlers onto the existing app. `A2AFastAPI(FastAPI)` — the real subclass — is
  only created by `.build()`, which this repo never calls.
- **`InMemoryTaskStore` is A2A task persistence**, handed to
  `DefaultRequestHandler`, not used by the executor. It is a `dict` + `asyncio.Lock`:
  process-local and ephemeral, so tasks are lost on restart and unsafe across
  multiple Cloud Run instances. Fine here because the client does one streaming
  round trip and never re-fetches a task.
- **`DefaultRequestHandler` exists because one execution must serve many
  requests.** The executor runs once and pushes to an `EventQueue`; the queue
  outlives the request, which is what makes `tasks/resubscribe` and
  `tasks/cancel` possible at all.
- **The executor exists as the A2A ⇄ ADK seam.** It is the only object that sees
  both vocabularies; `execute()` returns `None` and pushes events, deliberately.
  This repo overrides only `_prepare_session`.
- **Layering principle:** a layer is justified where *ownership* and
  *rate-of-change* differ (public A2A spec vs ADK vs your catalog vs the client
  repo). Where one team owns everything and it all changes together, the layers
  would be pure overhead.

Next: [README.md](README.md) for the navigation index.

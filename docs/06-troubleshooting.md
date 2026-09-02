# 06 — Troubleshooting (beginner)

Common questions and errors, and how to fix them.

## Setup / environment

### Docker: "failed to connect to the docker API … daemon is running"

Docker Desktop is not running (or still starting).

```text
ERROR: failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
```

Fix: start **Docker Desktop** and wait until the whale is steady before
running `deploy.personal.sh`.

### `agents-cli: command not found` / build script fails on PATH

The build script installs `uv`/tools itself, but on Windows Git Bash the
`~/.local/bin` may not be on PATH. Run:

```bash
export PATH="$HOME/.local/bin:$PATH"
./build.personal.sh
```

### Python can't reach the Cloud Run URL (`getaddrinfo failed` / DNS)

The dev box's Python resolver sometimes fails to resolve `.run.app` even
though `curl` works. Use `curl` for one-off checks, or retry.

## Runtime / deploy

### Card or catalog returns 404 after deploy

- Confirm the service is actually deployed to the URL you expect:
  `gcloud run services list` (or the deploy script's printed URL).
- Cloud Run needs `APP_URL` set to the **public https URL** so the card /
  catalog advertise correct links. Check the env on the service:
  `gcloud run services describe a2ui-agent-personal --region us-central1 --format='value(spec.template.spec.containers[0].env)'`.
- The catalog is served from a **file in the image** (`app/catalog.json`); if
  you changed it, you must redeploy.

### `403 PERMISSION_DENIED` / "Permission denied on resource project …"

The service (or your local machine) cannot call Vertex AI.

- **Locally**: you need ADC + permission.
  `gcloud auth application-default login`, then make sure your account has
  `roles/aiplatform.user` on the project.
- **On Cloud Run**: grant the runtime service account
  `roles/aiplatform.user` on the project:

```bash
gcloud projects add-iam-policy-binding adk-tut-499512 \
  --member="serviceAccount:<service-account-email>" \
  --role="roles/aiplatform.user"
```

(The deploy uses the default compute/run SA unless you pass
`--service-account`.)

### `KeyError: Context variable not found: expression`

This was the original bug that motivated the redesign. The old
`BasicCatalog` schema text contained a literal `{expression}` that ADK treats
as a session-state template variable. In the new design:

- the custom catalog has **no** `{expression}` text, and
- the executor seeds `expression` in session state anyway (mirroring the
  official sample).

If you see it again after adding a component, search your catalog/examples for
`{word}` braces and either remove them or seed that key in
`agent_executor._prepare_session`.

### A2UI request returns text instead of UI (no DataParts)

Check the two gates:

1. Did the client send `extensions: ["https://a2ui.org/a2a-extension/a2ui/v0.9"]`?
   Without it the executor keeps A2UI off. (In `client.js` this is attached on
   every message; a raw `curl` must include it.)
2. Did the client declare `a2uiClientCapabilities.supportedCatalogIds`
   matching the agent's `supportedCatalogIds`? If the intersection is empty,
   negotiation fails. Fetch both card and catalog to compare IDs.
3. The model may still judge a request as not-UI-worthy (that's the prompt's
   call). Try a phrase like "show me an A2UI demo with a button and text".

### Agent says the tool failed / invalid A2UI

`send_a2ui_json_to_client` validates against the catalog. Errors usually mean
the model used a component/property not in the catalog, or missed a required
field. The model retries once. If it keeps failing:

- Check `app/catalog.json` — is the component/property defined and listed in
  `$defs.anyComponent.oneOf`?
- Check `app/examples/` — examples are validated at startup; a bad example
  fails the build (good early signal).

### I see `<a2ui-json>` tags in the output

That is the *older* "text-delimited" A2UI style from the original
implementation (the model wraps JSON in `<a2ui-json>…</a2ui-json>`). The new
design uses the **tool-based** path (`send_a2ui_json_to_client`), where output
arrives as `DataPart`s with `mimeType: application/json+a2ui`. If you see raw
tags, the toolset is not enabled for the session (Gate 1) — the model fell
back to emitting delimited text in its prompt. Double-check the extension +
capabilities.

### The demo page loads but clicking "A2UI demo" shows nothing

Open the browser dev tools (F12) → Console/Network:

- Confirm `/.well-known/agent-card.json` and `/catalog.json` loaded (200).
- Confirm the POST to `/a2a/a2ui_agent` returns 200 and the JSON contains
  `result.artifacts[].parts[]` with `kind: "data"`.
- If the console shows a JS error (e.g. `crypto.randomUUID` not available),
  use a current browser (randomUUID needs a secure context / modern Chrome,
  Edge, Firefox, Safari).

### Client /catalog.json is 404 in the browser but the file exists locally

Make sure the image contains `client/` and `app/`:

```dockerfile
COPY app/ app/
COPY client/ client/
```

The Dockerfile was updated to copy `client/` — if you reverted it, `/client`
mounts but files 404.

## Code / dependency gotchas (you probably won't hit these, but…)

### `a2a-sdk` version conflict

`a2ui-agent-sdk` pins `a2a-sdk>=0.3,<0.4`. The A2A serving helpers
(`A2AFastAPIApplication`, `DefaultRequestHandler`, the old client) come from
that line. Do NOT bump `a2a-sdk` to 1.x to match other projects (e.g. the
financial planner) — it will break resolution and the imports above.

### `CatalogConfig.from_path` fails on Windows paths

`CatalogConfig.from_path` treats `D:\…` as a URL scheme. `app/agent.py`
deliberately uses `FileSystemCatalogProvider(str(path))` + a plain
`CatalogConfig` instead.

### "The referenced name `#/$defs/...` … does not match a display_name"

This was a Vertex validation error in the old architecture caused by serving a
catalog that still contained `$ref`s to the model. The new architecture does
not feed the catalog back to the model as a tool response — the schema is
rendered into the prompt and validated server-side — so this class of error is
gone. If it reappears, check you are not returning raw schema JSON from a
tool.

## Where to look when something breaks

1. **Cloud Run logs**:
   ```bash
   gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=a2ui-agent-personal' \
     --project adk-tut-499512 --limit 50 --format='value(timestamp,severity,textPayload)'
   ```
2. **Card/catalog sanity**:
   ```bash
   curl https://<service>/.well-known/agent-card.json
   curl https://<service>/catalog.json
   ```
3. **A raw A2UI request** (fastest repro, no browser):
   ```bash
   curl -X POST https://<service>/a2a/a2ui_agent -H 'Content-Type: application/json' \
     -d '{"jsonrpc":"2.0","id":"x","method":"message/send","params":{"message":{"messageId":"m1","role":"user","extensions":["https://a2ui.org/a2a-extension/a2ui/v0.9"],"metadata":{"a2uiClientCapabilities":{"supportedCatalogIds":["https://<service>/catalog.json"]}},"parts":[{"text":"show me an A2UI demo with a button and text"}]}}}'
   ```
4. **Docs to re-read**: [03-flow.md](03-flow.md) (what should happen),
   [04-catalog.md](04-catalog.md) (catalog rules).

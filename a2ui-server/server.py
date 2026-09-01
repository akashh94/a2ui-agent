"""Catalog + chat facade service for a2ui-agent.

This Cloud Run service does two things:

  GET  /etcatalog -- the A2UI catalog as JSON (official v0.9 JSON Schema format),
                     served statically from catalog.json.
  POST /chat      -- SSE stream of the agent's text reply. This endpoint is a
                     thin proxy: the agent itself runs on Vertex AI Agent Engine,
                     so this handler forwards the message to the deployed agent
                     (via the vertexai agent_engines client) and relays the
                     streamed events back to the caller as SSE frames.

Local run: uvicorn server:app --reload
Cloud Run: uses the PORT env var Cloud Run injects; see README.md.
"""

import json
import os
import pathlib

import google.auth
import google.auth.transport.requests
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Canonical /etcatalog URL. Override in deployment (e.g. Cloud Run) so the
# catalog's $id / catalogId point at the real service URL, not localhost.
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8000/etcatalog")


class ChatRequest(BaseModel):
    """Body for POST /chat."""

    message: str
    user_id: str = "local"

CATALOG = json.loads(
    pathlib.Path(__file__).with_name("catalog.json").read_text(encoding="utf-8")
)
CATALOG["$id"] = CATALOG_URL
CATALOG["catalogId"] = CATALOG_URL


def _strip_refs(catalog: dict) -> dict:
    """Remove $refs from the catalog so consumers (the agent's tool response)
    don't hit model-side function-response validation failures.

    Components reference a remote schema (https://a2ui.org/specification/...)
    and the local $defs/CatalogComponentCommon. Gemini rejects any $ref it
    cannot resolve to a display_name. The components' own properties carry the
    real data, and CatalogComponentCommon only adds optional "weight", so the
    refs are inlined/dropped.
    """
    defs = catalog.get("$defs") or {}
    components = catalog.get("components") or {}
    for schema in components.values():
        if not isinstance(schema, dict):
            continue
        # Inline local $defs properties (CatalogComponentCommon -> weight).
        for part in schema.get("allOf") or []:
            if isinstance(part, dict) and part.get("$ref", "").startswith("#/"):
                ref_name = part["$ref"].split("/")[-1]
                schema.setdefault("properties", {}).update(
                    (defs.get(ref_name) or {}).get("properties", {})
                )
        # Drop all $ref parts (external and internal); data is inlined above.
        schema["allOf"] = [
            part
            for part in (schema.get("allOf") or [])
            if not (isinstance(part, dict) and "$ref" in part)
        ]
        if not schema["allOf"]:
            del schema["allOf"]
    catalog.pop("$defs", None)
    return catalog


CATALOG = _strip_refs(CATALOG)

app = FastAPI(title="a2ui-server")

# CORS: allow browser clients from anywhere by default (public demo endpoint).
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOW_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _engine_stream_url() -> str:
    """The :streamQuery REST URL for the configured Agent Engine."""
    project = os.getenv("AGENT_ENGINE_PROJECT", os.getenv("PROJECT_ID", ""))
    location = os.getenv("AGENT_ENGINE_LOCATION", os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"))
    engine_id = os.getenv("AGENT_ENGINE_ID", "")
    if not project or not engine_id:
        raise ValueError("AGENT_ENGINE_PROJECT and AGENT_ENGINE_ID must be set")
    return (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project}/locations/{location}/"
        f"reasoningEngines/{engine_id}:streamQuery"
    )


def _access_token() -> str:
    """An OAuth2 access token from ADC (the Cloud Run service account)."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


@app.get("/etcatalog")
def etcatalog() -> JSONResponse:
    """Return the A2UI catalog as JSON."""
    return JSONResponse(CATALOG)


@app.post("/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    """Proxy the user's message to the Agent Engine agent and stream the reply.

    Calls the engine's :streamQuery REST endpoint (the same pattern as
    akapal-geap-ui/server.js) with the service account's access token. Each
    SSE frame is ``data: <json>``; the reply is streamed as it is generated,
    and the stream ends with ``data: [DONE]``. On error an
    ``data: {"error": ...}`` frame is sent instead.
    """
    user_message = body.message.strip()
    if not user_message:
        return JSONResponse({"error": "missing 'message' in request body"}, status_code=400)

    user_id = body.user_id
    session_id = f"session-{user_id}"

    async def event_stream():
        try:
            url = _engine_stream_url()
            token = _access_token()
            payload = {
                "class_method": "stream_query",
                "input": {
                    "message": user_message,
                    "user_id": user_id,
                    "session_id": session_id,
                    # Without this, ADK's RunConfig defaults to StreamingMode.NONE
                    # and the agent yields one final event per turn. SSE mode is
                    # what actually streams token-level events.
                    "run_config": {"streaming_mode": "sse"},
                },
            }
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        err_body = (await response.aread()).decode(errors="replace")
                        err = f"Agent Engine {response.status_code}: {err_body}"
                        yield f"data: {json.dumps({'error': err})}\n\n"
                        return
                    partial = ""
                    async for chunk in response.aiter_bytes():
                        partial += chunk.decode("utf-8", errors="replace")
                        # Extract complete JSON events from the accumulated buffer.
                        while True:
                            depth = 0
                            start = -1
                            in_string = False
                            escape_next = False
                            found = -1
                            for i, ch in enumerate(partial):
                                if start == -1:
                                    if ch == "{":
                                        start = i
                                        depth = 1
                                    continue
                                if escape_next:
                                    escape_next = False
                                    continue
                                if ch == "\\":
                                    escape_next = True
                                    continue
                                if ch == '"':
                                    in_string = not in_string
                                    continue
                                if in_string:
                                    continue
                                if ch == "{":
                                    depth += 1
                                elif ch == "}":
                                    depth -= 1
                                    if depth == 0:
                                        found = i
                                        break
                            if found == -1:
                                break
                            raw = partial[start : found + 1]
                            partial = partial[found + 1 :]
                            event = json.loads(raw)
                            # The current ADK event format marks the final
                            # answer with "partial": false (there is no
                            # is_final_response key).
                            if event.get("partial") is False:
                                content = event.get("content") or {}
                                parts = content.get("parts") or []
                                text = parts[0].get("text", "") if parts else ""
                                if text:
                                    yield f"data: {json.dumps({'text': text})}\n\n"
        except Exception as exc:  # keep the SSE stream alive and report cleanly
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

"""FastAPI server for a2ui-agent.

Endpoints:
  GET  /etcatalog -- the A2UI catalog as JSON (official v0.9 JSON Schema format)
  POST /chat      -- SSE stream of the agent's text reply

Local run: uvicorn server:app --reload
Cloud Run: uses the PORT env var Cloud Run injects; see README.md.
"""

import json
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from google.adk.agents import RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from agent import CATALOG, agent

app = FastAPI(title="a2ui-agent")

# CORS: allow browser clients from anywhere by default (public demo endpoint).
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOW_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base Runner with auto_create_session=True, the same pattern geap-agent's
# fast_api_app.py uses. Unlike InMemoryRunner, the base Runner honors the
# auto-create flag, so the session is created on first run_async.
runner = Runner(
    agent=agent,
    app_name=agent.name,
    session_service=InMemorySessionService(),
    artifact_service=InMemoryArtifactService(),
    memory_service=InMemoryMemoryService(),
    auto_create_session=True,
)


@app.get("/etcatalog")
def etcatalog() -> JSONResponse:
    """Return the A2UI catalog as JSON."""
    return JSONResponse(CATALOG)


@app.post("/chat")
async def chat(request: Request) -> StreamingResponse:
    """Stream the agent's reply as Server-Sent Events.

    Each SSE frame is ``data: <json>``; text deltas arrive as they are
    generated, and the stream ends with ``data: [DONE]``. On error an
    ``data: {"error": ...}`` frame is sent instead.

    The client may pass a ``user_id`` to get its own conversation; it
    defaults to "local" (one shared in-memory conversation).
    """
    body = await request.json()
    user_message = str(body.get("message", "")).strip()
    if not user_message:
        return JSONResponse({"error": "missing 'message' in request body"}, status_code=400)

    user_id = str(body.get("user_id", "local"))
    session_id = f"session-{user_id}"

    async def event_stream():
        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                if event.is_final_response():
                    text = (
                        event.content.parts[0].text
                        if event.content and event.content.parts
                        else ""
                    )
                    if text:
                        yield f"data: {json.dumps({'text': text})}\n\n"
        except Exception as exc:  # keep the SSE stream alive and report cleanly
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

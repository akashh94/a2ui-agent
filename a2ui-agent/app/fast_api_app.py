"""FastAPI serving app for the a2ui-agent (A2A service on Cloud Run).

Planner-style wiring (mirrors akapal-geap-financial-planner):
- lifespan builds the LlmAgent + Runner (in-memory services) and attaches the
  A2A routes (card + JSON-RPC) via app/app_utils/a2a.py.
- GET /catalog.json serves the custom catalog so clients can register it
  under the catalogId the agent advertises.
- Env: GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION (required by
  get_fast_api_app on Cloud Run), APP_URL (public https URL so the card's
  advertised rpc_url / catalogId are correct), AGENT_MODEL / MODEL_LOCATION.
"""

import contextlib
import logging
import os
import pathlib
from collections.abc import AsyncIterator

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI, Response
from google.adk.artifacts import InMemoryArtifactService
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

load_dotenv()

logger = logging.getLogger(__name__)

try:
    _, project_id = google.auth.default()
except Exception:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "unknown")

if project_id and project_id != "unknown":
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)

allow_origin = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_URL = os.getenv(
    "APP_URL", "https://a2ui-agent-personal-947331501288.us-central1.run.app"
)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import build_agent
    from app.app_utils.a2a import attach_a2a_routes

    agent = build_agent()
    runner = Runner(
        app_name=agent.name,
        agent=agent,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = agent.name

    await attach_a2a_routes(
        app,
        agent=agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{agent.name}",
        app_url=APP_URL,
    )
    logger.info("A2A routes attached for %s at /a2a/%s", agent.name, agent.name)
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    allow_origins=allow_origin,
    auto_create_session=True,
    lifespan=lifespan,
    gemini_enterprise_app_name="app",
)
app.title = "a2ui-agents"
app.description = "A2UI agent — google_search + A2UI catalog generation over A2A"


@app.get("/catalog.json")
def catalog_json() -> Response:
    """Serve the custom catalog so clients register renderers under its
    catalogId (which is this same URL)."""
    catalog_path = pathlib.Path(AGENT_DIR) / "catalog.json"
    return Response(
        content=catalog_path.read_text(encoding="utf-8"),
        media_type="application/json",
    )


# Serve the minimal demo client (fetches card/catalog, sends A2A, renders).
_CLIENT_DIR = pathlib.Path(AGENT_DIR).parent / "client"
if _CLIENT_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/client", StaticFiles(directory=str(_CLIENT_DIR)), name="client")


@app.get("/client")
def client_redirect() -> Response:
    return Response(
        status_code=302,
        headers={"Location": "/client/index.html"},
    )


@app.get("/")
def root() -> dict:
    """Minimal root: point clients at the card + catalog."""
    return {
        "service": app.title,
        "agent_card": f"{APP_URL}/a2a/a2ui_agent/.well-known/agent-card.json",
        "catalog": f"{APP_URL}/catalog.json",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

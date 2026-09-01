"""FastAPI serving app for the a2ui-agent.

Wraps the single ADK agent (app/agent.py) in an HTTP server via
``get_fast_api_app``. ``gemini_enterprise_app_name`` wires the Vertex Agent
Engine remote-agent protocol (what a2ui-server's ``agent_engines.get(...).
async_stream_query`` calls), matching geap-agent's deployment pattern.
"""

import os

from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

# The agents dir ADK scans for agent definitions. This file lives next to
# agent.py, so the directory itself is the single-agent dir (name "app").
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    allow_origins=allow_origins,
    auto_create_session=True,
    gemini_enterprise_app_name="app",
)
app.title = "a2ui-agents"
app.description = "A2UI agent — google_search + get_a2ui_catalog"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

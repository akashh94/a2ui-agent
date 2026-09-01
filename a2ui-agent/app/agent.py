"""The a2ui-agent ADK agent (deployed on Vertex AI Agent Engine).

A minimal LlmAgent with exactly two tools:
  * google_search       -- Google Search via a sub-agent wrapper (GoogleSearchAgentTool)
  * get_a2ui_catalog    -- fetches the A2UI catalog from the a2ui-server
                           (Cloud Run) /etcatalog over HTTP, authenticated with
                           a service-account ID token.

The model only decides WHEN to call get_a2ui_catalog; it never authors
component JSON itself. The catalog data lives in the a2ui-server, not
in this agent, so this service has no catalog.json.

Mirrors geap-agent's pattern (app/tools/google_search_tool.py): search is
wrapped as a GoogleSearchAgentTool sub-agent so it can coexist with custom
function tools on one agent, avoiding Vertex's "multiple tools" restriction
(custom functions + built-in grounding tools can't share one request).

Deployment: this module is the "agent" passed to agent_engines.create(...);
the a2ui-server /chat endpoint proxies to the deployed Agent Engine.
"""

import json
import os
import urllib.request

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from google.adk.tools.google_search_agent_tool import (
    GoogleSearchAgentTool,
    create_google_search_agent,
)

# Base URL of the a2ui-server (Cloud Run). On Agent Engine this must be the
# deployed service URL (set via env var when creating the Agent Engine).
# The catalog tool calls <CATALOG_URL>/etcatalog.
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8000")


def _build_model() -> Gemini:
    """Build the Gemini model over Vertex AI using Application Default
    Credentials (the Agent Engine service account in production, gcloud auth
    application-default login locally). No API key needed."""
    return Gemini(
        model=os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
        client_kwargs={
            "vertexai": True,
            "location": os.getenv("MODEL_LOCATION", "us-central1"),
        },
    )


def get_a2ui_catalog() -> dict:
    """Get the A2UI component catalog (available components and their
    properties). Call this when the user asks about A2UI components, the A2UI
    catalog, building agent-driven UIs, or anything mentioning 'etcatalog'."""
    with urllib.request.urlopen(f"{CATALOG_URL}/etcatalog", timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


catalog_tool = FunctionTool(get_a2ui_catalog)


google_search_tool = GoogleSearchAgentTool(create_google_search_agent(_build_model()))

root_agent = LlmAgent(
    name="a2ui_agent",
    model=_build_model(),
    instruction=(
        "You are a helpful assistant with two tools: google_search for web "
        "lookups, and get_a2ui_catalog for A2UI component information.\n\n"
        "Use google_search for general questions (facts, current time, "
        "weather, news, capital cities, etc.) -- never call get_a2ui_catalog "
        "for those.\n\n"
        "Call get_a2ui_catalog ONLY when the user asks specifically about "
        "A2UI: 'a2ui demo', the A2UI catalog, A2UI components, A2UI "
        "catalogs, building agent-driven UIs, what A2UI can do, or anything "
        "mentioning 'etcatalog'. Never invent component names or properties "
        "from memory -- answer from the catalog data the tool returns."
    ),
    tools=[google_search_tool, catalog_tool],
)

# Backward-compatible alias (the old deploy_agent_engine.py path used "agent").
agent = root_agent

__all__ = ["root_agent", "agent"]

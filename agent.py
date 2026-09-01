"""The a2ui-agent ADK agent.

A minimal LlmAgent with exactly two tools:
  * google_search  -- built-in ADK web search
  * get_a2ui_catalog -- returns the A2UI catalog as JSON

The model only decides WHEN to call get_a2ui_catalog; it never authors
component JSON itself.

The agent and the server are one project (one Cloud Run service). The catalog
lives in catalog.json, is served by the server at /etcatalog, and is read
directly from memory here -- no HTTP round-trip needed.
"""

import json
import os
import pathlib

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import google_search

CATALOG = json.loads(
    pathlib.Path(__file__).with_name("catalog.json").read_text(encoding="utf-8")
)


def _build_model() -> Gemini:
    """Build the Gemini model over Vertex AI using Application Default
    Credentials (service account on Cloud Run, gcloud auth application-default
    login locally). No API key needed. Mirrors geap-agent's app/config/models.py."""
    return Gemini(
        model=os.getenv("AGENT_MODEL", "gemini-2.0-flash"),
        client_kwargs={
            "vertexai": True,
            "location": os.getenv("MODEL_LOCATION", "global"),
        },
    )


def get_a2ui_catalog() -> str:
    """Return the A2UI component catalog as JSON.

    Use this when the user asks about A2UI components, catalogs, or how to
    build an agent-driven UI. Answer using this catalog data rather than
    from memory.
    """
    return json.dumps(CATALOG, indent=2)


agent = LlmAgent(
    name="a2ui_agent",
    model=_build_model(),
    instruction=(
        "You are a helpful assistant with two tools: google_search for web "
        "lookups, and get_a2ui_catalog for A2UI component information. "
        "When the user asks anything about A2UI (components, catalogs, or "
        "building agent-driven UIs) or mentions 'etcatalog', call "
        "get_a2ui_catalog first and answer from the catalog data it returns "
        "-- never invent component names or properties from memory. Use "
        "google_search for general web questions."
    ),
    tools=[google_search, get_a2ui_catalog],
)

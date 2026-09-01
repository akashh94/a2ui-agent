"""The a2ui-agent ADK agent (deployed on Vertex AI Agent Engine).

An LlmAgent with three capabilities:
  * google_search       -- Google Search via a sub-agent wrapper (GoogleSearchAgentTool)
  * get_a2ui_catalog    -- fetches the A2UI catalog from the a2ui-server
                           (Cloud Run) /etcatalog over HTTP.
  * A2UI message output -- for A2UI-related requests, the model generates A2UI
                           messages (render/update) per the A2UI v0.9 schema,
                           driven by a2ui-agent-sdk's DirectJsonFormat.

The model decides WHEN to call get_a2ui_catalog or google_search; for A2UI
UI-generation requests it emits A2UI JSON instead of plain text.

Deployment: the a2ui-server /chat endpoint proxies to this agent on Agent Engine.
"""

import json
import os
import urllib.request

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.inference_formats.direct_json import DirectJsonFormat
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.constants import VERSION_0_9
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

ROLE_DESCRIPTION = (
    "You are a helpful assistant that answers questions and, when asked about "
    "A2UI, generates A2UI messages. Your final output for A2UI requests MUST "
    "be valid A2UI v0.9 JSON (a list of A2UI messages)."
)

UI_DESCRIPTION = """
- Use the catalog data returned by get_a2ui_catalog when you need component
  details.
- For questions about A2UI components or building agent-driven UIs, generate
  an A2UI render/update message list using the schema and examples below.
- For general questions (facts, time, weather, news), use google_search and
  reply in plain text -- do NOT generate A2UI messages.
"""


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


# A2UI system prompt: schema + examples from the SDK's built-in catalog,
# following the official restaurant_finder sample (DirectJsonFormat +
# remove_strict_validation, which drops additionalProperties:false so the
# model can include extra fields in generated components).
schema_manager = DirectJsonFormat(
    version=VERSION_0_9,
    catalogs=[
        BasicCatalog.get_config(version=VERSION_0_9),
    ],
    schema_modifiers=[remove_strict_validation],
)
A2UI_INSTRUCTION = schema_manager.generate_system_prompt(
    role_description=ROLE_DESCRIPTION,
    ui_description=UI_DESCRIPTION,
    include_schema=True,
    include_examples=True,
    validate_examples=True,
)

# ADK treats "{expression}" in the instruction as a session-state template
# variable and raises if the session has no "expression" state. The SDK's
# catalog schema mentions it only in a docstring example, so drop the literal
# braces to keep ADK from interpolating it.
A2UI_INSTRUCTION = A2UI_INSTRUCTION.replace("{expression}", "expression")

root_agent = LlmAgent(
    name="a2ui_agent",
    model=_build_model(),
    instruction=(
        A2UI_INSTRUCTION + "\n\n"
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

__all__ = ["agent", "root_agent"]

"""The a2ui-agent ADK agent (A2A service on Cloud Run).

An LlmAgent with:
  * google_search    -- general questions via a Google Search sub-agent
                        (GoogleSearchAgentTool), used when A2UI is not active
                        (the client did not request the A2UI extension).
  * send_a2ui_json_to_client -- provided by SendA2uiToClientToolset, enabled
                        only when the A2UI extension is active. The model
                        calls it with the A2UI v0.9 message list it built
                        against the catalog in app/catalog.json.

The catalog (app/catalog.json) is the single source of truth: its schema is
injected into the LLM request per-turn by the toolset (from session state,
which the executor populates after catalog negotiation), and it is served to
clients at /catalog.json for them to register renderers under the catalogId.

Deployment: Cloud Run (planner-style), served over A2A by fast_api_app.py.
"""

from __future__ import annotations

import os
import pathlib

from a2ui.inference_formats.direct_json import DirectJsonFormat
from a2ui.schema.catalog import CatalogConfig
from a2ui.schema.catalog_provider import FileSystemCatalogProvider
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.constants import VERSION_0_9
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.google_llm import Gemini
from google.adk.tools.google_search_agent_tool import (
    GoogleSearchAgentTool,
    create_google_search_agent,
)

_APP_DIR = pathlib.Path(__file__).resolve().parent

# Public catalogId — the same URL /catalog.json is served at. Kept in sync
# with app/catalog.json via CATALOG_URI (APP_URL + "/catalog.json").
CATALOG_URI = (
    os.getenv("APP_URL", "https://a2ui-agent-personal-947331501288.us-central1.run.app")
    + "/catalog.json"
)

ROLE_DESCRIPTION = (
    "You are a helpful assistant. When the user asks you to show UI, a demo, "
    "or an interface, you build an A2UI interface by calling the "
    "send_a2ui_json_to_client tool with a valid A2UI v0.9 JSON message list. "
    "For anything else (facts, questions, chat), answer in plain text using "
    "google_search when needed."
)

UI_DESCRIPTION = """
- Build surfaces with the components defined in the catalog provided to you
  (createSurface -> updateComponents). Use ONLY component names and
  properties from that catalog. Never invent components.
- Always start with a createSurface message carrying the catalogId, then one
  or more updateComponents messages defining the component tree (root first,
  parents before children).
- Do not send conversational text; the A2UI payload IS your answer.
"""

WORKFLOW_DESCRIPTION = """
1. Determine intent: UI request (build an A2UI interface) vs a normal chat /
   fact question.
2. If a normal question, answer in plain text (google_search for facts).
3. If a UI request, call send_a2ui_json_to_client with the full A2UI message
   list as the a2ui_json argument, using the schema and examples injected
   into the request. If the tool reports an error, fix the payload and call
   it again.
"""


def _build_model() -> Gemini:
    """Build the Gemini model over Vertex AI using ADC (Cloud Run SA in
    production, gcloud auth application-default login locally)."""
    return Gemini(
        model=os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
        client_kwargs={
            "vertexai": True,
            "location": os.getenv("MODEL_LOCATION", "us-central1"),
        },
    )


def build_inference_format() -> DirectJsonFormat:
    """The DirectJsonFormat over the custom catalog (app/catalog.json).

    Uses FileSystemCatalogProvider directly (CatalogConfig.from_path mangles
    Windows drive paths via os.path.abspath on the file URI).
    """
    return DirectJsonFormat(
        version=VERSION_0_9,
        catalogs=[
            CatalogConfig(
                name="a2ui-demo",
                provider=FileSystemCatalogProvider(str(_APP_DIR / "catalog.json")),
                examples_path=str(_APP_DIR / "examples"),
            ),
        ],
        schema_modifiers=[remove_strict_validation],
        accepts_inline_catalogs=True,
    )


inference_format = build_inference_format()

# Session-state keys (populated by the executor after catalog negotiation;
# read by the SendA2uiToClientToolset providers below). Kept in sync with
# app/agent_executor.py.
A2UI_ENABLED_KEY = "system:a2ui_enabled"
A2UI_CATALOG_KEY = "system:a2ui_catalog"
A2UI_EXAMPLES_KEY = "system:a2ui_examples"


def a2ui_enabled_provider(ctx: ReadonlyContext) -> bool:
    """True when the A2UI extension was negotiated for this session."""
    return bool(ctx.state.get(A2UI_ENABLED_KEY, False))


def a2ui_catalog_provider(ctx: ReadonlyContext):
    """The negotiated A2uiCatalog stored in session state."""
    return ctx.state.get(A2UI_CATALOG_KEY)


def a2ui_examples_provider(ctx: ReadonlyContext):
    """The validated examples string stored in session state."""
    return ctx.state.get(A2UI_EXAMPLES_KEY)


def _google_search_tool() -> GoogleSearchAgentTool:
    return GoogleSearchAgentTool(create_google_search_agent(_build_model()))


def build_agent() -> LlmAgent:
    """Build the agent. The SendA2uiToClientToolset is always present but
    resolves to zero tools when A2UI is not enabled for the session; the
    schema/examples it injects come from session state (see providers)."""
    from a2ui.adk.send_a2ui_to_client_toolset import SendA2uiToClientToolset
    from google.adk.agents.llm_agent import ToolUnion

    tools: list[ToolUnion] = [
        _google_search_tool(),
        SendA2uiToClientToolset(
            a2ui_enabled=a2ui_enabled_provider,
            a2ui_catalog=a2ui_catalog_provider,
            a2ui_examples=a2ui_examples_provider,
        ),
    ]

    return LlmAgent(
        name="a2ui_agent",
        model=_build_model(),
        instruction=(
            ROLE_DESCRIPTION
            + "\n\n## Workflow Description:\n"
            + WORKFLOW_DESCRIPTION
            + "\n\n## UI Description:\n"
            + UI_DESCRIPTION
        ),
        tools=tools,
        disallow_transfer_to_peers=True,
    )


# Backward-compatible aliases.
agent = build_agent()
root_agent = agent

__all__ = [
    "A2UI_CATALOG_KEY",
    "A2UI_ENABLED_KEY",
    "A2UI_EXAMPLES_KEY",
    "CATALOG_URI",
    "a2ui_catalog_provider",
    "a2ui_enabled_provider",
    "a2ui_examples_provider",
    "agent",
    "build_agent",
    "build_inference_format",
    "inference_format",
    "root_agent",
]

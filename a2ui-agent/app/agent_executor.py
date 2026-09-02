"""A2A executor for the a2ui-agent: negotiates the A2UI extension + catalog
and stores them in session state, so the SendA2uiToClientToolset can inject
the schema/examples and the A2uiEventConverter can turn tool responses into
A2A DataParts.

Modeled on the official rizzcharts sample executor
(samples/community/agent/adk/rizzcharts/python/agent_executor.py):
- A2aAgentExecutor subclass (keeps the ADK A2A machinery: request conversion,
  task events, streaming).
- _prepare_session() runs try_activate_a2ui_extension() and, when active,
  resolves the catalog via inference_format.get_selected_catalog(client
  capabilities) and writes system:a2ui_* keys into session state.
- The A2uiEventConverter (registered via config) converts the agent's
  send_a2ui_json_to_client tool responses into A2A DataPart messages with
  mime application/json+a2ui.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from a2a.server.agent_execution import RequestContext
from a2a.types import AgentCard
from a2ui.a2a.extension import try_activate_a2ui_extension
from a2ui.adk.a2a.event_converter import A2uiEventConverter
from a2ui.inference_formats.direct_json import DirectJsonFormat
from a2ui.schema.constants import A2UI_CLIENT_CAPABILITIES_KEY
from google.adk.a2a.converters.request_converter import AgentRunRequest
from google.adk.a2a.executor.a2a_agent_executor import (
    A2aAgentExecutor,
    A2aAgentExecutorConfig,
)
from google.adk.agents.invocation_context import new_invocation_context_id
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.runners import Runner

if TYPE_CHECKING:
    from google.adk.agents import BaseAgent

from app.agent import (
    A2UI_CATALOG_KEY,
    A2UI_ENABLED_KEY,
    A2UI_EXAMPLES_KEY,
)

logger = logging.getLogger(__name__)


class A2uiAgentExecutor(A2aAgentExecutor):
    """Executor that activates A2UI for the session and stores the negotiated
    catalog + examples in session state (read by the toolset + converter)."""

    def __init__(
        self,
        *,
        agent: BaseAgent,
        runner: Runner,
        inference_format: DirectJsonFormat,
        app_url: str,
        agent_card: AgentCard,
    ):
        self._agent = agent
        self._agent_card = agent_card
        self._app_url = app_url
        # A2uiEventConverter reads the catalog from session state
        # (system:a2ui_catalog) so tool-based A2UI output is converted to
        # A2A DataParts. When no catalog is in state (no A2UI), it falls back
        # to the default part converter (text passthrough).
        config = A2aAgentExecutorConfig(event_converter=A2uiEventConverter())
        super().__init__(runner=runner, config=config)
        self._inference_format = inference_format

    async def _prepare_session(
        self,
        context: RequestContext,
        run_request: AgentRunRequest,
        runner: Runner,
    ):
        logger.info("Loading session for message %s", context.message)
        active_ui_version = try_activate_a2ui_extension(context, self._agent_card)
        logger.info("A2UI active version: %s", active_ui_version)

        session = await super()._prepare_session(context, run_request, runner)

        # Seed the expression state the SDK schema uses (official pattern:
        # session_state = {"expression": "{expression}"}).
        if "expression" not in session.state:
            session.state["expression"] = "{expression}"
        if "base_url" not in session.state:
            session.state["base_url"] = self._app_url

        if active_ui_version:
            capabilities = (
                context.message.metadata.get(A2UI_CLIENT_CAPABILITIES_KEY)
                if context.message and context.message.metadata
                else None
            )
            a2ui_catalog = self._inference_format.get_selected_catalog(
                client_ui_capabilities=capabilities
            )
            examples = self._inference_format.load_examples(a2ui_catalog, validate=True)

            # Store into session state via an event (same as rizzcharts), so
            # the SendA2uiToClientToolset providers and A2uiEventConverter see
            # it per-session.
            await runner.session_service.append_event(
                session,
                Event(
                    invocation_id=new_invocation_context_id(),
                    author="system",
                    actions=EventActions(
                        state_delta={
                            A2UI_ENABLED_KEY: True,
                            A2UI_CATALOG_KEY: a2ui_catalog,
                            A2UI_EXAMPLES_KEY: examples,
                        }
                    ),
                ),
            )

        return session


__all__ = ["A2uiAgentExecutor"]

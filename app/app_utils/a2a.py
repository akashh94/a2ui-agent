"""Attach A2A (Agent2Agent) endpoints to the a2ui-agent FastAPI app.

Uses the A2A serving stack that a2ui-agent-sdk is built against
(a2a-sdk <0.4): ``A2AFastAPIApplication.add_routes_to_app`` mounts the
agent-card + JSON-RPC endpoints. The card's capabilities include the A2UI
extension advertising supportedCatalogIds, per the official A2UI
agent-development flow.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import AgentCapabilities, AgentExtension
from a2ui.a2a.extension import get_a2ui_agent_extension
from a2ui.schema.constants import VERSION_0_9
from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder

if TYPE_CHECKING:
    from a2a.server.tasks.task_store import TaskStore
    from fastapi import FastAPI
    from google.adk.agents import BaseAgent
    from google.adk.runners import Runner

from app.agent import build_inference_format
from app.agent_executor import A2uiAgentExecutor

# URI advertised on the agent card describing the ADK executor extension.
_ADK_AGENT_EXECUTOR_EXTENSION_URI = (
    "https://google.github.io/adk-docs/a2a/a2a-extension/"
)


def _default_capabilities() -> AgentCapabilities:
    """The agent's advertised A2A capabilities: ADK executor extension plus
    the A2UI extension (which announces supportedCatalogIds)."""
    inference_format = build_inference_format()
    extensions: list[AgentExtension] = [
        AgentExtension(
            uri=_ADK_AGENT_EXECUTOR_EXTENSION_URI,
            description="Ability to use the new agent executor implementation",
        ),
        get_a2ui_agent_extension(
            version=VERSION_0_9,
            accepts_inline_catalogs=inference_format.accepts_inline_catalogs,
            supported_catalog_ids=inference_format.supported_catalog_ids,
        ),
    ]
    return AgentCapabilities(streaming=True, extensions=extensions)


async def attach_a2a_routes(
    app: FastAPI,
    *,
    agent: BaseAgent,
    runner: Runner,
    task_store: TaskStore,
    rpc_path: str,
    capabilities: AgentCapabilities | None = None,
    agent_version: str | None = None,
    app_url: str | None = None,
) -> None:
    """Register A2A routes (JSON-RPC + agent-card) under ``rpc_path``."""
    resolved_app_url = app_url or os.getenv("APP_URL", "http://0.0.0.0:8000")
    resolved_agent_version = agent_version or os.getenv("AGENT_VERSION", "0.1.0")
    resolved_capabilities = capabilities or _default_capabilities()

    agent_card = await AgentCardBuilder(
        agent=agent,
        capabilities=resolved_capabilities,
        rpc_url=f"{resolved_app_url}{rpc_path}",
        agent_version=resolved_agent_version,
    ).build()

    executor = A2uiAgentExecutor(
        agent=agent,
        runner=runner,
        inference_format=build_inference_format(),
        app_url=resolved_app_url,
        agent_card=agent_card,
    )

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )

    A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    ).add_routes_to_app(
        app,
        rpc_url=rpc_path,
    )


__all__ = ["attach_a2a_routes"]

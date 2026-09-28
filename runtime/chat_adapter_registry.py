"""Resolve project Chat Agent contracts to provider adapters."""

from __future__ import annotations

from typing import Any

from core.chat_agent_registry import ChatAgentRegistry
from core.contracts.chat_agent import ChatAgentProvider


class ChatAdapterRegistry:
    def __init__(self) -> None:
        self._factories: dict[ChatAgentProvider, Any] = {}

    def register(self, provider: ChatAgentProvider, factory: Any) -> None:
        self._factories[provider] = factory

    def create(self, provider: ChatAgentProvider, *, model: str | None = None) -> Any:
        try:
            factory = self._factories[provider]
        except KeyError as exc:
            raise LookupError(f"no Chat Agent adapter registered for {provider.value}") from exc
        return factory(model=model)


def default_chat_adapters() -> ChatAdapterRegistry:
    registry = ChatAdapterRegistry()

    def openai_factory(*, model=None):
        from integrations.openai.chat_agent import OpenAIChatAgentAdapter
        return OpenAIChatAgentAdapter(model=model)

    registry.register(ChatAgentProvider.CHATGPT, openai_factory)
    return registry


def resolve_project_chat_adapter(
    project_agent,
    model: str | None = None,
    registry: ChatAdapterRegistry | None = None,
):
    adapters = registry or default_chat_adapters()
    return adapters.create(project_agent.provider, model=model)

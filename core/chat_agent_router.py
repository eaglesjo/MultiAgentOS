"""Routing policy for provider-neutral Chat Agents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.chat_agent_registry import ChatAgentRegistry
from core.contracts.chat_agent import ChatAgentContract


class ChatAgentRoutingStrategy(str, Enum):
    EXPLICIT = "explicit"
    FALLBACK = "fallback"
    AUTO = "auto"


@dataclass(frozen=True)
class ChatAgentAssignment:
    agent: ChatAgentContract
    strategy: ChatAgentRoutingStrategy
    candidates: tuple[str, ...]


class ChatAgentRouter:
    """Select a Chat Agent without giving any provider execution authority."""

    def __init__(self, registry: ChatAgentRegistry) -> None:
        self.registry = registry

    def route(
        self,
        *,
        preferred_agent_id: str | None = None,
        fallback_agent_ids: tuple[str, ...] = (),
        required_capabilities: frozenset[str] = frozenset(),
        strategy: ChatAgentRoutingStrategy | str = ChatAgentRoutingStrategy.AUTO,
    ) -> ChatAgentAssignment:
        strategy = ChatAgentRoutingStrategy(strategy)
        candidates: list[ChatAgentContract] = []

        if preferred_agent_id is not None:
            candidates.append(self.registry.get(preferred_agent_id))

        for agent_id in fallback_agent_ids:
            agent = self.registry.get(agent_id)
            if agent.id not in {item.id for item in candidates}:
                candidates.append(agent)

        if strategy is ChatAgentRoutingStrategy.AUTO and not candidates:
            candidates.extend(self.registry.list())

        if strategy is ChatAgentRoutingStrategy.EXPLICIT:
            if preferred_agent_id is None:
                raise ValueError("explicit chat-agent routing requires preferred_agent_id")
            candidates = [self.registry.get(preferred_agent_id)]

        if strategy is ChatAgentRoutingStrategy.FALLBACK and not candidates:
            raise ValueError("fallback chat-agent routing requires candidates")

        compatible = [
            agent for agent in candidates
            if required_capabilities.issubset(agent.capabilities)
        ]
        if not compatible:
            raise LookupError(
                "no chat agent satisfies required capabilities: "
                + ", ".join(sorted(required_capabilities))
            )

        # AUTO prefers the registered primary ChatGPT agent when it is compatible.
        if strategy is ChatAgentRoutingStrategy.AUTO:
            primary = self.registry.primary()
            if primary in compatible:
                selected = primary
            else:
                selected = compatible[0]
        else:
            selected = compatible[0]

        return ChatAgentAssignment(
            agent=selected,
            strategy=strategy,
            candidates=tuple(agent.id for agent in compatible),
        )

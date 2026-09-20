"""Registry for chat-facing AI agents."""

from __future__ import annotations

from core.contracts.chat_agent import ChatAgentContract, ChatAgentProvider


class ChatAgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, ChatAgentContract] = {}

    def register(self, agent: ChatAgentContract) -> None:
        agent.validate()
        if agent.id in self._agents:
            raise ValueError(f"chat agent already registered: {agent.id}")
        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> ChatAgentContract:
        return self._agents[agent_id]

    def primary(self) -> ChatAgentContract:
        for agent in self._agents.values():
            if agent.primary:
                return agent
        raise LookupError("no primary chat agent registered")

    def list(self) -> tuple[ChatAgentContract, ...]:
        return tuple(sorted(self._agents.values(), key=lambda agent: agent.id))


def default_chat_agents() -> ChatAgentRegistry:
    registry = ChatAgentRegistry()
    registry.register(
        ChatAgentContract(
            id="chatgpt",
            provider=ChatAgentProvider.CHATGPT,
            name="ChatGPT Agent",
            capabilities=frozenset({"conversation", "planning", "orchestration"}),
            instruction_profile="vyrelon",
            primary=True,
        )
    )
    registry.register(
        ChatAgentContract(
            id="gemini",
            provider=ChatAgentProvider.GEMINI,
            name="Gemini Agent",
            capabilities=frozenset({"conversation", "planning"}),
            instruction_profile="vyrelon",
        )
    )
    registry.register(
        ChatAgentContract(
            id="claude",
            provider=ChatAgentProvider.CLAUDE,
            name="Claude Agent",
            capabilities=frozenset({"conversation", "planning"}),
            instruction_profile="vyrelon",
        )
    )
    return registry

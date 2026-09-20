"""Registries for agents and AI providers."""

from core.contracts.agent import AgentContract
from core.contracts.ai import AIProvider, ModelSpec


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentContract] = {}

    def register(self, agent: AgentContract) -> None:
        if agent.id in self._agents:
            raise ValueError(f"Agent already registered: {agent.id}")
        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> AgentContract:
        return self._agents[agent_id]

    def list(self) -> tuple[AgentContract, ...]:
        return tuple(self._agents.values())


class AIRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}
        self._models: dict[str, ModelSpec] = {}

    def register(self, provider: AIProvider) -> None:
        if provider.id in self._providers:
            raise ValueError(f"Provider already registered: {provider.id}")
        self._providers[provider.id] = provider
        for model in provider.models:
            if model.id in self._models:
                raise ValueError(f"Model already registered: {model.id}")
            self._models[model.id] = model

    def provider(self, provider_id: str) -> AIProvider:
        return self._providers[provider_id]

    def model(self, model_id: str) -> ModelSpec:
        return self._models[model_id]

    def models(self) -> tuple[ModelSpec, ...]:
        return tuple(self._models.values())

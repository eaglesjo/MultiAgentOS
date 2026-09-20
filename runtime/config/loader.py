"""JSON configuration loader for AI providers and agents."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.ai import AIProvider, ModelSpec
from core.registry import AIRegistry, AgentRegistry
from core.routing import RoutingStrategy


class RuntimeConfig:
    def __init__(
        self,
        agents: AgentRegistry,
        ai: AIRegistry,
        routing: dict[str, RoutingStrategy],
    ) -> None:
        self.agents = agents
        self.ai = ai
        self.routing = routing


class ConfigLoader:
    def load(self, path: Path) -> RuntimeConfig:
        data = json.loads(path.read_text(encoding="utf-8"))
        ai_registry = AIRegistry()
        for provider_data in data.get("ai", {}).get("providers", []):
            models = tuple(
                ModelSpec(
                    id=model["id"],
                    provider_id=provider_data["id"],
                    capabilities=frozenset(model.get("capabilities", [])),
                    metadata=dict(model.get("metadata", {})),
                )
                for model in provider_data.get("models", [])
            )
            ai_registry.register(
                AIProvider(
                    id=provider_data["id"],
                    kind=provider_data.get("type", "generic"),
                    models=models,
                    metadata=dict(provider_data.get("metadata", {})),
                )
            )

        agent_registry = AgentRegistry()
        routing = {}
        for agent_data in data.get("agents", []):
            agent = AgentContract(
                id=agent_data["id"],
                role=agent_data.get("role", agent_data["id"]),
                capabilities=frozenset(agent_data.get("capabilities", [])),
                tools=frozenset(agent_data.get("tools", [])),
                permissions=frozenset(agent_data.get("permissions", [])),
                model_ids=tuple(agent_data.get("models", [])),
                metadata=dict(agent_data.get("metadata", {})),
                kind=agent_data.get("type", "custom"),
            )
            agent_registry.register(agent)
            routing[agent.id] = RoutingStrategy(
                agent_data.get("strategy", RoutingStrategy.POOL.value)
            )

        return RuntimeConfig(agent_registry, ai_registry, routing)

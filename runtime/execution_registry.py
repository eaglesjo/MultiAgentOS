"""Built-in execution contracts used by the VYRELON CLI."""

from __future__ import annotations

from core.contracts import AgentContract, AIProvider, ModelSpec
from core.registry import AgentRegistry, AIRegistry


def default_execution_registries() -> tuple[AgentRegistry, AIRegistry]:
    agents = AgentRegistry()
    agents.register(
        AgentContract(
            id="cli-executor",
            role="executor",
            capabilities=frozenset({"process"}),
            tools=frozenset({"process"}),
            kind="runtime",
        )
    )

    models = AIRegistry()
    models.register(
        AIProvider(
            id="local",
            kind="runtime",
            models=(
                ModelSpec(
                    id="local-process",
                    provider_id="local",
                    capabilities=frozenset({"process"}),
                    metadata={"runtime": "process"},
                ),
            ),
        )
    )
    return agents, models


def resolve_execution_contracts(
    agent_id: str,
    model_id: str,
) -> tuple[AgentContract, ModelSpec]:
    agents, models = default_execution_registries()
    agent = agents.get(agent_id)
    model = models.model(model_id)
    if not agent.capabilities.issubset(model.capabilities):
        raise ValueError(
            f"execution model {model.id!r} is incompatible with agent {agent.id!r}"
        )
    return agent, model

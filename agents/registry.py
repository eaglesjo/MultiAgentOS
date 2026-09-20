"""Agent catalog registration utilities."""

from core.registry import AgentRegistry
from agents.catalog import build_agent_catalog


def build_registry(profile_ids: tuple[str, ...] = ()) -> AgentRegistry:
    registry = AgentRegistry()
    for agent in build_agent_catalog(profile_ids):
        registry.register(agent)
    return registry

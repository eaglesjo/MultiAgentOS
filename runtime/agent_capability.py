"""First-class Agent capability registry."""

from __future__ import annotations

from core.contracts.agent import AgentContract
from core.contracts.agent_capability import AgentCapabilityMatch, AgentCapabilityProfile
from core.registry import AgentRegistry


class AgentCapabilityRegistry:
    """Index Agent contracts for capability-aware selection."""

    def __init__(self, agents: AgentRegistry | None = None) -> None:
        self._profiles: dict[str, AgentCapabilityProfile] = {}
        if agents is not None:
            self.register_all(agents.list())

    def register(self, agent: AgentContract) -> AgentCapabilityProfile:
        profile = AgentCapabilityProfile.from_agent(agent)
        if profile.agent_id in self._profiles:
            raise ValueError(f"Agent capability profile already registered: {profile.agent_id}")
        self._profiles[profile.agent_id] = profile
        return profile

    def register_all(self, agents: tuple[AgentContract, ...] | list[AgentContract]) -> None:
        for agent in agents:
            self.register(agent)

    def profile(self, agent_id: str) -> AgentCapabilityProfile:
        try:
            return self._profiles[agent_id]
        except KeyError as exc:
            raise LookupError(f"Agent capability profile not registered: {agent_id}") from exc

    def list(self) -> tuple[AgentCapabilityProfile, ...]:
        return tuple(self._profiles.values())

    def match(self, agent_id: str, *, capabilities=frozenset(), tools=frozenset(), permissions=frozenset()) -> AgentCapabilityMatch:
        profile = self.profile(agent_id)
        return AgentCapabilityMatch(
            agent_id=agent_id,
            required_capabilities=capabilities,
            required_tools=tools,
            required_permissions=permissions,
            matched_capabilities=profile.capabilities & capabilities,
            missing_capabilities=capabilities - profile.capabilities,
            matched_tools=profile.tools & tools,
            missing_tools=tools - profile.tools,
            matched_permissions=profile.permissions & permissions,
            missing_permissions=permissions - profile.permissions,
            score=profile.match_score(capabilities=capabilities, tools=tools, permissions=permissions),
        )

    def matches(self, *, capabilities=frozenset(), tools=frozenset(), permissions=frozenset()) -> tuple[AgentCapabilityMatch, ...]:
        return tuple(self.match(p.agent_id, capabilities=capabilities, tools=tools, permissions=permissions) for p in self._profiles.values())

    def compatible(self, *, capabilities=frozenset(), tools=frozenset(), permissions=frozenset()) -> tuple[AgentCapabilityProfile, ...]:
        return tuple(self.profile(m.agent_id) for m in self.matches(capabilities=capabilities, tools=tools, permissions=permissions) if m.compatible)

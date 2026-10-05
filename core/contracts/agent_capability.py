"""Agent capability matching contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.contracts.agent import AgentContract


@dataclass(frozen=True)
class AgentCapabilityProfile:
    """Normalized, vendor-neutral capabilities exposed by one Agent."""

    agent_id: str
    kind: str
    capabilities: frozenset[str] = frozenset()
    tools: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    model_ids: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_agent(cls, agent: AgentContract) -> "AgentCapabilityProfile":
        agent.validate()
        return cls(agent.id, agent.kind, agent.capabilities, agent.tools, agent.permissions, agent.model_ids, dict(agent.metadata))

    def supports(self, *, capabilities=frozenset(), tools=frozenset(), permissions=frozenset()) -> bool:
        return capabilities.issubset(self.capabilities) and tools.issubset(self.tools) and permissions.issubset(self.permissions)

    def match_score(self, *, capabilities=frozenset(), tools=frozenset(), permissions=frozenset()) -> float:
        groups = ((capabilities, self.capabilities), (tools, self.tools), (permissions, self.permissions))
        required = sum(len(items) for items, _ in groups)
        if not required:
            return 1.0
        matched = sum(len(items & available) for items, available in groups)
        return matched / required


@dataclass(frozen=True)
class AgentCapabilityMatch:
    """Explain how one Agent satisfies a capability requirement."""

    agent_id: str
    required_capabilities: frozenset[str]
    required_tools: frozenset[str]
    required_permissions: frozenset[str]
    matched_capabilities: frozenset[str]
    missing_capabilities: frozenset[str]
    matched_tools: frozenset[str]
    missing_tools: frozenset[str]
    matched_permissions: frozenset[str]
    missing_permissions: frozenset[str]
    score: float

    @property
    def compatible(self) -> bool:
        return not (self.missing_capabilities or self.missing_tools or self.missing_permissions)

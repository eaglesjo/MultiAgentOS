"""Technology, project, and agent profile contracts for VYRELON."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProfileSpec:
    id: str
    display_name: str
    detect_files: frozenset[str] = frozenset()
    detect_markers: frozenset[str] = frozenset()
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class DetectionResult:
    profile_id: str
    confidence: float
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class AgentProfile:
    """Stable agent identity derived from a project technology profile."""

    id: str
    role: str
    profile_ids: tuple[str, ...] = ()
    capabilities: frozenset[str] = frozenset()
    tools: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    model_ids: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    def to_contract(self):
        from core.contracts.agent import AgentContract

        return AgentContract(
            id=self.id,
            role=self.role,
            capabilities=self.capabilities,
            tools=self.tools,
            permissions=self.permissions,
            model_ids=self.model_ids,
            metadata={
                **self.metadata,
                "profiles": list(self.profile_ids),
                "agent_profile_id": self.id,
            },
            kind="profile",
        )


@dataclass(frozen=True)
class ProjectProfile:
    """Resolved project identity shared by VYRELON integrations."""

    id: str
    root: str
    technology_profile_ids: tuple[str, ...] = ()
    agent_profile_ids: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def primary_technology_profile(self) -> str | None:
        return self.technology_profile_ids[0] if self.technology_profile_ids else None

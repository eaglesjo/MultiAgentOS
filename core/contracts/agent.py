"""Agent contract independent of any model or vendor."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class AgentTaxonomy:
    """Orthogonal specialist taxonomy used by routing and catalog discovery."""

    layer: str = "specialist"
    domain: str = ""
    platform: str = ""
    technology: str = ""
    specialization: str = ""
    parent_id: str | None = None

    def validate(self) -> None:
        allowed_layers = {"governance", "specialist"}
        if self.layer not in allowed_layers:
            raise ValueError(f"unsupported agent taxonomy layer: {self.layer}")
        if self.parent_id == "":
            raise ValueError("agent taxonomy parent_id must be null or non-empty")
        if self.layer == "governance" and self.domain:
            raise ValueError("governance agents cannot declare a specialist domain")


@dataclass(frozen=True)
class AgentContract:
    id: str
    role: str
    capabilities: frozenset[str] = frozenset()
    tools: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    model_ids: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
    kind: str = "custom"
    scope_aware: bool = True
    taxonomy: AgentTaxonomy = field(default_factory=AgentTaxonomy)

    def validate(self) -> None:
        self.taxonomy.validate()
        if self.kind == "governance" and self.taxonomy.layer != "governance":
            raise ValueError(
                "governance agents must use the governance taxonomy layer"
            )
        if self.kind == "specialist" and self.taxonomy.layer != "specialist":
            raise ValueError(
                "specialist agents must use the specialist taxonomy layer"
            )


class AgentRuntime(Protocol):
    def execute(self, agent: AgentContract, work_unit: object) -> object:
        ...

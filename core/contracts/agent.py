"""Agent contract independent of any model or vendor."""

from dataclasses import dataclass, field
from typing import Protocol


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


class AgentRuntime(Protocol):
    def execute(self, agent: AgentContract, work_unit: object) -> object:
        ...

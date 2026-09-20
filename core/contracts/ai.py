"""AI provider/model contracts used by VYRELON routing."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider_id: str
    capabilities: frozenset[str] = frozenset()
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AIProvider:
    id: str
    kind: str
    models: tuple[ModelSpec, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


class AIExecutor(Protocol):
    def generate(self, model: ModelSpec, prompt: str, **kwargs: object) -> str:
        ...

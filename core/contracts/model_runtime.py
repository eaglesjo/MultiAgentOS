"""Provider-neutral model invocation contracts."""

from dataclasses import dataclass, field
from typing import Protocol

from core.contracts.ai import ModelSpec


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    system: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model_id: str
    metadata: dict[str, object] = field(default_factory=dict)


class ModelAdapter(Protocol):
    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        ...

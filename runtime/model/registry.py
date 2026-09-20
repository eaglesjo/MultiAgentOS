"""Registry for model adapters."""

from core.contracts.model_runtime import ModelAdapter


class ModelAdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ModelAdapter] = {}

    def register(self, adapter_id: str, adapter: ModelAdapter) -> None:
        if adapter_id in self._adapters:
            raise ValueError(f"Model adapter already registered: {adapter_id}")
        self._adapters[adapter_id] = adapter

    def get(self, adapter_id: str) -> ModelAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise LookupError(f"Model adapter not registered: {adapter_id}") from exc

    def list(self) -> tuple[str, ...]:
        return tuple(self._adapters)

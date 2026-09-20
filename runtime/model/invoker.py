"""Model invocation service."""

from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from runtime.model.registry import ModelAdapterRegistry


class ModelInvoker:
    def __init__(self, registry: ModelAdapterRegistry) -> None:
        self.registry = registry

    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        adapter_id = model.metadata.get("adapter_id", model.provider_id)
        if not isinstance(adapter_id, str) or not adapter_id:
            raise ValueError(f"Invalid adapter id for model: {model.id}")
        return self.registry.get(adapter_id).generate(model, request)

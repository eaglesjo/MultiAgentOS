"""Load provider/model configuration from project JSON without vendor-specific branches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.contracts.ai import AIProvider, ModelSpec
from runtime.model.providers import AIProviderRegistry


DEFAULT_CONFIG_PATH = ".multiagentos/providers.json"


class ProviderConfigLoader:
    """Parse a declarative provider configuration into the VYRELON registry."""

    def load(
        self,
        path: Path,
        registry: AIProviderRegistry | None = None,
    ) -> AIProviderRegistry:
        target = registry or AIProviderRegistry()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Provider configuration root must be an object")

        providers = payload.get("providers", [])
        if not isinstance(providers, list):
            raise ValueError("'providers' must be a list")

        for provider_data in providers:
            target.register(self._provider(provider_data))
        return target

    def _provider(self, value: Any) -> AIProvider:
        if not isinstance(value, dict):
            raise ValueError("Provider entry must be an object")

        provider_id = self._required_string(value, "id")
        kind = self._required_string(value, "kind")
        models_data = value.get("models", [])
        if not isinstance(models_data, list):
            raise ValueError(f"Provider {provider_id}: 'models' must be a list")

        models = tuple(
            self._model(provider_id, item)
            for item in models_data
        )
        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError(f"Provider {provider_id}: 'metadata' must be an object")

        return AIProvider(
            id=provider_id,
            kind=kind,
            models=models,
            metadata=dict(metadata),
        )

    def _model(self, provider_id: str, value: Any) -> ModelSpec:
        if not isinstance(value, dict):
            raise ValueError(f"Provider {provider_id}: model entry must be an object")

        model_id = self._required_string(value, "id")
        capabilities = value.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(
            isinstance(item, str) for item in capabilities
        ):
            raise ValueError(
                f"Provider {provider_id}, model {model_id}: "
                "'capabilities' must be a list of strings"
            )

        metadata = value.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError(
                f"Provider {provider_id}, model {model_id}: "
                "'metadata' must be an object"
            )

        return ModelSpec(
            id=model_id,
            provider_id=provider_id,
            capabilities=frozenset(capabilities),
            metadata=dict(metadata),
        )

    @staticmethod
    def _required_string(value: dict[str, Any], key: str) -> str:
        item = value.get(key)
        if not isinstance(item, str) or not item:
            raise ValueError(f"Configuration field '{key}' must be a non-empty string")
        return item

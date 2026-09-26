"""Registry for provider and model configuration used by VYRELON."""

from core.contracts.ai import AIProvider, ModelSpec


class AIProviderRegistry:
    """Resolve provider and model configuration without vendor-specific logic."""

    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}
        self._models: dict[str, ModelSpec] = {}

    def register(self, provider: AIProvider) -> None:
        if provider.id in self._providers:
            raise ValueError(f"AI provider already registered: {provider.id}")
        for model in provider.models:
            if model.provider_id != provider.id:
                raise ValueError(
                    f"Model {model.id} belongs to {model.provider_id}, "
                    f"not provider {provider.id}"
                )
            if model.id in self._models:
                raise ValueError(f"Model already registered: {model.id}")
        self._providers[provider.id] = provider
        for model in provider.models:
            self._models[model.id] = model

    def get_provider(self, provider_id: str) -> AIProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise LookupError(
                f"AI provider not registered: {provider_id}"
            ) from exc

    def get_model(self, model_id: str) -> ModelSpec:
        try:
            return self._models[model_id]
        except KeyError as exc:
            raise LookupError(f"Model not registered: {model_id}") from exc

    def models(self, provider_id: str | None = None) -> tuple[ModelSpec, ...]:
        if provider_id is None:
            return tuple(self._models.values())
        provider = self.get_provider(provider_id)
        return provider.models

    def providers(self) -> tuple[AIProvider, ...]:
        return tuple(self._providers.values())

    def list_provider_ids(self) -> tuple[str, ...]:
        return tuple(self._providers)

    def list_model_ids(self) -> tuple[str, ...]:
        return tuple(self._models)

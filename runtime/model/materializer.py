"""Materialize declarative provider configuration into executable adapters."""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts.ai import AIProvider, ModelSpec
from core.contracts.model_runtime import ModelAdapter
from runtime.model.credentials import EnvironmentCredentialResolver
from runtime.model.native import (
    AnthropicMessagesToolAdapter,
    GeminiGenerateContentToolAdapter,
    OpenAIResponsesToolAdapter,
)
from runtime.model.registry import ModelAdapterRegistry
from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class ProviderMaterialization:
    """Executable adapters plus non-secret credential checks."""

    adapters: ModelAdapterRegistry
    credential_checks: tuple[object, ...]


class NativeProviderMaterializer:
    """Build provider-native adapters from AIProvider metadata.

    Provider configuration remains declarative; this class is the only place that
    maps provider kinds to concrete native adapters.
    """

    _CREDENTIALS = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }

    def __init__(
        self,
        *,
        policy: ExecutionPolicy | None = None,
        credentials: EnvironmentCredentialResolver | None = None,
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.credentials = credentials or EnvironmentCredentialResolver()

    def materialize(
        self,
        providers: tuple[AIProvider, ...],
        registry: ModelAdapterRegistry | None = None,
        *,
        validate_credentials: bool = False,
    ) -> ProviderMaterialization:
        target = registry or ModelAdapterRegistry()
        checks = []
        for provider in providers:
            kind = provider.kind.lower()
            adapter_id = str(provider.metadata.get("adapter_id", provider.id))
            adapter = self._adapter(kind, provider)
            target.register(adapter_id, adapter)
            for model in provider.models:
                model_adapter_id = str(model.metadata.get("adapter_id", adapter_id))
                if model_adapter_id != adapter_id and model_adapter_id not in target.list():
                    target.register(model_adapter_id, adapter)
            if validate_credentials:
                env = str(metadata_env(provider, kind))
                if env:
                    checks.extend(self.credentials.check([env]))
        return ProviderMaterialization(target, tuple(checks))

    def _adapter(self, kind: str, provider: AIProvider) -> ModelAdapter:
        metadata = provider.metadata
        policy = self.policy
        if kind in {"openai", "openai_responses"}:
            return OpenAIResponsesToolAdapter(
                api_key_env=str(metadata.get("api_key_env", "OPENAI_API_KEY")),
                endpoint=str(metadata.get("endpoint", "https://api.openai.com/v1/responses")),
                policy=policy,
            )
        if kind in {"anthropic", "anthropic_messages"}:
            return AnthropicMessagesToolAdapter(
                api_key_env=str(metadata.get("api_key_env", "ANTHROPIC_API_KEY")),
                endpoint=str(metadata.get("endpoint", "https://api.anthropic.com/v1/messages")),
                api_version=str(metadata.get("api_version", "2023-06-01")),
                max_tokens=int(metadata.get("max_tokens", 4096)),
                policy=policy,
            )
        if kind in {"gemini", "gemini_generate_content"}:
            return GeminiGenerateContentToolAdapter(
                api_key_env=str(metadata.get("api_key_env", "GEMINI_API_KEY")),
                endpoint_base=str(metadata.get("endpoint_base", "https://generativelanguage.googleapis.com/v1beta/models")),
                policy=policy,
            )
        raise ValueError(f"Unsupported native provider kind: {provider.kind}")


def metadata_env(provider: AIProvider, kind: str) -> str:
    default = NativeProviderMaterializer._CREDENTIALS.get(kind, "")
    return str(provider.metadata.get("api_key_env", default))

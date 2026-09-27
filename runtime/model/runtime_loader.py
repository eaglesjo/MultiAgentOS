"""One-step loader for declarative VYRELON provider runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime.model.config import ProviderConfigLoader
from runtime.model.credentials import CredentialCheck
from runtime.model.materializer import NativeProviderMaterializer, ProviderMaterialization
from runtime.model.providers import AIProviderRegistry
from runtime.model.registry import ModelAdapterRegistry
from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class ProviderRuntime:
    providers: AIProviderRegistry
    adapters: ModelAdapterRegistry
    credential_checks: tuple[CredentialCheck, ...]


class ProviderRuntimeLoader:
    """Load providers.json and turn its providers into executable adapters."""

    def __init__(
        self,
        *,
        policy: ExecutionPolicy | None = None,
        config_loader: ProviderConfigLoader | None = None,
        materializer: NativeProviderMaterializer | None = None,
    ) -> None:
        self.config_loader = config_loader or ProviderConfigLoader()
        self.materializer = materializer or NativeProviderMaterializer(policy=policy)

    def load(
        self,
        path: Path,
        *,
        validate_credentials: bool = False,
    ) -> ProviderRuntime:
        providers = self.config_loader.load(path)
        materialized = self.materializer.materialize(
            providers.providers(),
            validate_credentials=validate_credentials,
        )
        return ProviderRuntime(
            providers=providers,
            adapters=materialized.adapters,
            credential_checks=materialized.credential_checks,
        )

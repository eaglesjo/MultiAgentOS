"""Provider-neutral discovery adapters for model capabilities and quota."""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from core.contracts.ai import AIProvider, ModelSpec
from core.contracts.capability import CapabilityConfidence, ModelCapabilityProfile
from core.contracts.discovery import DiscoveryError, ProviderDiscoveryResult
from core.contracts.quota import QuotaConfidence, QuotaDimension, QuotaSnapshot
from runtime.policy import ExecutionPolicy


def _path(value: object, path: tuple[str, ...]) -> object:
    current = value
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _string_list(value: object) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(str(item) for item in value if isinstance(item, (str, int, float)))


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProviderDiscoveryAdapter:
    """Discover provider metadata using declarative provider configuration."""

    def __init__(
        self,
        policy: ExecutionPolicy | None = None,
        fetch: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.fetch = fetch or self._fetch

    def discover(
        self,
        provider: AIProvider,
        *,
        models: tuple[ModelSpec, ...] | None = None,
    ) -> ProviderDiscoveryResult:
        metadata = provider.metadata
        discovery = metadata.get("discovery", {})
        if not isinstance(discovery, dict):
            return ProviderDiscoveryResult(provider.id, source="model_spec")

        endpoint = discovery.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint:
            return ProviderDiscoveryResult(provider.id, source="model_spec")

        headers = self._headers(discovery)
        payload = self.fetch(endpoint, headers)
        model_payload = self._extract(payload, discovery.get("models_path", ["data"]))
        quota_payload = self._extract(payload, discovery.get("quota_path", []))

        configured = {model.id: model for model in (models or provider.models)}
        profiles = self._capabilities(provider, model_payload, configured)
        quotas = self._quotas(provider, quota_payload, configured)
        return ProviderDiscoveryResult(
            provider_id=provider.id,
            capabilities=tuple(profiles),
            quotas=tuple(quotas),
            source="provider_discovery",
            metadata={"endpoint": endpoint},
        )

    def discover_safe(
        self,
        provider: AIProvider,
        *,
        models: tuple[ModelSpec, ...] | None = None,
    ) -> tuple[ProviderDiscoveryResult | None, DiscoveryError | None]:
        try:
            return self.discover(provider, models=models), None
        except (OSError, ValueError, RuntimeError) as exc:
            return None, DiscoveryError(
                provider_id=provider.id,
                operation="discover",
                message=str(exc),
                retryable=isinstance(exc, OSError),
            )

    def _capabilities(
        self,
        provider: AIProvider,
        value: object,
        configured: dict[str, ModelSpec],
    ) -> list[ModelCapabilityProfile]:
        if not isinstance(value, list):
            return []
        profiles: list[ModelCapabilityProfile] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id", ""))
            if not model_id:
                continue
            base = configured.get(model_id)
            capabilities = set(base.capabilities if base else ())
            capabilities.update(_string_list(item.get("capabilities")))
            capabilities.update(_string_list(item.get("input_modalities")))
            capabilities.update(_string_list(item.get("output_modalities")))
            for field, capability in (
                ("supports_tools", "tools"),
                ("supports_reasoning", "reasoning"),
                ("supports_vision", "vision"),
            ):
                if item.get(field) is True:
                    capabilities.add(capability)
            profiles.append(
                ModelCapabilityProfile(
                    model_id=model_id,
                    provider_id=provider.id,
                    capabilities=frozenset(capabilities),
                    confidence=CapabilityConfidence.DECLARED,
                    source="provider_discovery",
                    metadata={"provider_metadata": item},
                )
            )
        return profiles

    def _quotas(
        self,
        provider: AIProvider,
        value: object,
        configured: dict[str, ModelSpec],
    ) -> list[QuotaSnapshot]:
        if not isinstance(value, list):
            return []
        snapshots: list[QuotaSnapshot] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("model_id", item.get("model", "")))
            if not model_id or model_id not in configured:
                continue
            raw_dimensions = item.get("dimensions", [])
            dimensions: list[QuotaDimension] = []
            if isinstance(raw_dimensions, list):
                for raw in raw_dimensions:
                    if not isinstance(raw, dict) or not raw.get("name"):
                        continue
                    dimensions.append(
                        QuotaDimension(
                            name=str(raw["name"]),
                            limit=raw.get("limit"),
                            used=raw.get("used"),
                            remaining=raw.get("remaining"),
                            reset_at=_parse_datetime(raw.get("reset_at")),
                            window_seconds=_as_int(raw.get("window_seconds")),
                            confidence=QuotaConfidence.ACTUAL,
                            source="provider_discovery",
                        )
                    )
            snapshots.append(
                QuotaSnapshot(
                    model_id=model_id,
                    provider_id=provider.id,
                    observed_at=_now(),
                    dimensions=tuple(dimensions),
                    scope=str(item.get("scope", "model")),
                    metadata={"provider_metadata": item},
                )
            )
        return snapshots

    @staticmethod
    def _extract(payload: dict[str, Any], value: object) -> object:
        if value in (None, [], ""):
            return None
        if not isinstance(value, list):
            return None
        return _path(payload, tuple(str(item) for item in value))

    @staticmethod
    def _headers(discovery: dict[str, object]) -> dict[str, str]:
        result = {str(k): str(v) for k, v in (discovery.get("headers", {}) or {}).items()}
        for header, env_name in (discovery.get("header_env", {}) or {}).items():
            if isinstance(env_name, str) and os.environ.get(env_name):
                result[str(header)] = os.environ[env_name]
        return result

    def _fetch(self, endpoint: str, headers: dict[str, str]) -> dict[str, Any]:
        if not self.policy.permits("network"):
            raise PermissionError("Network discovery is disabled by policy")
        request = urllib.request.Request(endpoint, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("provider discovery response must be a JSON object")
        return payload


def _as_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

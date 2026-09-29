"""Provider-neutral discovery adapters for model capabilities and quota."""

from __future__ import annotations

import json
import os
import urllib.request
from urllib.error import HTTPError, URLError
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
        fetch: Callable[[str, dict[str, str]], dict[str, Any] | tuple[dict[str, Any], dict[str, str]]] | None = None,
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
        discovery = dict(metadata.get("discovery", {}) or {})
        self._apply_builtin_defaults(provider, discovery)
        if not isinstance(discovery, dict):
            return ProviderDiscoveryResult(provider.id, source="model_spec")

        endpoint = discovery.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint:
            return ProviderDiscoveryResult(provider.id, source="model_spec")

        headers = self._headers(discovery)
        self._query_env = discovery.get("query_env", {})
        fetched = self.fetch(endpoint, headers)
        response_headers = {}
        if isinstance(fetched, tuple):
            payload, response_headers = fetched
        else:
            payload = fetched
        model_payload = self._extract(payload, discovery.get("models_path", ["data"]))
        if provider.kind.lower() == "gemini" and isinstance(model_payload, list):
            model_payload = [self._normalize_gemini_model(item) for item in model_payload]
        quota_payload = self._extract(payload, discovery.get("quota_path", []))

        configured = {model.id: model for model in (models or provider.models)}
        profiles = self._capabilities(provider, model_payload, configured)
        quotas = self._quotas(provider, quota_payload, configured)
        quotas.extend(self._header_quotas(provider, response_headers, configured))
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

    @staticmethod
    def _apply_builtin_defaults(provider: AIProvider, discovery: dict[str, object]) -> None:
        if discovery.get("endpoint"):
            return
        presets = {
            "openai": ("https://api.openai.com/v1/models", "OPENAI_API_KEY", "openai"),
            "anthropic": ("https://api.anthropic.com/v1/models", "ANTHROPIC_API_KEY", "anthropic"),
            "gemini": ("https://generativelanguage.googleapis.com/v1beta/models", "GEMINI_API_KEY", "gemini"),
        }
        preset = presets.get(provider.kind.lower()) or presets.get(provider.id.lower())
        if not preset:
            return
        endpoint, key_env, kind = preset
        discovery["endpoint"] = endpoint
        discovery["models_path"] = ["models"] if kind == "gemini" else ["data"]
        if kind == "gemini":
            discovery["query_env"] = {"key": key_env}
        elif kind == "openai":
            discovery["header_env"] = {"Authorization": key_env}
            discovery["header_prefix"] = {"Authorization": "Bearer "}
        else:
            discovery["header_env"] = {"x-api-key": key_env}
            discovery["headers"] = {"anthropic-version": "2023-06-01"}

    @staticmethod
    def _header_quotas(provider: AIProvider, headers: dict[str, str], configured: dict[str, ModelSpec]) -> list[QuotaSnapshot]:
        mappings = {
            "openai": (
                ("requests", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests"),
                ("tokens", "x-ratelimit-limit-tokens", "x-ratelimit-remaining-tokens"),
            ),
            "anthropic": (
                ("requests", "anthropic-ratelimit-requests-limit", "anthropic-ratelimit-requests-remaining"),
                ("input_tokens", "anthropic-ratelimit-input-tokens-limit", "anthropic-ratelimit-input-tokens-remaining"),
                ("output_tokens", "anthropic-ratelimit-output-tokens-limit", "anthropic-ratelimit-output-tokens-remaining"),
            ),
        }
        rows = mappings.get(provider.kind.lower(), ())
        dimensions = []
        for name, limit_key, remaining_key in rows:
            limit, remaining = _as_int(headers.get(limit_key)), _as_int(headers.get(remaining_key))
            if limit is None and remaining is None:
                continue
            dimensions.append(QuotaDimension(name=name, limit=limit, used=(limit - remaining) if limit is not None and remaining is not None else None,
                remaining=remaining, confidence=QuotaConfidence.ACTUAL, source="provider_response_headers"))
        if not dimensions:
            return []
        return [QuotaSnapshot(model_id=model_id, provider_id=provider.id, observed_at=_now(), dimensions=tuple(dimensions),
            scope="provider", metadata={"source": "provider_response_headers"}) for model_id in configured]
    
    @staticmethod
    def _normalize_gemini_model(item: object) -> object:
        if not isinstance(item, dict):
            return item
        normalized = dict(item)
        name = normalized.get("name")
        if isinstance(name, str) and name.startswith("models/"):
            normalized["id"] = name[len("models/"):]
        methods = normalized.get("supportedGenerationMethods")
        if isinstance(methods, list):
            normalized["capabilities"] = ["chat" if str(method) == "generateContent" else str(method) for method in methods]
        return normalized

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
            capabilities.update(_normalize_capabilities(item))
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
        prefixes = discovery.get("header_prefix", {}) or {}
        for header, env_name in (discovery.get("header_env", {}) or {}).items():
            if isinstance(env_name, str) and os.environ.get(env_name):
                prefix = prefixes.get(header, "") if isinstance(prefixes, dict) else ""
                result[str(header)] = f"{prefix}{os.environ[env_name]}"
        return result

    def _fetch(self, endpoint: str, headers: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
        if not self.policy.permits("network"):
            raise PermissionError("Network discovery is disabled by policy")
        query_env = getattr(self, "_query_env", {})
        if query_env:
            from urllib.parse import urlencode, urlsplit, urlunsplit
            parts = urlsplit(endpoint)
            query = {key: os.environ.get(env, "") for key, env in query_env.items()}
            endpoint = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        request = urllib.request.Request(endpoint, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
                response_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
        except HTTPError as exc:
            raise RuntimeError(f"provider discovery failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("provider discovery failed: network error") from exc
        if not isinstance(payload, dict):
            raise ValueError("provider discovery response must be a JSON object")
        return payload, response_headers

def _normalize_capabilities(item: dict[str, object]) -> frozenset[str]:
    """Normalize provider-specific metadata to AGENT_EXECUTION_RUNTIME routing vocabulary."""
    aliases = {
        "generatecontent": "chat",
        "generate_content": "chat",
        "chat": "chat",
        "embedcontent": "embeddings",
        "embed_content": "embeddings",
        "embeddings": "embeddings",
        "predictlongrunning": "predict",
        "counttokens": "token_count",
        "function_calling": "tools",
        "function-calling": "tools",
        "structured-outputs": "structured_output",
    }
    result: set[str] = set()
    for field in ("capabilities", "supportedGenerationMethods"):
        for value in _string_list(item.get(field)):
            key = value.strip().lower().replace(" ", "_")
            result.add(aliases.get(key, key))
    for field in ("input_modalities", "output_modalities", "modalities"):
        for value in _string_list(item.get(field)):
            key = value.strip().lower()
            result.add(aliases.get(key, key))
    for field, capability in (
        ("supports_tools", "tools"),
        ("supports_reasoning", "reasoning"),
        ("supports_vision", "vision"),
        ("supports_audio", "audio"),
        ("supports_image", "image"),
        ("supports_structured_output", "structured_output"),
    ):
        if item.get(field) is True:
            result.add(capability)
    return frozenset(result)


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

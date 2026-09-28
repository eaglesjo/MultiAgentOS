"""Provider discovery contracts for VYRELON model intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.contracts.capability import ModelCapabilityProfile
from core.contracts.quota import QuotaSnapshot


@dataclass(frozen=True)
class ProviderDiscoveryResult:
    """Normalized discovery result returned by a provider adapter."""

    provider_id: str
    capabilities: tuple[ModelCapabilityProfile, ...] = ()
    quotas: tuple[QuotaSnapshot, ...] = ()
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveryError:
    """Non-fatal discovery failure for one provider."""

    provider_id: str
    operation: str
    message: str
    retryable: bool = False

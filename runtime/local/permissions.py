"""Local tool permission enforcement."""

from __future__ import annotations

from dataclasses import dataclass

from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class LocalPermissionGuard:
    """Apply VYRELON execution policy to local tool operations."""

    policy: ExecutionPolicy

    def require(self, capability: str, *, approved: bool = False) -> None:
        if not self.policy.permits(capability):
            raise PermissionError(f"local capability is disabled: {capability}")
        if self.policy.requires_approval(capability) and not approved:
            raise PermissionError(f"explicit approval required for: {capability}")

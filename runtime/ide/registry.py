"""Registry for optional IDE adapters."""

from __future__ import annotations

from core.contracts.ide import IDEAdapter, IDEKind


class IDEAdapterRegistry:
    """Register and resolve IDE adapters without IDE SDK dependencies."""

    def __init__(self) -> None:
        self._adapters: dict[IDEKind, IDEAdapter] = {}

    def register(self, adapter: IDEAdapter) -> None:
        self._adapters[adapter.kind] = adapter

    def get(self, kind: IDEKind) -> IDEAdapter:
        try:
            return self._adapters[kind]
        except KeyError as exc:
            raise LookupError(f"IDE adapter not registered: {kind.value}") from exc

    def list(self) -> tuple[IDEKind, ...]:
        return tuple(self._adapters)

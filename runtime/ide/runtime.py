"""High-level facade for optional IDE adapters."""

from __future__ import annotations

from core.contracts.ide import IDEAdapter, IDECommand, IDECommandResult, IDEContext, IDEEvent, IDEKind
from runtime.ide.registry import IDEAdapterRegistry


class IDERuntime:
    """Expose IDE adapters without importing any native IDE SDK."""

    def __init__(self, registry: IDEAdapterRegistry | None = None) -> None:
        self.registry = registry or IDEAdapterRegistry()

    def register(self, adapter: IDEAdapter) -> None:
        self.registry.register(adapter)

    def context(self, kind: IDEKind) -> IDEContext:
        return self.registry.get(kind).context()

    def execute(self, kind: IDEKind, command: IDECommand) -> IDECommandResult:
        return self.registry.get(kind).execute(command)

    def ingest_event(self, event: IDEEvent) -> object:
        """Accept an IDE-originated event without treating it as a command."""
        return event

    def capabilities(self, kind: IDEKind) -> frozenset[str]:
        return self.registry.get(kind).capabilities()

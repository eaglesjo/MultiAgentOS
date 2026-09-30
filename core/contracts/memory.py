"""Durable project memory contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MemoryKind(StrEnum):
    FACT = "fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    NOTE = "note"


@dataclass(frozen=True)
class ProjectMemory:
    memory_id: str
    kind: MemoryKind
    content: str
    source: str
    created_at: str
    metadata: dict[str, object]


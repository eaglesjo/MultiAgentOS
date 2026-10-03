"""Evidence contracts for deterministic Agent Execution Runtime validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EvidenceKind(StrEnum):
    FACT = "fact"
    ASSUMPTION = "assumption"
    HYPOTHESIS = "hypothesis"
    VERIFIED = "verified"


@dataclass(frozen=True)
class EvidenceRecord:
    """A bounded, inspectable claim attached to a WorkUnit."""

    id: str
    work_unit_id: str
    kind: EvidenceKind
    source: str
    statement: str
    command: str | None = None
    exit_code: int | None = None
    artifact_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        for name, value in (
            ("id", self.id),
            ("work_unit_id", self.work_unit_id),
            ("source", self.source),
            ("statement", self.statement),
        ):
            if not value.strip():
                raise ValueError(f"evidence {name} must not be empty")
        if self.exit_code is not None and self.command is None:
            raise ValueError("exit_code requires command")

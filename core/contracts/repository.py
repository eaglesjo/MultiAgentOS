"""Repository-level contracts for VYRELON."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RepositoryCheckpoint:
    id: str
    project_root: str
    marker: str
    status: str
    diff: str
    created_at: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RepositoryEvidence:
    checkpoint_id: str | None
    git_status: str
    git_diff: str
    workflows: tuple[object, ...] = ()
    validation: dict[str, object] | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryResult:
    checkpoint_id: str
    restored: bool
    output: str
    error: str = ""

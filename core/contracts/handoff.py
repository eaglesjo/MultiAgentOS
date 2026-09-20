"""Handoff artifact contracts."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HandoffArtifact:
    work_unit_id: str
    from_agent: str
    to_agent: str
    summary: str
    artifacts: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewResult:
    approved: bool
    reviewer_id: str
    feedback: str

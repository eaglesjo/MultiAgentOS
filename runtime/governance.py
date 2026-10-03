"""Deterministic governance helpers migrated from PetTarotReading."""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts.evidence import EvidenceRecord, EvidenceKind
from core.contracts.scope import ScopeLock
from core.contracts.work_unit import WorkUnit


ROUTE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "simple": ("planner", "editor", "executor", "reviewer"),
    "external_research": ("planner", "web-researcher", "editor", "executor", "reviewer"),
    "web_ui": ("planner", "editor", "executor", "browser-agent", "reviewer"),
    "failure": ("planner", "executor", "terminal-monitor", "debugger", "executor", "reviewer"),
}


@dataclass(frozen=True)
class GovernanceCheck:
    passed: bool
    findings: tuple[str, ...] = ()


def smallest_sufficient_path(work_type: str) -> tuple[str, ...]:
    """Return a bounded execution-role path without invoking every role."""
    try:
        return ROUTE_TEMPLATES[work_type]
    except KeyError as exc:
        raise ValueError(f"unsupported governance work type: {work_type}") from exc


def validate_scope(scope: ScopeLock) -> GovernanceCheck:
    try:
        scope.validate()
    except ValueError as exc:
        return GovernanceCheck(False, (str(exc),))
    return GovernanceCheck(True)


def validate_evidence(
    work_unit: WorkUnit,
    evidence: tuple[EvidenceRecord, ...],
    *,
    require_verified: bool = False,
) -> GovernanceCheck:
    findings: list[str] = []
    for record in evidence:
        try:
            record.validate()
        except ValueError as exc:
            findings.append(str(exc))
            continue
        if record.work_unit_id != work_unit.id:
            findings.append(
                f"evidence {record.id} belongs to {record.work_unit_id}, "
                f"not {work_unit.id}"
            )
    if require_verified and not any(item.kind is EvidenceKind.VERIFIED for item in evidence):
        findings.append("verified evidence is required")
    return GovernanceCheck(not findings, tuple(findings))

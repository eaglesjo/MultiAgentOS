"""Deterministic governance helpers migrated from PetTarotReading."""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.handoff import ArtifactContract
from core.contracts.planning import PlanStep, WorkPlan
from core.contracts.scope import ScopeLock
from core.contracts.work_unit import WorkUnit


ROUTE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "simple": ("file-picker", "planner", "editor", "executor", "reviewer"),
    "external_research": (
        "file-picker",
        "planner",
        "web-researcher",
        "editor",
        "executor",
        "reviewer",
    ),
    "web_ui": (
        "file-picker",
        "planner",
        "editor",
        "executor",
        "browser-agent",
        "reviewer",
    ),
    "failure": (
        "file-picker",
        "planner",
        "executor",
        "terminal-monitor",
        "debugger",
        "executor",
        "reviewer",
    ),
}

WORK_TYPE_ALIASES = {
    "development": "simple",
    "simple": "simple",
    "external_research": "external_research",
    "research": "external_research",
    "web_ui": "web_ui",
    "failure": "failure",
}


@dataclass(frozen=True)
class GovernanceCheck:
    passed: bool
    findings: tuple[str, ...] = ()


def smallest_sufficient_path(work_type: str) -> tuple[str, ...]:
    """Return the smallest bounded execution-role path for a work type."""
    route = WORK_TYPE_ALIASES.get(work_type, work_type)
    try:
        return ROUTE_TEMPLATES[route]
    except KeyError as exc:
        raise ValueError(f"unsupported governance work type: {work_type}") from exc


def validate_scope(scope: ScopeLock) -> GovernanceCheck:
    try:
        scope.validate()
    except ValueError as exc:
        return GovernanceCheck(False, (str(exc),))
    return GovernanceCheck(True)


def validate_plan(work_unit: WorkUnit, plan: WorkPlan) -> GovernanceCheck:
    findings: list[str] = []
    try:
        plan.validate()
        work_unit.scope_lock.validate()
        for step in plan.steps:
            if not work_unit.scope_lock.contains(step.scope_lock):
                findings.append(f"plan step scope escapes WorkUnit scope: {step.id}")
    except ValueError as exc:
        findings.append(str(exc))
    return GovernanceCheck(not findings, tuple(findings))


def validate_artifacts(
    work_unit: WorkUnit,
    artifacts: tuple[ArtifactContract, ...],
) -> GovernanceCheck:
    findings: list[str] = []
    for artifact in artifacts:
        try:
            artifact.validate()
        except ValueError as exc:
            findings.append(str(exc))
            continue
        if artifact.id not in work_unit.artifacts:
            findings.append(
                f"artifact {artifact.id} is not registered on WorkUnit {work_unit.id}"
            )
    return GovernanceCheck(not findings, tuple(findings))


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
    if require_verified and not any(
        item.kind is EvidenceKind.VERIFIED for item in evidence
    ):
        findings.append("verified evidence is required")
    return GovernanceCheck(not findings, tuple(findings))


def route_plan_steps(
    work_unit: WorkUnit,
    *,
    work_type: str | None = None,
) -> tuple[PlanStep, ...]:
    """Build the native PlanStep route for the smallest sufficient path."""
    route = smallest_sufficient_path(work_type or work_unit.work_type)
    return tuple(
        PlanStep(
            id=f"{agent_id}-{index + 1}",
            objective=f"{agent_id} stage for: {work_unit.objective}",
            agent_id=agent_id,
            depends_on=(f"{route[index - 1]}-{index}",) if index else (),
            scope_lock=work_unit.scope_lock,
        )
        for index, agent_id in enumerate(route)
    )

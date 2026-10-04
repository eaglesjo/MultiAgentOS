"""Deterministic governance and specialist routing helpers."""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.handoff import ArtifactContract
from core.contracts.planning import PlanStep, WorkPlan
from core.contracts.scope import ScopeLock
from core.contracts.work_unit import WorkUnit


GOVERNANCE_PREFIX = ("file-picker", "planner")
GOVERNANCE_SUFFIX = ("editor", "executor", "reviewer")

ROUTE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "simple": (
        "file-picker",
        "planner",
        "editor",
        "executor",
        "reviewer",
    ),
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
        "ui-research-web",
        "ui-web",
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
    "development": "development",
    "simple": "simple",
    "external_research": "external_research",
    "research": "external_research",
    "development_research": "development_research",
    "ui_research": "ui_research",
    "ui": "ui",
    "web_ui": "web_ui",
    "failure": "failure",
}


_PLATFORM_ALIASES = {
    "react": "react",
    "web": "react",
    "react-native": "react-native",
    "react_native": "react-native",
    "android": "android",
    "android-native": "android",
    "ios": "ios",
    "ios-native": "ios",
}


_DEVELOPMENT_SPECIALISTS = {
    "react": ("development-research-react", "react-developer"),
    "react-native": (
        "development-research-react-native",
        "react-native-developer",
    ),
    "android": ("development-research-android", "android-developer"),
    "ios": ("development-research-ios", "ios-developer"),
}


_UI_SPECIALISTS = {
    "react": ("ui-research-web", "ui-web", "browser-agent"),
    "react-native": (
        "ui-research-react-native",
        "ui-react-native",
        "tester",
    ),
    "android": ("ui-research-android", "ui-android", "tester"),
    "ios": ("ui-research-ios", "ui-ios", "tester"),
}


@dataclass(frozen=True)
class GovernanceCheck:
    passed: bool
    findings: tuple[str, ...] = ()


def _normalize_platform(target: str) -> str:
    normalized = _PLATFORM_ALIASES.get(target.strip().lower())
    if normalized is None:
        raise ValueError(f"unsupported specialist platform: {target}")
    return normalized


def _specialist_platform(work_unit: WorkUnit) -> str:
    target = work_unit.target or str(work_unit.metadata.get("platform", ""))
    return _normalize_platform(target)


def smallest_sufficient_path(work_type: str) -> tuple[str, ...]:
    """Return the smallest bounded execution-role path for a work type."""
    route = WORK_TYPE_ALIASES.get(work_type, work_type)
    if route == "development":
        return ROUTE_TEMPLATES["simple"]
    if route in ROUTE_TEMPLATES:
        return ROUTE_TEMPLATES[route]
    if route in {"research", "development_research", "ui_research", "ui"}:
        raise ValueError(
            f"specialist target is required for work type: {work_type}"
        )
    raise ValueError(f"unsupported governance work type: {work_type}")


def specialist_route(
    work_unit: WorkUnit,
    *,
    research_required: bool | None = None,
) -> tuple[str, ...]:
    """Compose governance stages with a platform/domain specialist path."""
    work_type = WORK_TYPE_ALIASES.get(work_unit.work_type, work_unit.work_type)

    if work_type == "development":
        platform = _specialist_platform(work_unit)
        research, developer = _DEVELOPMENT_SPECIALISTS[platform]
        include_research = (
            bool(work_unit.metadata.get("research_required", True))
            if research_required is None
            else research_required
        )
        specialist = (research, developer) if include_research else (developer,)
        return GOVERNANCE_PREFIX + specialist + GOVERNANCE_SUFFIX

    if work_type == "development_research":
        platform = _specialist_platform(work_unit)
        return GOVERNANCE_PREFIX + (_DEVELOPMENT_SPECIALISTS[platform][0],) + (
            "reviewer",
        )

    if work_type == "ui_research":
        platform = _specialist_platform(work_unit)
        return GOVERNANCE_PREFIX + (_UI_SPECIALISTS[platform][0],) + ("reviewer",)

    if work_type == "ui":
        platform = _specialist_platform(work_unit)
        research, ui_agent, validation = _UI_SPECIALISTS[platform]
        return GOVERNANCE_PREFIX + (
            research,
            ui_agent,
            "editor",
            "executor",
            validation,
            "reviewer",
        )

    if work_type == "research":
        return ROUTE_TEMPLATES["external_research"]

    return smallest_sufficient_path(work_type)


def validate_specialist_route(
    work_unit: WorkUnit,
    agent_ids: tuple[str, ...],
) -> GovernanceCheck:
    """Ensure the planned specialist stages match the requested taxonomy."""
    expected = specialist_route(work_unit)
    if agent_ids != expected:
        return GovernanceCheck(
            False,
            (
                "specialist route mismatch: "
                f"expected {expected}, got {agent_ids}",
            ),
        )
    return GovernanceCheck(True)


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
    """Build native PlanStep objects for governance + specialist routing."""
    effective_type = work_type or work_unit.work_type
    if effective_type == "web_ui" and not (\n        work_unit.target or work_unit.metadata.get("platform")\n    ):\n        route = ROUTE_TEMPLATES["web_ui"]\n    elif effective_type in {"development", "simple"} and (
        work_unit.target or work_unit.metadata.get("platform")
    ):
        route = specialist_route(work_unit)
    elif effective_type in {"development", "simple"}:
        route = smallest_sufficient_path(effective_type)
    else:
        route = specialist_route(work_unit)

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

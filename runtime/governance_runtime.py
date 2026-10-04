"""Operational governance runtime for the native MultiAgentOS lifecycle."""

from __future__ import annotations

from core.contracts.evidence import EvidenceRecord
from core.contracts.handoff import ArtifactContract
from core.contracts.planning import WorkPlan
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.governance import (
    validate_artifacts,
    validate_evidence,
    validate_plan,
    validate_scope,
    validate_specialist_route,
)


class GovernanceRuntime:
    """Enforce governance at execution boundaries without replacing Orchestrator."""

    def validate_work_unit(self, work_unit: WorkUnit) -> None:
        check = validate_scope(work_unit.scope_lock)
        if not check.passed:
            raise ValueError("Invalid WorkUnit scope: " + "; ".join(check.findings))

    def validate_plan(self, work_unit: WorkUnit, plan: WorkPlan) -> None:
        check = validate_plan(work_unit, plan)
        if not check.passed:
            raise ValueError("Invalid governed plan: " + "; ".join(check.findings))
        if work_unit.work_type in {"development", "development_research", "ui", "ui_research"}:
            route_check = validate_specialist_route(
                work_unit,
                tuple(step.agent_id or "" for step in plan.steps),
            )
            if not route_check.passed:
                raise ValueError("Invalid specialist route: " + "; ".join(route_check.findings))

    def validate_artifacts(
        self,
        work_unit: WorkUnit,
        artifacts: tuple[ArtifactContract, ...],
    ) -> None:
        check = validate_artifacts(work_unit, artifacts)
        if not check.passed:
            raise ValueError("Invalid governed artifacts: " + "; ".join(check.findings))

    def validate_evidence(
        self,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
        *,
        require_verified: bool = False,
    ) -> None:
        check = validate_evidence(
            work_unit,
            evidence,
            require_verified=require_verified,
        )
        if not check.passed:
            raise ValueError("Invalid governed evidence: " + "; ".join(check.findings))

    def enforce_hold(self, work_unit: WorkUnit) -> None:
        if work_unit.status is WorkStatus.HOLD:
            raise PermissionError(
                "WorkUnit is on HOLD; explicit authorization is required before execution"
            )

    def mark_execution_ready_for_approval(
        self,
        work_unit: WorkUnit,
        *,
        evidence: tuple[EvidenceRecord, ...] = (),
    ) -> None:
        """Stop release-impacting work at the human approval boundary."""
        self.validate_work_unit(work_unit)
        artifacts = tuple(
            artifact
            for artifact in work_unit.metadata.get("artifacts", ())
            if isinstance(artifact, ArtifactContract)
        )
        self.validate_artifacts(work_unit, artifacts)
        self.validate_evidence(
            work_unit,
            evidence,
            require_verified=work_unit.release_impact != "none",
        )
        work_unit.metadata["governance_evidence"] = tuple(
            evidence
        )
        if work_unit.status is not WorkStatus.COMPLETED:
            raise ValueError(
                "release-impacting work must complete execution before approval gating"
            )
        work_unit.transition(WorkStatus.READY_FOR_APPROVAL)
        work_unit.metadata["human_approval_required"] = True

    def approve(self, work_unit: WorkUnit, *, authorized: bool = False, notes: str = "") -> None:
        if work_unit.status is not WorkStatus.READY_FOR_APPROVAL:
            raise ValueError("WorkUnit is not ready for human approval")
        if not authorized:
            raise PermissionError("human approval requires explicit authorization")
        work_unit.metadata["human_approval_required"] = False
        work_unit.metadata["human_approval"] = "approved"
        if notes.strip():
            work_unit.metadata["human_approval_notes"] = notes
        work_unit.transition(WorkStatus.USER_APPROVED)

    def release(self, work_unit: WorkUnit, *, authorized: bool = False) -> None:
        """Record the explicit approval boundary; callers own the external action."""
        if work_unit.status is not WorkStatus.USER_APPROVED:
            raise PermissionError(
                "release requires explicit human approval before irreversible action"
            )
        if not authorized:
            raise PermissionError("release requires explicit authorization")
        work_unit.transition(WorkStatus.RELEASED)
        work_unit.transition(WorkStatus.COMPLETED)
        work_unit.metadata["released"] = True

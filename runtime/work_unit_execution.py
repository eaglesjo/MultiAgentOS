"""Automatic local-first execution for one durable WorkUnit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.contracts.execution_mission import (
    ExecutionEvidence,
    ExecutionMission,
    MissionOperation,
    verify_execution_evidence,
)
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.execution_route import ExecutionRoute, select_execution_route


class LocalExecutionUnavailable(RuntimeError):
    """Raised when local execution cannot start and remote fallback is safe."""


@dataclass(frozen=True)
class AutomaticExecutionResult:
    work_unit: WorkUnit
    route: ExecutionRoute
    output: object | None = None
    evidence: ExecutionEvidence | None = None


class AutomaticWorkUnitExecutor:
    """Execute one WorkUnit locally first, with one bounded remote fallback."""

    def __init__(self, *, allow_github_actions: bool = False) -> None:
        self.allow_github_actions = allow_github_actions

    def execute(
        self,
        work_unit: WorkUnit,
        *,
        local: Callable[[WorkUnit], object] | None = None,
        remote: Callable[[WorkUnit], tuple[object, ExecutionEvidence]] | None = None,
        local_available: bool = True,
        force_remote: bool = False,
        prefer_local: bool = True,
    ) -> AutomaticExecutionResult:
        decision = select_execution_route(
            local_available=local_available,
            force_remote=force_remote,
            allow_github_actions=self.allow_github_actions,
            prefer_local=prefer_local,
        )

        if decision.route is ExecutionRoute.BLOCKED:
            work_unit.metadata["execution_route"] = ExecutionRoute.BLOCKED.value
            work_unit.metadata["execution_block_reason"] = decision.reason
            if work_unit.status is WorkStatus.PENDING:
                work_unit.transition(WorkStatus.BLOCKED)
            raise PermissionError(decision.reason)

        if decision.route is ExecutionRoute.LOCAL:
            if local is None:
                message = "local execution route requires a local runner"
                work_unit.metadata["execution_route"] = ExecutionRoute.LOCAL.value
                work_unit.metadata["execution_error"] = message
                if work_unit.status is WorkStatus.PENDING:
                    work_unit.transition(WorkStatus.FAILED)
                raise ValueError(message)
            if work_unit.status is WorkStatus.PENDING:
                work_unit.transition(WorkStatus.EXECUTING)
            try:
                output = local(work_unit)
            except LocalExecutionUnavailable as exc:
                work_unit.metadata["local_execution_error"] = str(exc)
                if remote is None or not self.allow_github_actions:
                    work_unit.transition(WorkStatus.FAILED)
                    raise
                return self._run_remote_fallback(work_unit, remote)
            except Exception as exc:
                work_unit.metadata["local_execution_error"] = str(exc)
                work_unit.transition(WorkStatus.FAILED)
                raise
            work_unit.transition(WorkStatus.VERIFYING)
            work_unit.transition(WorkStatus.COMPLETED)
            return AutomaticExecutionResult(work_unit, ExecutionRoute.LOCAL, output=output)

        if remote is None:
            message = "GitHub Actions route requires a bounded remote runner"
            work_unit.metadata["execution_route"] = ExecutionRoute.GITHUB_ACTIONS.value
            work_unit.metadata["execution_error"] = message
            if work_unit.status is WorkStatus.PENDING:
                work_unit.transition(WorkStatus.FAILED)
            raise ValueError(message)
        return self._run_remote_fallback(work_unit, remote)

    def _run_remote_fallback(
        self,
        work_unit: WorkUnit,
        remote: Callable[[WorkUnit], tuple[object, ExecutionEvidence]],
    ) -> AutomaticExecutionResult:
        if work_unit.status is WorkStatus.FAILED:
            work_unit.transition(WorkStatus.EXECUTING)
        elif work_unit.status is WorkStatus.PENDING:
            work_unit.transition(WorkStatus.EXECUTING)

        try:
            output, evidence = remote(work_unit)
        except Exception as exc:
            work_unit.metadata["remote_execution_error"] = str(exc)
            if work_unit.status is WorkStatus.EXECUTING:
                work_unit.transition(WorkStatus.FAILED)
            raise
        work_unit.metadata["execution_route"] = ExecutionRoute.GITHUB_ACTIONS.value
        work_unit.metadata["execution_evidence"] = {
            "mission_id": evidence.mission_id,
            "run_id": evidence.run_id,
            "status": evidence.status,
            "conclusion": evidence.conclusion,
            "source_sha": evidence.source_sha,
            "head_sha": evidence.head_sha,
            "artifacts": list(evidence.artifacts),
        }

        if evidence.status in {"completed", "success"} and evidence.conclusion == "success":
            mission_data = work_unit.metadata.get("execution_mission")
            if isinstance(mission_data, dict):
                try:
                    mission = ExecutionMission(
                        id=str(mission_data["id"]),
                        repository=str(mission_data["repository"]),
                        source_sha=str(mission_data["source_sha"]),
                        workflow=str(mission_data["workflow"]),
                        operation=MissionOperation(str(mission_data["operation"])),
                        ref=mission_data.get("ref"),
                        expected_artifacts=tuple(mission_data.get("expected_artifacts", ())),
                    )
                    verify_execution_evidence(mission, evidence)
                except Exception:
                    if work_unit.status is WorkStatus.EXECUTING:
                        work_unit.transition(WorkStatus.FAILED)
                    raise
            if work_unit.status is WorkStatus.EXECUTING:
                work_unit.transition(WorkStatus.VERIFYING)
                work_unit.transition(WorkStatus.COMPLETED)
        else:
            if work_unit.status is WorkStatus.EXECUTING:
                work_unit.transition(WorkStatus.FAILED)

        return AutomaticExecutionResult(
            work_unit,
            ExecutionRoute.GITHUB_ACTIONS,
            output=output,
            evidence=evidence,
        )

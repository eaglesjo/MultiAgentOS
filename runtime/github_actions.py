"""Bounded GitHub Actions execution for Agent Execution Runtime."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from core.contracts.execution_mission import (
    ExecutionEvidence,
    ExecutionMission,
    MissionOperation,
    verify_execution_evidence,
)
from core.contracts.github import GitHubGateway, WorkflowRun
from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class GitHubActionsMissionResult:
    mission: ExecutionMission
    evidence: ExecutionEvidence


class GitHubActionsMissionRuntime:
    """Dispatch and verify one bounded GitHub Actions mission."""

    def __init__(
        self,
        gateway: GitHubGateway,
        policy: ExecutionPolicy | None = None,
        *,
        poll_interval_seconds: float = 2.0,
        timeout_seconds: float = 900.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.gateway = gateway
        self.policy = policy or ExecutionPolicy()
        self.poll_interval_seconds = poll_interval_seconds
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep

    def run(self, mission: ExecutionMission) -> GitHubActionsMissionResult:
        mission.validate()
        if not self.policy.permits("github.actions"):
            raise PermissionError("GitHub Actions execution is disabled by policy")

        workflow_ref = (
            mission.ref
            or self.gateway.get_repository(mission.repository).default_branch
        )
        run = self.gateway.dispatch_workflow(
            mission.repository,
            mission.workflow,
            workflow_ref,
            {
                "mission_id": mission.id,
                "source_sha": mission.source_sha,
                "operation": mission.operation.value,
                **mission.inputs,
            },
        )
        evidence = self._wait_for_terminal(mission, run)
        verify_execution_evidence(mission, evidence)
        return GitHubActionsMissionResult(mission=mission, evidence=evidence)

    def _wait_for_terminal(
        self, mission: ExecutionMission, run: WorkflowRun
    ) -> ExecutionEvidence:
        deadline = time.monotonic() + self.timeout_seconds
        current = run
        while current.status not in {"completed", "success"}:
            if time.monotonic() >= deadline:
                return ExecutionEvidence(
                    mission_id=mission.id,
                    run_id=current.id,
                    status=current.status,
                    conclusion=current.conclusion,
                    head_sha=current.head_sha,
                    url=current.url,
                )
            self.sleep(self.poll_interval_seconds)
            current = self.gateway.get_workflow_run(mission.repository, current.id)

        artifacts = tuple(
            artifact.name
            for artifact in self.gateway.list_workflow_artifacts(
                mission.repository, current.id
            )
        )
        return ExecutionEvidence(
            mission_id=mission.id,
            run_id=current.id,
            status=current.status,
            conclusion=current.conclusion,
            head_sha=current.head_sha,
            url=current.url,
            artifacts=artifacts,
            logs_available=current.conclusion is not None,
        )

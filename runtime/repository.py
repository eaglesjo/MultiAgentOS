"""Repository runtime combining Git, GitHub, checkpoints, recovery, and evidence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.contracts.repository import RecoveryResult, RepositoryCheckpoint, RepositoryEvidence
from runtime.git import GitRuntime
from runtime.github import GitHubRuntime
from runtime.policy import ExecutionPolicy


class RepositoryRuntime:
    def __init__(
        self,
        git: GitRuntime,
        github: GitHubRuntime,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.git = git
        self.github = github

    def checkpoint(self, project_root: Path, *, metadata: dict[str, object] | None = None) -> RepositoryCheckpoint:
        checkpoint_id = f"cp-{uuid.uuid4().hex[:12]}"
        marker = f"AGENT_EXECUTION_RUNTIME checkpoint {checkpoint_id}"
        initial_status = self.git.status(project_root.as_posix())
        has_changes = bool(initial_status.stdout.splitlines()[1:])
        stashed = False
        if has_changes:
            result = self.git.stash(project_root.as_posix(), "push", marker)
            stashed = result.returncode == 0
            if not stashed:
                raise RuntimeError(result.stderr.strip() or "failed to create Git checkpoint")
        status = self.git.status(project_root.as_posix())
        diff = self.git.diff(project_root.as_posix())
        checkpoint = RepositoryCheckpoint(
            id=checkpoint_id,
            project_root=str(project_root),
            marker=marker,
            status=status.stdout,
            diff=diff.stdout,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata={**dict(metadata or {}), "stashed": stashed},
        )
        self._persist_checkpoint(project_root, checkpoint)
        return checkpoint

    def recover(self, project_root: Path, checkpoint: RepositoryCheckpoint) -> RecoveryResult:
        if not bool(checkpoint.metadata.get("stashed", False)):
            return RecoveryResult(checkpoint.id, True, "No local changes required recovery", "")
        result = self.git.stash(project_root.as_posix(), "pop")
        if result.returncode == 0:
            return RecoveryResult(checkpoint.id, True, result.stdout, "")
        return RecoveryResult(checkpoint.id, False, result.stdout, result.stderr)

    def evidence(
        self,
        project_root: Path,
        *,
        repository: str | None = None,
        ref: str | None = None,
        validation: dict[str, object] | None = None,
    ) -> RepositoryEvidence:
        status = self.git.status(project_root.as_posix())
        diff = self.git.diff(project_root.as_posix())
        workflows = ()
        if repository and ref:
            workflows = tuple(self.github.gateway.list_workflows(repository, ref))
        evidence = RepositoryEvidence(
            checkpoint_id=self._latest_checkpoint_id(project_root),
            git_status=status.stdout,
            git_diff=diff.stdout,
            workflows=workflows,
            validation=validation,
            metadata={"runtime": "agent_execution_runtime-repository"},
        )
        path = project_root / ".multiagentos" / "evidence" / "repository.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "checkpoint_id": evidence.checkpoint_id,
            "git_status": evidence.git_status,
            "git_diff": evidence.git_diff,
            "workflows": [getattr(item, "__dict__", str(item)) for item in evidence.workflows],
            "validation": evidence.validation,
            "metadata": evidence.metadata,
        }, indent=2, default=str) + "\n", encoding="utf-8")
        return evidence

    def _persist_checkpoint(self, project_root: Path, checkpoint: RepositoryCheckpoint) -> None:
        path = project_root / ".multiagentos" / "checkpoints" / f"{checkpoint.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(checkpoint.__dict__, indent=2) + "\n", encoding="utf-8")

    def _latest_checkpoint_id(self, project_root: Path) -> str | None:
        directory = project_root / ".multiagentos" / "checkpoints"
        if not directory.exists():
            return None
        files = sorted(directory.glob("cp-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        return files[0].stem if files else None

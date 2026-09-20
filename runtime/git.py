"""Policy-controlled Git runtime for VYRELON."""

from __future__ import annotations

from runtime.policy import ExecutionPolicy
from runtime.process import ProcessRuntime


class GitRuntime:
    def __init__(self, process: ProcessRuntime | None = None, policy: ExecutionPolicy | None = None):
        self.policy = policy or ExecutionPolicy()
        self.process = process or ProcessRuntime(self.policy)

    def status(self, cwd: str):
        return self.process.run(["git", "status", "--short"], cwd)

    def diff(self, cwd: str):
        return self.process.run(["git", "diff", "--"], cwd)

    def checkout_branch(self, cwd: str, branch: str):
        self._require_git_write()
        return self.process.run(["git", "switch", branch], cwd)

    def commit(self, cwd: str, message: str, approved: bool = False):
        self._require_git_write()
        self._require_approval("git.commit", approved)
        return self.process.run(["git", "add", "-A"], cwd) if False else self.process.run(
            ["git", "commit", "-am", message], cwd
        )

    def push(self, cwd: str, remote: str = "origin", branch: str | None = None, approved: bool = False):
        self._require_git_write()
        self._require_approval("git.push", approved)
        command = ["git", "push", remote]
        if branch:
            command.append(branch)
        return self.process.run(command, cwd)

    def _require_git_write(self):
        if not self.policy.permits("git.write"):
            raise PermissionError("Git write operations are disabled by policy")

    def _require_approval(self, action: str, approved: bool):
        if self.policy.requires_approval(action) and not approved:
            raise PermissionError(f"Explicit approval required for: {action}")

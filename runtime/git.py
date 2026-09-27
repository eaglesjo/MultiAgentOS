"""Policy-controlled Git runtime for VYRELON."""

from __future__ import annotations

from runtime.process import ProcessRuntime
from runtime.policy import ExecutionPolicy


class GitRuntime:
    def __init__(self, process: ProcessRuntime | None = None, policy: ExecutionPolicy | None = None):
        self.policy = policy or ExecutionPolicy()
        self.process = process or ProcessRuntime(self.policy)

    def status(self, cwd: str):
        return self.process.run(["git", "status", "--short", "--branch"], cwd)

    def diff(self, cwd: str, *, staged: bool = False, path: str | None = None):
        command = ["git", "diff"]
        if staged:
            command.append("--staged")
        if path:
            command.extend(["--", path])
        else:
            command.append("--")
        return self.process.run(command, cwd)

    def log(self, cwd: str, count: int = 10):
        return self.process.run(["git", "log", "--oneline", "-n", str(count)], cwd)

    def add(self, cwd: str, paths: list[str] | None = None):
        self._require_git_write()
        command = ["git", "add"]
        command.extend(paths if paths else ["-A"])
        return self.process.run(command, cwd)

    def checkout_branch(self, cwd: str, branch: str):
        self._require_git_write()
        return self.process.run(["git", "switch", branch], cwd)

    def restore(self, cwd: str, paths: list[str], source: str = "HEAD"):
        self._require_git_write()
        return self.process.run(["git", "restore", "--source", source, "--", *paths], cwd)

    def stash(self, cwd: str, action: str = "list", message: str | None = None):
        command = ["git", "stash"]
        if action == "list":
            command.append("list")
        else:
            self._require_git_write()
            command.append(action)
            if action == "push" and message:
                command.extend(["-m", message])
        return self.process.run(command, cwd)

    def commit(self, cwd: str, message: str, approved: bool = False):
        self._require_git_write()
        self._require_approval("git.commit", approved)
        added = self.process.run(["git", "add", "-A"], cwd)
        if added.returncode != 0:
            return added
        return self.process.run(["git", "commit", "-m", message], cwd)

    def push(self, cwd: str, remote: str = "origin", branch: str | None = None, approved: bool = False):
        self._require_git_write()
        self._require_approval("git.push", approved)
        command = ["git", "push", remote]
        if branch:
            command.append(branch)
        return self.process.run(command, cwd)

    def pull(self, cwd: str, remote: str = "origin", branch: str | None = None):
        self._require_git_write()
        command = ["git", "pull", remote]
        if branch:
            command.append(branch)
        return self.process.run(command, cwd)

    def _require_git_write(self):
        if not self.policy.permits("git.write"):
            raise PermissionError("Git write operations are disabled by policy")

    def _require_approval(self, action: str, approved: bool):
        if self.policy.requires_approval(action) and not approved:
            raise PermissionError(f"Explicit approval required for: {action}")

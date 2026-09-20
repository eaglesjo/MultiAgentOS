"""Policy-controlled local process runtime."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessRuntime:
    def __init__(self, policy: ExecutionPolicy | None = None) -> None:
        self.policy = policy or ExecutionPolicy()

    def run(self, command: list[str], cwd: str | None = None) -> ProcessResult:
        if not self.policy.permits("process"):
            raise PermissionError("Process execution is disabled by policy")
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
        return ProcessResult(result.returncode, result.stdout, result.stderr)

"""Subprocess executor with explicit execution policy."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.contracts.runtime import ExecutionRequest
from runtime.policy import ExecutionPolicy


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    command: tuple[str, ...]


class LocalProcessExecutor:
    """Execute an explicit argv command on the local machine."""

    def __init__(self, policy: ExecutionPolicy | None = None) -> None:
        self.policy = policy or ExecutionPolicy()

    def execute(self, request: ExecutionRequest) -> ProcessResult:
        if not self.policy.permits("process"):
            raise PermissionError("Local process execution is disabled by policy")

        command = request.work_unit.inputs.get("command")
        if not isinstance(command, (list, tuple)) or not command:
            raise ValueError("WorkUnit.inputs['command'] must be a non-empty argv list")
        if not all(isinstance(part, str) and part for part in command):
            raise ValueError("Every command argument must be a non-empty string")

        cwd_value = request.work_unit.inputs.get("cwd")
        cwd = Path(cwd_value).expanduser() if isinstance(cwd_value, str) else None
        timeout = request.work_unit.inputs.get("timeout", 300)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("WorkUnit.inputs['timeout'] must be a positive number")

        completed = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return ProcessResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            command=tuple(command),
        )

"""Persistent working-directory shell runtime."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field

from runtime.local.path_security import PathPolicy
from runtime.local.permissions import LocalPermissionGuard
from runtime.policy import ExecutionPolicy


@dataclass
class ShellState:
    cwd: str
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ShellResult:
    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str


class PersistentShellRuntime:
    """Shell execution with persistent cwd/environment state between calls."""

    def __init__(
        self,
        cwd: str,
        policy: ExecutionPolicy | None = None,
        paths: PathPolicy | None = None,
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.paths = paths or PathPolicy()
        self.permissions = LocalPermissionGuard(self.policy)
        initial = self.paths.resolve(cwd, must_exist=True)
        if not initial.is_dir():
            raise NotADirectoryError(str(initial))
        self.state = ShellState(str(initial))

    def status(self) -> ShellState:
        return ShellState(self.state.cwd, dict(self.state.environment))

    def reset(self, cwd: str) -> ShellState:
        self.permissions.require("process")
        target = self.paths.resolve(cwd, must_exist=True)
        if not target.is_dir():
            raise NotADirectoryError(str(target))
        self.state.cwd = str(target)
        return self.status()

    def set_environment(self, name: str, value: str) -> ShellState:
        self.permissions.require("process")
        if not name or "=" in name or "\x00" in name:
            raise ValueError("invalid environment variable name")
        self.state.environment[name] = value
        return self.status()

    def run(self, command: str, *, timeout: float = 120.0) -> ShellResult:
        self.permissions.require("process")
        if not command.strip():
            raise ValueError("command must not be empty")
        env = os.environ.copy()
        env.update(self.state.environment)
        completed = subprocess.run(
            command,
            cwd=self.state.cwd,
            env=env,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return ShellResult(
            command=command,
            cwd=self.state.cwd,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def cd(self, path: str) -> ShellState:
        self.permissions.require("process")
        target = self.paths.resolve(path, must_exist=True)
        if not target.is_dir():
            raise NotADirectoryError(str(target))
        self.state.cwd = str(target)
        return self.status()

    def command_words(self, command: str) -> tuple[str, ...]:
        return tuple(shlex.split(command))

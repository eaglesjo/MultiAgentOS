"""Policy- and path-controlled filesystem runtime."""

from __future__ import annotations

from pathlib import Path

from runtime.local.path_security import PathPolicy
from runtime.local.permissions import LocalPermissionGuard
from runtime.policy import ExecutionPolicy


class FilesystemRuntime:
    """First-class AGENT_EXECUTION_RUNTIME filesystem operations."""

    def __init__(
        self,
        policy: ExecutionPolicy | None = None,
        paths: PathPolicy | None = None,
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.paths = paths or PathPolicy()
        self.permissions = LocalPermissionGuard(self.policy)

    def read_text(self, path: str, *, encoding: str = "utf-8") -> str:
        target = self.paths.resolve(path, must_exist=True)
        if not target.is_file():
            raise IsADirectoryError(str(target))
        return target.read_text(encoding=encoding)

    def write_text(
        self, path: str, content: str, *, encoding: str = "utf-8", approved: bool = False
    ) -> Path:
        self.permissions.require("filesystem.write", approved=approved)
        target = self.paths.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
        return target

    def list_directory(self, path: str = ".") -> tuple[str, ...]:
        target = self.paths.resolve(path, must_exist=True)
        if not target.is_dir():
            raise NotADirectoryError(str(target))
        return tuple(sorted(item.name for item in target.iterdir()))

    def create_directory(self, path: str, *, approved: bool = False) -> Path:
        self.permissions.require("filesystem.write", approved=approved)
        target = self.paths.resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def delete(self, path: str, *, approved: bool = False) -> Path:
        self.permissions.require("filesystem.write", approved=approved)
        target = self.paths.resolve(path, must_exist=True)
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()
        return target

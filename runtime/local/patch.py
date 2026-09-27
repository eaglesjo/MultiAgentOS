"""Patch application runtime for VYRELON."""

from __future__ import annotations

import tempfile
from pathlib import Path

from runtime.local.path_security import PathPolicy
from runtime.local.permissions import LocalPermissionGuard
from runtime.policy import ExecutionPolicy
from runtime.process import ProcessResult, ProcessRuntime


class PatchRuntime:
    """Apply/check unified patches through the local Git patch engine."""

    def __init__(
        self,
        policy: ExecutionPolicy | None = None,
        paths: PathPolicy | None = None,
        process: ProcessRuntime | None = None,
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.paths = paths or PathPolicy()
        self.permissions = LocalPermissionGuard(self.policy)
        self.process = process or ProcessRuntime(self.policy)

    def _with_patch_file(self, patch_text: str, callback):
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".patch",
            delete=True,
        ) as patch_file:
            patch_file.write(patch_text)
            patch_file.flush()
            return callback(patch_file.name)

    def check(self, project_root: str, patch_text: str) -> ProcessResult:
        root = self.paths.resolve(project_root, must_exist=True)
        if not root.is_dir():
            raise NotADirectoryError(str(root))
        return self._with_patch_file(
            patch_text,
            lambda patch_path: self.process.run(
                ["git", "apply", "--check", patch_path],
                cwd=str(root),
            ),
        )

    def apply(
        self, project_root: str, patch_text: str, *, approved: bool = False
    ) -> ProcessResult:
        self.permissions.require("filesystem.write", approved=approved)
        checked = self.check(project_root, patch_text)
        if checked.returncode != 0:
            return checked
        root = self.paths.resolve(project_root, must_exist=True)
        return self._with_patch_file(
            patch_text,
            lambda patch_path: self.process.run(
                ["git", "apply", patch_path],
                cwd=str(root),
            ),
        )

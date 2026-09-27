"""Tests for the VYRELON local tool runtime."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from runtime.local.filesystem import FilesystemRuntime
from runtime.local.patch import PatchRuntime
from runtime.local.path_security import PathPolicy, PathSecurityError
from runtime.local.shell import PersistentShellRuntime
from runtime.policy import ExecutionPolicy


class LocalToolRuntimeTests(unittest.TestCase):
    def test_path_policy_confines_absolute_and_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = PathPolicy((str(root),))
            self.assertEqual(policy.resolve("nested/file.txt"), root / "nested" / "file.txt")
            with self.assertRaises(PathSecurityError):
                policy.resolve(str(root.parent / "outside.txt"))

    def test_filesystem_round_trip_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fs = FilesystemRuntime(
                policy=ExecutionPolicy(allow_filesystem_write=True),
                paths=PathPolicy((str(root),)),
            )
            fs.write_text("src/example.txt", "hello", approved=True)
            self.assertEqual(fs.read_text("src/example.txt"), "hello")
            self.assertIn("example.txt", fs.list_directory("src"))
            fs.delete("src/example.txt", approved=True)
            self.assertNotIn("example.txt", fs.list_directory("src"))

    def test_filesystem_write_is_policy_controlled(self):
        with tempfile.TemporaryDirectory() as tmp:
            fs = FilesystemRuntime(
                policy=ExecutionPolicy(allow_filesystem_write=False),
                paths=PathPolicy((tmp,)),
            )
            with self.assertRaises(PermissionError):
                fs.write_text("blocked.txt", "no")

    def test_shell_persists_cwd_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child"
            child.mkdir()
            shell = PersistentShellRuntime(str(root), paths=PathPolicy((str(root),)))
            shell.cd("child")
            shell.set_environment("VYRELON_TEST", "ok")
            result = shell.run(
                "python -c \"import os; print(os.getcwd()); print(os.getenv('VYRELON_TEST'))\""
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn(str(child), result.stdout)
            self.assertIn("ok", result.stdout)

    def test_patch_checks_and_applies_unified_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            target = root / "README.md"
            target.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test",
                 "commit", "-m", "initial"],
                cwd=root, check=True, capture_output=True,
            )
            patch = (
                "diff --git a/README.md b/README.md\n"
                "--- a/README.md\n"
                "+++ b/README.md\n"
                "@@ -1 +1 @@\n"
                "-before\n"
                "+after\n"
            )
            runtime = PatchRuntime(
                policy=ExecutionPolicy(allow_filesystem_write=True),
                paths=PathPolicy((str(root),)),
            )
            self.assertEqual(runtime.check(str(root), patch).returncode, 0)
            self.assertEqual(
                runtime.apply(str(root), patch, approved=True).returncode, 0
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "after\n")


if __name__ == "__main__":
    unittest.main()

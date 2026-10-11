import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import ToolRequest
from runtime.builtin_tools import BuiltinToolBindings
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolRuntime


class BuiltinToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.policy = ExecutionPolicy(
            allow_filesystem_write=True,
            require_approval_for=frozenset(),
        )
        self.tools = ToolRuntime(self.policy)
        BuiltinToolBindings(str(self.root), self.tools)

    def _read(self, path):
        return self.tools.execute(ToolRequest("filesystem.read", {"path": str(path)}))

    def _write(self, path, content="changed"):
        return self.tools.execute(
            ToolRequest(
                "filesystem.write",
                {"path": str(path), "content": content},
                metadata={"approved": True},
            ),
            granted_permissions=frozenset({"filesystem.write"}),
            approved=True,
        )

    def test_filesystem_read_write_and_patch_are_registered(self):
        target = self.root / "hello.py"
        target.write_text("value = 1\n", encoding="utf-8")
        read = self.tools.execute(ToolRequest("filesystem.read", {"path": "hello.py"}))
        self.assertTrue(read.ok)
        self.assertEqual(read.output, "value = 1\n")
        write = self.tools.execute(
            ToolRequest(
                "filesystem.write",
                {"path": "hello.py", "content": "value = 2\n"},
                metadata={"approved": True},
            ),
            granted_permissions=frozenset({"filesystem.write"}),
            approved=True,
        )
        self.assertTrue(write.ok)
        self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")

    def test_filesystem_read_rejects_parent_traversal(self):
        outside = self.root.parent / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        result = self._read("../outside.txt")
        self.assertFalse(result.ok)
        self.assertIn("outside allowed roots", result.error)

    def test_filesystem_read_rejects_absolute_path_outside_project(self):
        outside = self.root.parent / "absolute-secret.txt"
        outside.write_text("secret", encoding="utf-8")
        result = self._read(outside)
        self.assertFalse(result.ok)
        self.assertIn("outside allowed roots", result.error)

    def test_filesystem_write_rejects_parent_traversal(self):
        outside = self.root.parent / "outside-write.txt"
        outside.write_text("before", encoding="utf-8")
        result = self._write("../outside-write.txt", "after")
        self.assertFalse(result.ok)
        self.assertEqual(outside.read_text(encoding="utf-8"), "before")

    def test_filesystem_write_rejects_absolute_path_outside_project(self):
        outside = self.root.parent / "absolute-write.txt"
        outside.write_text("before", encoding="utf-8")
        result = self._write(outside, "after")
        self.assertFalse(result.ok)
        self.assertEqual(outside.read_text(encoding="utf-8"), "before")

    def test_filesystem_read_rejects_symlink_escape(self):
        outside = self.root.parent / "symlink-secret.txt"
        outside.write_text("secret", encoding="utf-8")
        link = self.root / "outside-link.txt"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable on this platform")
        result = self._read("outside-link.txt")
        self.assertFalse(result.ok)
        self.assertIn("outside allowed roots", result.error)

    def test_shell_tool_respects_process_policy(self):
        policy = ExecutionPolicy(allow_process=False)
        tools = ToolRuntime(policy)
        BuiltinToolBindings(str(self.root), tools)
        result = tools.execute(
            ToolRequest("shell.run", {"command": "printf ok"}),
            granted_permissions=frozenset({"process"}),
            approved=True,
        )
        self.assertFalse(result.ok)
        self.assertIn("disabled", result.error)


if __name__ == "__main__":
    unittest.main()

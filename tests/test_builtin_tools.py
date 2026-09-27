import tempfile
import unittest
from pathlib import Path
from core.contracts.vyrelon_runtime import ToolRequest
from runtime.builtin_tools import BuiltinToolBindings
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolRuntime

class BuiltinToolTests(unittest.TestCase):
    def test_filesystem_read_write_and_patch_are_registered(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,"hello.py").write_text("value = 1\n",encoding="utf-8")
            policy=ExecutionPolicy(allow_filesystem_write=True, require_approval_for=frozenset())
            tools=ToolRuntime(policy)
            BuiltinToolBindings(root,tools)
            read=tools.execute(ToolRequest("filesystem.read",{"path":"hello.py"}))
            self.assertTrue(read.ok)
            self.assertEqual(read.output,"value = 1\n")
            write=tools.execute(ToolRequest("filesystem.write",{"path":"hello.py","content":"value = 2\n"},metadata={"approved":True}),granted_permissions=frozenset({"filesystem.write"}),approved=True)
            self.assertTrue(write.ok)
            self.assertEqual(Path(root,"hello.py").read_text(), "value = 2\n")
    def test_shell_tool_respects_process_policy(self):
        with tempfile.TemporaryDirectory() as root:
            policy=ExecutionPolicy(allow_process=False)
            tools=ToolRuntime(policy)
            BuiltinToolBindings(root,tools)
            result=tools.execute(ToolRequest("shell.run",{"command":"printf ok"}),granted_permissions=frozenset({"process"}),approved=True)
            self.assertFalse(result.ok)
            self.assertIn("disabled",result.error)

if __name__=="__main__":
    unittest.main()

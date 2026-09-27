import tempfile
import unittest
from pathlib import Path
from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.work_unit import WorkUnit
from runtime.agent.model import ModelAgentExecutor
from runtime.agent.ide import IDECodingExecutor
from runtime.builtin_tools import BuiltinToolBindings
from runtime.tool_calling import ToolRuntime
from runtime.policy import ExecutionPolicy

class FakeToolModel:
    def __init__(self): self.calls=0
    def generate(self, model, request): return ModelResponse("unused",model.id)
    def generate_with_tools(self, model, request, tools):
        self.calls += 1
        if self.calls == 1:
            patch = """diff --git a/hello.py b/hello.py
--- a/hello.py
+++ b/hello.py
@@ -1 +1 @@
-value = 1
+value = 2
"""
            return ModelResponse("tool call",model.id,{"tool_calls":[{"id":"call-1","name":"patch.apply","arguments":{"patch":patch}}]})
        return ModelResponse("changed",model.id,{"tool_results_seen":request.metadata.get("tool_results")})

class IDEToolCallingTests(unittest.TestCase):
    def test_ide_code_change_uses_real_patch_tool(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,"hello.py").write_text("value = 1\n",encoding="utf-8")
            policy=ExecutionPolicy(allow_filesystem_write=True,require_approval_for=frozenset())
            tools=ToolRuntime(policy)
            BuiltinToolBindings(root,tools)
            model=ModelSpec("fake","fake")
            adapter=FakeToolModel()
            delegate=ModelAgentExecutor({"fake":adapter},[model])
            executor=IDECodingExecutor(delegate,Path(root),apply_changes=True,policy=policy,tool_runtime=tools)
            agent=AgentContract("coder","coder",permissions=frozenset({"filesystem.write"}),model_ids=("fake",))
            work=WorkUnit(id="w1",objective="change value")
            output=executor.execute(agent=agent,model_id="fake",work_unit=work)
            self.assertEqual(output.text,"changed")
            self.assertEqual(Path(root,"hello.py").read_text(), "value = 2\n")
            self.assertTrue(work.metadata["patch_applied"])
            self.assertEqual(work.metadata["tool_rounds"],2)
            self.assertEqual(adapter.calls,2)

if __name__=="__main__":
    unittest.main()

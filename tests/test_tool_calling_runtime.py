import unittest
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.agent_execution_runtime_runtime import ToolRequest, ToolSideEffect, ToolSpec
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolCallingRuntime, ToolRuntime

class FakeToolModel:
    def __init__(self): self.calls = 0
    def generate_with_tools(self, model, request, tools):
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(text="", model_id=model.id, metadata={"tool_calls":[{"id":"call-1","name":"echo","arguments":{"value":"hello"}}]})
        return ModelResponse(text=request.metadata["tool_results"][0]["output"], model_id=model.id)

class ToolCallingRuntimeTests(unittest.TestCase):
    def test_round_trip(self):
        adapter = FakeToolModel()
        model = ModelSpec("fake", "fake-provider")
        tools = ToolRuntime()
        tools.register(ToolSpec("echo", "echo"), lambda r: r.arguments["value"])
        runtime = ToolCallingRuntime(models={"fake":model}, adapters={"fake":adapter}, tools=tools)
        result = runtime.execute(ModelRequest(prompt="hello"), model_id="fake")
        self.assertEqual(result.response.text, "hello")
        self.assertEqual(result.rounds, 2)
        self.assertEqual(len(result.tool_results), 1)
    def test_policy_blocks_process_tool(self):
        tools = ToolRuntime(ExecutionPolicy(allow_process=False))
        tools.register(ToolSpec("run", "run", ToolSideEffect.EXECUTE), lambda r: "bad")
        result = tools.execute(ToolRequest("run", {"command":"true"}))
        self.assertFalse(result.ok)
        self.assertIn("disabled", result.error)
    def test_permission_blocks_tool(self):
        tools = ToolRuntime()
        tools.register(ToolSpec("write", "write", ToolSideEffect.WRITE, frozenset({"filesystem.write"})), lambda r: "bad")
        result = tools.execute(ToolRequest("write"))
        self.assertFalse(result.ok)
        self.assertIn("permission denied", result.error)

if __name__ == "__main__": unittest.main()

import os
import unittest
from unittest.mock import patch

from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest
from core.contracts.agent_execution_runtime_runtime import ToolSpec
from runtime.model.native import (
    AnthropicMessagesToolAdapter,
    GeminiGenerateContentToolAdapter,
    OpenAIResponsesToolAdapter,
)
from runtime.policy import ExecutionPolicy

class NativeProviderToolCallingTests(unittest.TestCase):
    def setUp(self):
        self.model = ModelSpec("test-model", "test")
        self.tool = ToolSpec("patch.apply", "Apply a unified diff", input_schema={
            "type": "object", "properties": {"patch": {"type": "string"}}, "required": ["patch"]
        })
        self.request = ModelRequest("change the file")
        self.env = patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key",
            "ANTHROPIC_API_KEY": "test-key",
            "GEMINI_API_KEY": "test-key",
        })

    def test_openai_normalizes_function_call_and_history(self):
        adapter = OpenAIResponsesToolAdapter(policy=ExecutionPolicy(allow_network=True))
        with self.env, patch("runtime.model.native._request", side_effect=[
            ({"output": [{"type": "function_call", "call_id": "c1", "name": "patch_apply", "arguments": '{"patch":"x"}'}]}, {}),
            ({"output": [{"type": "message", "content": [{"type": "output_text", "text": "done"}]}]}, {}),
        ]) as request:
            first = adapter.generate_with_tools(self.model, self.request, (self.tool,))
            second = adapter.generate_with_tools(self.model, ModelRequest("change the file", metadata={
                "tool_history": ({"tool_calls": ({"call_id": "c1", "tool_id": "patch.apply", "arguments": {"patch": "x"}},),
                                  "tool_results": ({"call_id": "c1", "tool_id": "patch.apply", "ok": True, "output": "applied"},)},)
            }), (self.tool,))
        self.assertEqual(first.metadata["tool_calls"][0]["name"], "patch.apply")
        self.assertEqual(second.text, "done")
        payload = request.call_args_list[1].args[1]
        self.assertEqual(payload["input"][-1]["type"], "function_call_output")

    def test_anthropic_uses_tool_use_and_tool_result_blocks(self):
        adapter = AnthropicMessagesToolAdapter(policy=ExecutionPolicy(allow_network=True))
        history = {"tool_calls": ({"call_id": "c1", "tool_id": "patch.apply", "arguments": {"patch": "x"}},),
                   "tool_results": ({"call_id": "c1", "tool_id": "patch.apply", "ok": True, "output": "applied"},)}
        with self.env, patch("runtime.model.native._request", return_value=({"content": [{"type": "text", "text": "done"}]}, {})) as request:
            response = adapter.generate_with_tools(self.model, ModelRequest("change", metadata={"tool_history": (history,)}), (self.tool,))
        self.assertEqual(response.text, "done")
        messages = request.call_args.args[1]["messages"]
        self.assertEqual(messages[-2]["role"], "assistant")
        self.assertEqual(messages[-1]["content"][0]["type"], "tool_result")

    def test_gemini_uses_function_call_and_function_response(self):
        adapter = GeminiGenerateContentToolAdapter(policy=ExecutionPolicy(allow_network=True))
        history = {"tool_calls": ({"call_id": "c1", "tool_id": "patch.apply", "arguments": {"patch": "x"}},),
                   "tool_results": ({"call_id": "c1", "tool_id": "patch.apply", "ok": True, "output": "applied"},)}
        with self.env, patch("runtime.model.native._request", return_value=({"candidates": [{"content": {"parts": [{"text": "done"}]}}]}, {})) as request:
            response = adapter.generate_with_tools(self.model, ModelRequest("change", metadata={"tool_history": (history,)}), (self.tool,))
        self.assertEqual(response.text, "done")
        contents = request.call_args.args[1]["contents"]
        self.assertEqual(contents[-2]["role"], "model")
        self.assertIn("functionResponse", contents[-1]["parts"][0])

if __name__ == "__main__":
    unittest.main()

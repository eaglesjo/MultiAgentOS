import unittest

from core.contracts.agent_execution_runtime import SessionSpec, ToolRequest
from runtime import AgentExecutionRuntime
from runtime.mcp.agent_execution_runtime_server import AgentExecutionRuntimeMCPServer


class AgentExecutionRuntimeAPITests(unittest.TestCase):
    def test_canonical_runtime_name_is_available(self):
        self.assertEqual(SessionSpec.__name__, "SessionSpec")

    def test_canonical_contracts_are_importable(self):
        request = ToolRequest(tool_id="filesystem.read")
        self.assertEqual(request.tool_id, "filesystem.read")

    def test_canonical_mcp_server_identifies_itself(self):
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            response = AgentExecutionRuntimeMCPServer(Path(temp)).handle({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            })
            self.assertEqual(
                response["result"]["serverInfo"]["name"],
                "Agent Execution Runtime",
            )


if __name__ == "__main__":
    unittest.main()

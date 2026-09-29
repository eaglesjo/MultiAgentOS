import unittest

from core.contracts.agent_execution_runtime import SessionSpec, ToolRequest
from core.contracts.vyrelon_runtime import SessionSpec as LegacySessionSpec
from runtime import AgentExecutionRuntime, VYRELONRuntime
from runtime.mcp.agent_execution_runtime_server import AgentExecutionRuntimeMCPServer
from runtime.mcp.server import VYRELONMCPServer


class AgentExecutionRuntimeAPITests(unittest.TestCase):
    def test_canonical_runtime_name_is_available(self):
        self.assertIs(AgentExecutionRuntime, VYRELONRuntime)
        self.assertEqual(SessionSpec.__name__, "SessionSpec")
        self.assertIs(LegacySessionSpec, SessionSpec)

    def test_canonical_contracts_are_importable(self):
        request = ToolRequest(tool_id="filesystem.read")
        self.assertEqual(request.tool_id, "filesystem.read")

    def test_canonical_mcp_server_name_is_available(self):
        self.assertTrue(issubclass(VYRELONMCPServer, AgentExecutionRuntimeMCPServer))

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

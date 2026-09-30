import json
import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import RuntimeEventKind
from runtime.mcp.server import AgentExecutionRuntimeMCPServer


class MCPDurableExecutionTests(unittest.TestCase):
    def test_mcp_tool_call_creates_durable_execution_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hello.txt").write_text("hello durable MCP\n", encoding="utf-8")

            server = AgentExecutionRuntimeMCPServer(root)

            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "filesystem.read",
                        "arguments": {"path": "hello.txt"},
                    },
                }
            )

            self.assertIsNotNone(response)
            self.assertFalse(response["result"]["isError"])

            durable = root / ".multiagentos"

            work_units = list((durable / "work-state").glob("*.json"))
            self.assertEqual(len(work_units), 1)

            work_unit = json.loads(work_units[0].read_text(encoding="utf-8"))
            work_unit_id = work_unit["id"]

            events = (durable / "events" / f"{work_unit_id}.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            event_kinds = [json.loads(line)["kind"] for line in events]

            self.assertIn(RuntimeEventKind.REQUEST.value, event_kinds)
            self.assertIn(RuntimeEventKind.TOOL_CALL.value, event_kinds)
            self.assertIn(RuntimeEventKind.TOOL_RESULT.value, event_kinds)
            self.assertIn(RuntimeEventKind.COMPLETED.value, event_kinds)

            ledger_path = durable / "tool-ledger" / f"{work_unit_id}.jsonl"
            ledger = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
            ]

            states = [item["state"] for item in ledger]
            self.assertIn("requested", states)
            self.assertIn("started", states)
            self.assertIn("completed", states)

            self.assertEqual(ledger[-1]["tool_id"], "filesystem.read")
            self.assertEqual(ledger[-1]["replay_policy"]["disposition"], "safe")
            self.assertTrue(ledger[-1]["idempotency_key"])
            self.assertEqual(work_unit["status"], "completed")
            self.assertTrue(
                all(
                    not item["requires_recovery_review"]
                    for item in ledger
                    if "requires_recovery_review" in item
                )
            )


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import RuntimeEventKind
from core.contracts.recovery import RecoveryDisposition
from core.contracts.recovery import RecoveryDisposition
from runtime.agent_execution_runtime import AgentExecutionRuntime
from runtime.mcp.durable_bridge import MCPDurableExecutionBridge
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

            work_units = list((durable / "state").glob("*.json"))
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

            decisions = [
                json.loads(line)
                for line in (durable / "decisions" / f"{work_unit_id}.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(decisions[-1]["category"], "capability")
            self.assertEqual(decisions[-1]["disposition"], "allow")
            self.assertEqual(decisions[-1]["action"], "filesystem.read")

            runtime = AgentExecutionRuntime()
            plan = runtime.recovery_plan(root, work_unit_id)
            self.assertEqual(plan.disposition, RecoveryDisposition.COMPLETED)


    def _truncate_to_crash_boundary(self, root: Path, work_unit_id: str) -> None:
        durable = root / ".multiagentos"
        state_path = durable / "state" / f"{work_unit_id}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["status"] = "executing"
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

        ledger_path = durable / "tool-ledger" / f"{work_unit_id}.jsonl"
        ledger_lines = ledger_path.read_text(encoding="utf-8").splitlines()
        ledger_path.write_text("\n".join(ledger_lines[:2]) + "\n", encoding="utf-8")

        event_path = durable / "events" / f"{work_unit_id}.jsonl"
        event_lines = event_path.read_text(encoding="utf-8").splitlines()
        event_path.write_text("\n".join(event_lines[:2]) + "\n", encoding="utf-8")

    def test_safe_mcp_invocation_resumes_from_started_crash_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hello.txt").write_text("recover me\n", encoding="utf-8")
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
            self.assertFalse(response["result"]["isError"])

            durable = root / ".multiagentos"
            work_unit_id = json.loads(next((durable / "state").glob("*.json")).read_text(encoding="utf-8"))["id"]
            ledger_before = [
                json.loads(line)
                for line in (durable / "tool-ledger" / f"{work_unit_id}.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            invocation_id = ledger_before[-1]["invocation_id"]
            idempotency_key = ledger_before[-1]["idempotency_key"]

            self._truncate_to_crash_boundary(root, work_unit_id)

            runtime = AgentExecutionRuntime()
            snapshot = runtime.inspect_work_unit(root, work_unit_id)
            self.assertEqual(snapshot["execution_state"], "tool_in_flight")
            plan = runtime.recovery_plan(root, work_unit_id)
            self.assertEqual(plan.disposition, RecoveryDisposition.RESUME)
            self.assertTrue(plan.safe_to_resume)
            self.assertEqual(plan.pending_tool_call_ids, (invocation_id,))

            bridge = server.durable_bridge
            recovered = bridge.recover(work_unit_id)
            self.assertTrue(recovered["replayed"])
            self.assertEqual(recovered["disposition"], RecoveryDisposition.COMPLETED.value)
            self.assertEqual(recovered["invocation_id"], invocation_id)
            self.assertEqual(recovered["idempotency_key"], idempotency_key)

            final_plan = runtime.recovery_plan(root, work_unit_id)
            self.assertEqual(final_plan.disposition, RecoveryDisposition.COMPLETED)
            final_ledger = [
                json.loads(line)
                for line in (durable / "tool-ledger" / f"{work_unit_id}.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(final_ledger[-1]["state"], "completed")
            self.assertEqual(final_ledger[-1]["invocation_id"], invocation_id)
            self.assertEqual(final_ledger[-1]["idempotency_key"], idempotency_key)

            decisions = [
                json.loads(line)
                for line in (durable / "decisions" / f"{work_unit_id}.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(any(item["category"] == "recovery" and item["disposition"] == "allow" for item in decisions))

    def test_side_effecting_mcp_invocation_requires_human_review_after_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = AgentExecutionRuntimeMCPServer(root, allow_write=True)

            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "filesystem.write",
                        "arguments": {"path": "side-effect.txt", "content": "initial\n"},
                    },
                }
            )
            self.assertFalse(response["result"]["isError"])
            self.assertEqual((root / "side-effect.txt").read_text(encoding="utf-8"), "initial\n")

            durable = root / ".multiagentos"
            work_unit_id = json.loads(next((durable / "state").glob("*.json")).read_text(encoding="utf-8"))["id"]
            self._truncate_to_crash_boundary(root, work_unit_id)

            runtime = AgentExecutionRuntime()
            plan = runtime.recovery_plan(root, work_unit_id)
            self.assertEqual(plan.disposition, RecoveryDisposition.REVIEW_REQUIRED)
            self.assertTrue(plan.requires_human_review)

            recovered = server.durable_bridge.recover(work_unit_id)
            self.assertFalse(recovered["replayed"])
            self.assertEqual(recovered["disposition"], RecoveryDisposition.REVIEW_REQUIRED.value)
            self.assertEqual((root / "side-effect.txt").read_text(encoding="utf-8"), "initial\n")

            ledger = [
                json.loads(line)
                for line in (durable / "tool-ledger" / f"{work_unit_id}.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(ledger[-1]["state"], "started")

            decisions = [
                json.loads(line)
                for line in (durable / "decisions" / f"{work_unit_id}.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(any(item["category"] == "recovery" and item["disposition"] == "review_required" for item in decisions))


if __name__ == "__main__":
    unittest.main()

import unittest

from core.contracts.idempotency import IdempotencyContract, IdempotencyMode
from core.security import redact_sensitive
from core.execution_state import ExecutionStateStore
from core.state import RuntimeEventStore
from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState
from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.tool_ledger import ToolInvocationStore
from pathlib import Path
import tempfile


class RuntimeSecurityBoundaryTests(unittest.TestCase):
    def test_sensitive_keys_are_redacted(self):
        payload = {
            "api_key": "super-secret",
            "nested": {"password": "hunter2"},
            "safe": "ordinary value",
        }
        result = redact_sensitive(payload)
        self.assertEqual(result["api_key"], "[REDACTED]")
        self.assertEqual(result["nested"]["password"], "[REDACTED]")
        self.assertEqual(result["safe"], "ordinary value")

    def test_known_token_patterns_are_redacted(self):
        value = "Bearer abcdefghijklmnop and sk-abcdefghijklmnop"
        result = redact_sensitive(value)
        self.assertNotIn("abcdefghijklmnop", result)
        self.assertEqual(result.count("[REDACTED]"), 2)

    def test_keyed_idempotency_requires_key(self):
        self.assertTrue(IdempotencyContract(IdempotencyMode.KEYED, "work-1:call-1").replay_safe)
        with self.assertRaises(ValueError):
            IdempotencyContract(IdempotencyMode.KEYED)

    def test_none_idempotency_is_not_replay_safe(self):
        self.assertFalse(IdempotencyContract(IdempotencyMode.NONE).replay_safe)

    def test_durable_stores_redact_sensitive_values(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            events = RuntimeEventStore(base / "events")
            events.append(RuntimeEvent(
                kind=RuntimeEventKind.TOOL_RESULT,
                work_unit_id="work-1",
                payload={"output": {"api_key": "secret-value"}},
                metadata={"authorization": "Bearer abcdefghijklmnop"},
            ))
            event = events.load("work-1")[0]
            self.assertEqual(event["payload"]["output"]["api_key"], "[REDACTED]")
            self.assertEqual(event["metadata"]["authorization"], "[REDACTED]")

            ledger = ToolInvocationStore(base / "ledger")
            ledger.append(ToolInvocationRecord(
                invocation_id="inv-1",
                work_unit_id="work-1",
                tool_id="filesystem.read",
                arguments={"token": "secret-value"},
                state=ToolInvocationState.COMPLETED,
                replay_policy=ReplayPolicy(ReplayDisposition.SAFE),
                sequence=1,
                error="Bearer abcdefghijklmnop",
            ))
            record = ledger.load("work-1")[0]
            self.assertEqual(record.arguments["token"], "[REDACTED]")
            self.assertEqual(record.error, "[REDACTED]")

            messages = ExecutionStateStore(base / "execution")
            messages.append_message(
                "work-1",
                role="tool",
                round_number=1,
                content={"password": "secret-value"},
                metadata={"api_key": "secret-value"},
            )
            message = messages.load_messages("work-1")[0]
            self.assertEqual(message["content"]["password"], "[REDACTED]")
            self.assertEqual(message["metadata"]["api_key"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()

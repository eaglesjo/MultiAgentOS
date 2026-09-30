import tempfile
import unittest
from pathlib import Path

from runtime.harness import ExecutionHarness
from core.contracts.memory import MemoryKind


class ExecutionHarnessTests(unittest.TestCase):
    def test_create_builds_project_scoped_durable_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            harness = ExecutionHarness.create(root)
            self.assertEqual(harness.project_root, root.resolve())
            self.assertIn("filesystem.read", {item.id for item in harness.tool_runtime.specs()})
            self.assertNotIn("patch.apply", {item.id for item in harness.tool_runtime.specs()})
            self.assertTrue(harness.event_store.root.exists())
            self.assertTrue(harness.ledger_store.root.exists())
            self.assertTrue(harness.execution_state_store.root.exists())
            self.assertTrue(harness.recovery_audit_store.root.exists())

    def test_apply_changes_controls_patch_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            harness = ExecutionHarness.create(root, apply_changes=True)
            self.assertIn("patch.apply", {item.id for item in harness.tool_runtime.specs()})

    def test_event_sink_targets_durable_event_store(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            harness = ExecutionHarness.create(root)
            self.assertIs(harness.event_sink().__self__, harness.event_store)


    def test_memory_is_project_scoped_and_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            harness = ExecutionHarness.create(Path(temp))
            memory = harness.remember(
                "Use the durable runtime for project execution",
                kind=MemoryKind.DECISION,
                metadata={"api_key": "secret-value"},
            )
            recalled = harness.recall("durable runtime")
            self.assertEqual(recalled[0].memory_id, memory.memory_id)
            self.assertEqual(recalled[0].metadata["api_key"], "[REDACTED]")
            self.assertTrue(harness.memory_store.root.exists())
            self.assertNotEqual(harness.memory_store.root, harness.event_store.root)
if __name__ == "__main__":
    unittest.main()

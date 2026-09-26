"""Tests for the provider-neutral VYRELON runtime contracts."""

import unittest

from core.contracts.vyrelon_runtime import (
    FallbackPolicy,
    HarnessSpec,
    RuntimeEvent,
    RuntimeEventKind,
    SessionSpec,
    ToolRequest,
    ToolResult,
    ToolSideEffect,
    ToolSpec,
)


class VyrelonRuntimeContractsTests(unittest.TestCase):
    def test_harness_and_session_are_independent_of_models(self):
        harness = HarnessSpec(id="codex", kind="coding-harness")
        session = SessionSpec(
            id="session-1",
            project_root="/workspace",
            harness_id=harness.id,
        )

        self.assertEqual(session.harness_id, "codex")
        self.assertIsNone(session.model_id)

    def test_tool_contract_carries_side_effect_and_permissions(self):
        tool = ToolSpec(
            id="filesystem.write",
            description="Write a file",
            side_effect=ToolSideEffect.WRITE,
            permissions=frozenset({"filesystem.write"}),
        )
        request = ToolRequest(
            tool_id=tool.id,
            arguments={"path": "README.md", "content": "ok"},
        )

        self.assertEqual(tool.side_effect, ToolSideEffect.WRITE)
        self.assertIn("filesystem.write", tool.permissions)
        self.assertEqual(request.tool_id, tool.id)

    def test_tool_result_can_represent_failure_without_exception(self):
        result = ToolResult(
            tool_id="shell.run",
            ok=False,
            error="permission denied",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "permission denied")

    def test_runtime_events_are_typed(self):
        event = RuntimeEvent(
            kind=RuntimeEventKind.TOOL_CALL,
            session_id="session-1",
            payload={"tool_id": "git.status"},
            sequence=3,
        )

        self.assertEqual(event.kind, RuntimeEventKind.TOOL_CALL)
        self.assertEqual(event.sequence, 3)

    def test_fallback_policy_is_ordered_and_bounded(self):
        policy = FallbackPolicy(
            model_ids=("a", "b", "c"),
            max_attempts=2,
        )

        self.assertEqual(policy.candidates(), ("a", "b"))


if __name__ == "__main__":
    unittest.main()

import unittest

from core.contracts.execution_cursor import ExecutionCursor
from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState


class DurableRuntimeContractsTests(unittest.TestCase):
    def test_replay_policy_distinguishes_safe_review_and_never(self):
        self.assertTrue(ReplayPolicy(ReplayDisposition.SAFE).replayable)
        self.assertTrue(
            ReplayPolicy(ReplayDisposition.REVIEW_REQUIRED).requires_human_review
        )
        self.assertFalse(ReplayPolicy(ReplayDisposition.NEVER).replayable)

    def test_tool_invocation_requires_review_when_unresolved_and_policy_requires_it(self):
        record = ToolInvocationRecord(
            invocation_id="call-1",
            work_unit_id="work-1",
            tool_id="shell.run",
            arguments={"command": ["git", "commit"]},
            state=ToolInvocationState.STARTED,
            replay_policy=ReplayPolicy(
                ReplayDisposition.REVIEW_REQUIRED,
                reason="external side effect may already have occurred",
            ),
            sequence=4,
        )
        self.assertTrue(record.requires_recovery_review)

    def test_completed_tool_invocation_does_not_require_recovery_review(self):
        record = ToolInvocationRecord(
            invocation_id="call-1",
            work_unit_id="work-1",
            tool_id="filesystem.read",
            arguments={"path": "README.md"},
            state=ToolInvocationState.COMPLETED,
            replay_policy=ReplayPolicy(ReplayDisposition.SAFE),
            sequence=4,
        )
        self.assertFalse(record.requires_recovery_review)

    def test_cursor_requires_forward_event_sequence(self):
        previous = ExecutionCursor("work-1", 4, 2, "developer", "model-a")
        current = ExecutionCursor("work-1", 5, 3, "developer", "model-a")
        self.assertTrue(current.advances_from(previous))
        self.assertFalse(previous.advances_from(current))

    def test_cursor_rejects_different_work_unit(self):
        previous = ExecutionCursor("work-1", 4, 2, "developer")
        current = ExecutionCursor("work-2", 5, 3, "developer")
        self.assertFalse(current.advances_from(previous))


if __name__ == "__main__":
    unittest.main()

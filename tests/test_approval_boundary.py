import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.approval import ApprovalStore
from core.contracts.approval import ApprovalDecision, ApprovalGrant
from core.contracts.agent_execution_runtime import ToolRequest, ToolSideEffect, ToolSpec
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolRuntime


class ApprovalBoundaryTests(unittest.TestCase):
    def test_approval_is_action_scoped_and_expiring(self):
        now = datetime.now(timezone.utc)
        grant = ApprovalGrant(
            approval_id="a-1",
            decision=ApprovalDecision.APPROVED,
            action="git.commit",
            work_unit_id="wu-1",
            session_id="s-1",
            expires_at=(now + timedelta(minutes=5)).isoformat(),
        )
        self.assertTrue(grant.is_valid(action="git.commit", work_unit_id="wu-1", session_id="s-1", now=now))
        self.assertFalse(grant.is_valid(action="git.push", work_unit_id="wu-1", session_id="s-1", now=now))
        self.assertFalse(grant.is_valid(action="git.commit", work_unit_id="wu-2", session_id="s-1", now=now))
        self.assertFalse(grant.is_valid(action="git.commit", work_unit_id="wu-1", session_id="s-1", now=now + timedelta(minutes=6)))

    def test_missing_approval_blocks_side_effect_before_handler(self):
        calls = []
        runtime = ToolRuntime(ExecutionPolicy(allow_git_write=True))
        runtime.register(ToolSpec("git.commit", "commit", ToolSideEffect.WRITE, frozenset({"git.write"})), lambda request: calls.append(request) or "ok")
        result = runtime.execute(
            ToolRequest("git.commit", {"message": "x"}, work_unit_id="wu-1", session_id="s-1"),
            granted_permissions=frozenset({"git.write"}),
        )
        self.assertFalse(result.ok)
        self.assertIn("explicit approval required", result.error)
        self.assertEqual(calls, [])

    def test_unscoped_approved_boolean_does_not_bypass_required_approval(self):
        calls = []
        runtime = ToolRuntime(ExecutionPolicy(allow_git_write=True))
        runtime.register(ToolSpec("git.commit", "commit", ToolSideEffect.WRITE, frozenset({"git.write"})), lambda request: calls.append(request) or "ok")
        result = runtime.execute(
            ToolRequest("git.commit", {"message": "x"}, work_unit_id="wu-1", session_id="s-1"),
            granted_permissions=frozenset({"git.write"}),
            approved=True,
        )
        self.assertFalse(result.ok)
        self.assertIn("explicit approval required", result.error)
        self.assertEqual(calls, [])

    def test_valid_scoped_approval_reaches_handler(self):
        calls = []
        runtime = ToolRuntime(ExecutionPolicy(allow_git_write=True))
        runtime.register(ToolSpec("git.commit", "commit", ToolSideEffect.WRITE, frozenset({"git.write"})), lambda request: calls.append(request) or "ok")
        grant = ApprovalGrant(
            approval_id="a-2",
            decision=ApprovalDecision.APPROVED,
            action="git.commit",
            work_unit_id="wu-1",
            session_id="s-1",
        )
        result = runtime.execute(
            ToolRequest("git.commit", {"message": "x"}, work_unit_id="wu-1", session_id="s-1"),
            granted_permissions=frozenset({"git.write"}),
            approval=grant,
        )
        self.assertTrue(result.ok)
        self.assertEqual(len(calls), 1)

    def test_approval_store_redacts_sensitive_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ApprovalStore(Path(temp))
            grant = ApprovalGrant(
                approval_id="a-3",
                decision=ApprovalDecision.APPROVED,
                action="git.commit",
                reason="approved for task",
            )
            path = store.save(grant, metadata={"api_key": "secret-value"})
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("secret-value", raw)
            self.assertIn("[REDACTED]", raw)
            self.assertEqual(store.load("a-3"), grant)


if __name__ == "__main__":
    unittest.main()

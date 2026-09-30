import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.contracts.recovery import RecoveryDecision, RecoveryDisposition
from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.agent_execution_runtime import AgentExecutionRuntime


class RecoveryAuthorizationContractTests(unittest.TestCase):
    def _pending(self, runtime, root, work_unit_id):
        runtime.state_store(root).save(WorkUnit(work_unit_id, "recover", WorkStatus.EXECUTING))
        runtime.event_store(root).append(RuntimeEvent(
            kind=RuntimeEventKind.TOOL_CALL,
            work_unit_id=work_unit_id,
            payload={"call_id": "call-1", "tool_id": "filesystem.write"},
        ))
        runtime.tool_ledger_store(root).append(ToolInvocationRecord(
            invocation_id="inv-1",
            work_unit_id=work_unit_id,
            tool_id="filesystem.write",
            arguments={"path": "target.txt", "content": "after"},
            state=ToolInvocationState.STARTED,
            replay_policy=ReplayPolicy(
                ReplayDisposition.REVIEW_REQUIRED,
                reason="side effect may have happened",
            ),
            sequence=1,
            call_id="call-1",
            idempotency_key="inv-1",
        ))

    def test_approval_is_durable_but_does_not_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime()
            self._pending(runtime, root, "review-approve")

            auth = runtime.resolve_recovery_review(
                root,
                "review-approve",
                decision=RecoveryDecision.APPROVE,
                notes="verified boundary",
                session_id="session-1",
            )

            self.assertTrue(auth.authorized)
            self.assertEqual(auth.decision, RecoveryDecision.APPROVE)
            self.assertEqual(
                runtime.recovery_plan(root, "review-approve").disposition,
                RecoveryDisposition.REVIEW_REQUIRED,
            )
            self.assertEqual(
                len(runtime.tool_ledger_store(root).unresolved("review-approve")),
                1,
            )
            decisions = runtime.policy_decision_store(root).load("review-approve")
            self.assertTrue(any(
                item.category.value == "recovery"
                and item.disposition.value == "allow"
                and item.metadata.get("human_decision") == "approve"
                for item in decisions
            ))

    def test_rejection_is_terminal_and_durable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime()
            self._pending(runtime, root, "review-reject")

            auth = runtime.resolve_recovery_review(
                root,
                "review-reject",
                decision=RecoveryDecision.REJECT,
                notes="do not replay",
            )

            self.assertFalse(auth.authorized)
            self.assertEqual(
                runtime.state_store(root).load("review-reject").status,
                WorkStatus.FAILED,
            )
            self.assertEqual(
                len(runtime.tool_ledger_store(root).unresolved("review-reject")),
                1,
            )
            decisions = runtime.policy_decision_store(root).load("review-reject")
            self.assertTrue(any(
                item.category.value == "recovery"
                and item.disposition.value == "deny"
                and item.metadata.get("human_decision") == "reject"
                for item in decisions
            ))

    def test_invalid_recovery_decision_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime()
            self._pending(runtime, root, "review-invalid")

            with self.assertRaises(ValueError):
                runtime.resolve_recovery_review(
                    root,
                    "review-invalid",
                    decision="maybe",
                )


if __name__ == "__main__":
    unittest.main()

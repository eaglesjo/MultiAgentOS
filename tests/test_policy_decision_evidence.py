import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import ToolRequest, ToolSideEffect, ToolSpec
from core.contracts.execution_limits import ExecutionBudget, LimitDisposition
from core.contracts.policy_decision import DecisionCategory, DecisionDisposition, PolicyDecision
from core.policy_decision import PolicyDecisionStore
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolRuntime


class PolicyDecisionEvidenceTests(unittest.TestCase):
    def test_store_redacts_sensitive_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            store = PolicyDecisionStore(Path(temp))
            store.append(PolicyDecision(
                work_unit_id="wu",
                category=DecisionCategory.APPROVAL,
                disposition=DecisionDisposition.DENY,
                reason="approval missing",
                action="github.merge",
                metadata={"api_key": "secret-value"},
            ))
            data = store.load("wu")
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["metadata"]["api_key"], "[REDACTED]")

    def test_tool_permission_denial_is_durable_policy_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            store = PolicyDecisionStore(Path(temp))
            runtime = ToolRuntime(
                ExecutionPolicy(),
                decision_store=store,
            )
            runtime.register(ToolSpec(
                id="write.tool",
                description="write",
                side_effect=ToolSideEffect.WRITE,
                permissions=frozenset({"write"}),
            ), lambda request: "side-effect")
            result = runtime.execute(ToolRequest("write.tool", work_unit_id="wu"), granted_permissions=frozenset())
            self.assertFalse(result.ok)
            decisions = store.load("wu")
            self.assertEqual(decisions[-1]["category"], DecisionCategory.PERMISSION.value)
            self.assertEqual(decisions[-1]["disposition"], DecisionDisposition.DENY.value)

    def test_approval_allow_is_distinguished_from_tool_result(self):
        with tempfile.TemporaryDirectory() as temp:
            store = PolicyDecisionStore(Path(temp))
            policy = ExecutionPolicy(require_approval_for=frozenset({"read.tool"}))
            runtime = ToolRuntime(policy, decision_store=store)
            runtime.register(ToolSpec(id="read.tool", description="read"), lambda request: "ok")
            result = runtime.execute(ToolRequest("read.tool", work_unit_id="wu"), approved=True)
            self.assertTrue(result.ok)
            decisions = store.load("wu")
            self.assertEqual(decisions[-1]["category"], DecisionCategory.APPROVAL.value)
            self.assertEqual(decisions[-1]["disposition"], DecisionDisposition.ALLOW.value)

    def test_execution_budget_decision_contract_is_typed(self):
        budget = ExecutionBudget(max_tool_calls=0)
        self.assertEqual(budget.max_tool_calls, 0)
        self.assertEqual(LimitDisposition.DENY.value, "deny")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from core.contracts.execution_limits import ExecutionBudget, LimitDisposition, RateLimit
from core.execution_limits import ExecutionLimitStore


class ExecutionLimitTests(unittest.TestCase):
    def test_tool_budget_blocks_after_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ExecutionLimitStore(Path(temp))
            budget = ExecutionBudget(max_tool_calls=2)
            first = store.check_tool_call("wu", budget=budget)
            self.assertEqual(first.disposition, LimitDisposition.ALLOW)
            store.record_tool_call("wu")
            store.record_tool_call("wu")
            blocked = store.check_tool_call("wu", budget=budget)
            self.assertEqual(blocked.disposition, LimitDisposition.DENY)
            self.assertEqual(blocked.reason, "tool call budget exhausted")

    def test_rate_limit_is_work_unit_scoped_and_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ExecutionLimitStore(Path(temp))
            limit = RateLimit(max_calls=1, window_seconds=60)
            self.assertEqual(store.check_tool_call("wu-a", budget=ExecutionBudget(), rate_limit=limit, now=120).disposition, LimitDisposition.ALLOW)
            store.record_tool_call("wu-a", rate_limit=limit, now=120)
            self.assertEqual(store.check_tool_call("wu-a", budget=ExecutionBudget(), rate_limit=limit, now=121).disposition, LimitDisposition.DENY)
            self.assertEqual(store.check_tool_call("wu-b", budget=ExecutionBudget(), rate_limit=limit, now=121).disposition, LimitDisposition.ALLOW)

    def test_round_budget_is_separate_from_tool_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ExecutionLimitStore(Path(temp))
            budget = ExecutionBudget(max_rounds=1, max_tool_calls=3)
            self.assertEqual(store.check_round("wu", budget=budget).disposition, LimitDisposition.ALLOW)
            store.record_round("wu")
            self.assertEqual(store.check_round("wu", budget=budget).disposition, LimitDisposition.DENY)


if __name__ == "__main__":
    unittest.main()

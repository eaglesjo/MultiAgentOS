import unittest

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.multi_agent_workflow import MultiAgentWorkflow


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, *, agent, model_id, work_unit):
        self.calls.append((agent.id, model_id))
        return {"agent": agent.id}


class MultiAgentWorkflowTests(unittest.TestCase):
    def test_agents_execute_in_order_and_create_handoffs(self):
        executor = FakeExecutor()
        agents = [
            AgentContract(id="planner", role="planner"),
            AgentContract(id="developer", role="developer"),
            AgentContract(id="tester", role="tester"),
        ]
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-1", "build feature")

        result = MultiAgentWorkflow().run(
            work_unit=work_unit,
            stages=agents,
            models=models,
            executor=executor,
        )

        self.assertEqual(work_unit.status, WorkStatus.COMPLETED)
        self.assertEqual(
            executor.calls,
            [("planner", "local"), ("developer", "local"), ("tester", "local")],
        )
        self.assertEqual(len(result.stages), 3)
        self.assertEqual(
            [(h.from_agent, h.to_agent) for h in result.stages[1:] if h.handoff],
            [("planner", "developer"), ("developer", "tester")],
        )
        self.assertEqual(work_unit.metadata["execution_agent_ids"], ["planner", "developer", "tester"])

    def test_review_panel_requires_all_reviewers(self):
        executor = FakeExecutor()
        agents = [AgentContract(id="developer", role="developer")]
        reviewers = [
            (AgentContract(id="reviewer-a", role="reviewer"), {}),
            (AgentContract(id="reviewer-b", role="reviewer"), {}),
        ]
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-2", "review feature")

        def reviewer_runner(*, review_work_unit_id, reviewer, context):
            from core.contracts.execution import ReviewDecision
            return ReviewDecision(approved=True, feedback=reviewer.id)

        result = MultiAgentWorkflow().run(
            work_unit=work_unit,
            stages=agents,
            models=models,
            executor=executor,
            reviewers=reviewers,
            reviewer_runner=reviewer_runner,
        )

        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
        self.assertEqual(len(result.reviews), 2)
        self.assertEqual(work_unit.metadata["review_consensus"], "approved")


if __name__ == "__main__":
    unittest.main()

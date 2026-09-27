import tempfile
import unittest
from pathlib import Path

from core.contracts import AgentContract, ModelSpec, WorkStatus, WorkUnit
from core.contracts.planning import PlanStep
from runtime.multi_agent import MultiAgentRuntime


class RecordingExecutor:
    def __init__(self, name):
        self.name = name
        self.calls = []

    def execute(self, *, agent, model_id, work_unit):
        self.calls.append((agent.id, model_id, work_unit.id))
        return {"agent": agent.id, "objective": work_unit.objective}


class MultiAgentRuntimeTests(unittest.TestCase):
    def test_planner_delegates_stages_and_handoffs(self):
        planner = AgentContract("planner", "planner", frozenset({"planning"}))
        coder = AgentContract("coder", "coder", frozenset({"code"}))
        reviewer = AgentContract("reviewer", "reviewer", frozenset({"review"}))
        models = [
            ModelSpec("planning-model", "local", frozenset({"planning"})),
            ModelSpec("code-model", "local", frozenset({"code"})),
            ModelSpec("review-model", "local", frozenset({"review"})),
        ]
        # The planner role is represented as the first executable stage; the
        # actual plan is still generated deterministically by BasicPlanner.
        plan_executor = RecordingExecutor("planner")
        code_executor = RecordingExecutor("coder")
        review_executor = RecordingExecutor("reviewer")
        with tempfile.TemporaryDirectory() as tmp:
            result = MultiAgentRuntime().run(
                Path(tmp),
                WorkUnit("wu-ma", "ship feature"),
                [
                    PlanStep("plan", "prepare implementation", "planner"),
                    PlanStep("code", "implement feature", "coder", ("plan",)),
                    PlanStep("review", "review implementation", "reviewer", ("code",)),
                ],
                {"planner": planner, "coder": coder, "reviewer": reviewer},
                models,
                {"planner": plan_executor, "coder": code_executor, "reviewer": review_executor},
                preferred_model_ids={
                    "planner": ["planning-model"],
                    "coder": ["code-model"],
                    "reviewer": ["review-model"],
                },
            )
        self.assertTrue(result.completed)
        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
        self.assertEqual(len(result.stages), 3)
        self.assertEqual(len(result.handoffs), 2)
        self.assertEqual(result.work_unit.metadata["plan_steps"], ["plan", "code", "review"])
        self.assertEqual(code_executor.calls[0][0], "coder")

    def test_missing_dependency_fails_without_running_dependent_stage(self):
        coder = AgentContract("coder", "coder")
        model = ModelSpec("code", "local")
        executor = RecordingExecutor("coder")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                MultiAgentRuntime().run(
                    Path(tmp),
                    WorkUnit("wu-dep", "feature"),
                    [PlanStep("code", "implement", "coder", ("missing",))],
                    {"coder": coder},
                    [model],
                    {"coder": executor},
                )
        self.assertEqual(executor.calls, [])


if __name__ == "__main__":
    unittest.main()

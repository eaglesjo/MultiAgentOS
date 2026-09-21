import tempfile
import unittest
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import ReviewDecision
from core.contracts.human_review import HumanReviewDecision
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.vyrelon import VYRELONRuntime


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, *, agent, model_id, work_unit):
        self.calls.append(agent.id)
        return {"agent": agent.id}


class HumanReviewPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.runtime = VYRELONRuntime()
        self.developer = AgentContract(id="developer", role="developer")
        self.tester = AgentContract(id="tester", role="tester")
        self.reviewer = [(AgentContract(id="reviewer", role="reviewer"), {})]
        self.models = [ModelSpec("local", "local", frozenset())]

    def test_waiting_gate_is_saved_and_can_be_resolved_from_fresh_runtime(self):
        work_unit = WorkUnit("wu-persisted-gate", "persist human gate")

        def reject(*, review_work_unit_id, reviewer, context):
            return ReviewDecision(approved=False, feedback="human decision required")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.runtime.run_review_rework_workflow(
                work_unit=work_unit,
                developer=self.developer,
                tester=self.tester,
                reviewers=self.reviewer,
                models=self.models,
                executor=FakeExecutor(),
                reviewer_runner=reject,
                max_review_cycles=1,
                project_root=root,
            )
            self.assertEqual(result.work_unit.status, WorkStatus.WAITING_HUMAN_APPROVAL)

            fresh = VYRELONRuntime()
            loaded = fresh.state_store(root).load("wu-persisted-gate")
            self.assertEqual(loaded.status, WorkStatus.WAITING_HUMAN_APPROVAL)
            self.assertTrue(loaded.metadata["human_review_required"])
            self.assertEqual(loaded.metadata["resume_context"]["workflow"], "review_rework")
            self.assertEqual(loaded.metadata["resume_context"]["developer_id"], "developer")
            self.assertEqual(loaded.metadata["resume_context"]["reviewer_ids"], ["reviewer"])

            resolved = fresh.resolve_persisted_human_review(
                "wu-persisted-gate",
                decision=HumanReviewDecision.APPROVE_COMPLETION,
                notes="Human approved the retained evidence.",
                project_root=root,
            )
            self.assertEqual(resolved.work_unit.status, WorkStatus.COMPLETED)

            persisted = fresh.state_store(root).load("wu-persisted-gate")
            self.assertEqual(
                persisted.metadata["human_review_decision"],
                HumanReviewDecision.APPROVE_COMPLETION.value,
            )
            self.assertFalse(persisted.metadata["human_review_required"])

    def test_human_can_authorize_a_fresh_bounded_rework_cycle(self):
        work_unit = WorkUnit("wu-human-rework", "resume after human authorization")
        calls = []

        def reviewer_runner(*, review_work_unit_id, reviewer, context):
            calls.append(context["review_cycle"])
            approved = len(calls) == 2
            return ReviewDecision(
                approved=approved,
                feedback="" if approved else "authorize rework",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.runtime.run_review_rework_workflow(
                work_unit=work_unit,
                developer=self.developer,
                tester=self.tester,
                reviewers=self.reviewer,
                models=self.models,
                executor=FakeExecutor(),
                reviewer_runner=reviewer_runner,
                max_review_cycles=1,
                project_root=root,
            )
            self.assertEqual(first.work_unit.status, WorkStatus.WAITING_HUMAN_APPROVAL)

            resumed = self.runtime.resume_human_review_rework(
                "wu-human-rework",
                developer=self.developer,
                tester=self.tester,
                reviewers=self.reviewer,
                models=self.models,
                executor=FakeExecutor(),
                reviewer_runner=reviewer_runner,
                max_review_cycles=1,
                project_root=root,
                notes="Human authorizes one additional bounded rework cycle.",
            )
            self.assertEqual(resumed.work_unit.status, WorkStatus.COMPLETED)
            self.assertEqual(calls, [1, 1])

            persisted = self.runtime.state_store(root).load("wu-human-rework")
            self.assertEqual(persisted.status, WorkStatus.COMPLETED)
            self.assertEqual(
                persisted.metadata["human_review_decision"],
                HumanReviewDecision.APPROVE_REWORK.value,
            )

    def test_rework_decision_cannot_be_silently_completed(self):
        work_unit = WorkUnit(
            "wu-decision-contract",
            "decision contract",
            status=WorkStatus.WAITING_HUMAN_APPROVAL,
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.runtime.resolve_human_review(
                    work_unit=work_unit,
                    decision=HumanReviewDecision.APPROVE_REWORK,
                    project_root=Path(directory),
                )

    def test_resume_rejects_mismatched_agent_context(self):
        work_unit = WorkUnit("wu-context-mismatch", "reject mismatched resume")
        def reject(*, review_work_unit_id, reviewer, context):
            return ReviewDecision(approved=False, feedback="needs human")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.runtime.run_review_rework_workflow(
                work_unit=work_unit,
                developer=self.developer,
                tester=self.tester,
                reviewers=self.reviewer,
                models=self.models,
                executor=FakeExecutor(),
                reviewer_runner=reject,
                max_review_cycles=1,
                project_root=root,
            )
            with self.assertRaises(ValueError):
                self.runtime.resume_human_review_rework(
                    "wu-context-mismatch",
                    developer=AgentContract(id="different-developer", role="developer"),
                    tester=self.tester,
                    reviewers=self.reviewer,
                    models=self.models,
                    executor=FakeExecutor(),
                    reviewer_runner=reject,
                    project_root=root,
                )


if __name__ == "__main__":
    unittest.main()

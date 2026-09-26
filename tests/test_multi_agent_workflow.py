import unittest
from pathlib import Path
import tempfile

from core.artifacts import ArtifactStore
from core.contracts.handoff import ArtifactContract

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.lifecycle import ExecutionInterrupted
from core.multi_agent_workflow import MultiAgentWorkflow
from runtime.vyrelon import VYRELONRuntime


class FakeExecutor:
    def __init__(self):
        self.calls = []
        self.inputs = []

    def execute(self, *, agent, model_id, work_unit):
        self.calls.append((agent.id, model_id))
        self.inputs.append(dict(work_unit.metadata.get("stage_input", {})))
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

    def test_artifacts_are_persisted_and_linked_to_work_unit(self):
        executor = FakeExecutor()
        agent = AgentContract(id="developer", role="developer")
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-artifact", "produce evidence")
        artifact = ArtifactContract(
            id="artifact-001",
            kind="source",
            producer_agent_id="developer",
            content_ref="workspace/output.py",
            summary="Generated source file",
        )
        work_unit.metadata["artifacts"] = [artifact]

        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            result = MultiAgentWorkflow().run(
                work_unit=work_unit,
                stages=[agent],
                models=models,
                executor=executor,
                artifact_store=store,
            )
            loaded = store.load("artifact-001")

        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
        self.assertIn("artifact-001", work_unit.artifacts)
        self.assertEqual(loaded.content_ref, "workspace/output.py")

    def test_stage_context_contains_previous_artifacts_and_findings(self):
        executor = FakeExecutor()
        agents = [AgentContract(id="planner", role="planner"), AgentContract(id="developer", role="developer")]
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-context", "pass stage context")
        artifact = ArtifactContract("plan-001", "plan", "planner", "plan.json")
        work_unit.metadata["artifacts"] = [artifact]
        work_unit.metadata["stage_findings"] = ["plan is ready"]

        result = MultiAgentWorkflow().run(work_unit=work_unit, stages=agents, models=models, executor=executor)

        self.assertEqual(result.stages[1].findings, ("plan is ready",))
        self.assertEqual(executor.inputs[1]["from_agent"], "planner")
        self.assertEqual(executor.inputs[1]["artifacts"], ("plan-001",))
        self.assertEqual(executor.inputs[1]["findings"], ("plan is ready",))
    def test_debug_retry_is_bounded_and_can_recover(self):
        class Verifier:
            def __init__(self):
                self.calls = 0

            def verify(self, *, work_unit, output):
                self.calls += 1
                return self.calls == 2

        executor = FakeExecutor()
        verifier = Verifier()
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-retry", "fix failing tests")
        agents = [
            AgentContract(id="developer", role="developer"),
            AgentContract(id="tester", role="tester"),
            AgentContract(id="debugger", role="debugger"),
        ]

        result = MultiAgentWorkflow().run_with_debug_retry(
            work_unit=work_unit,
            developer=agents[0],
            tester=agents[1],
            debugger=agents[2],
            models=models,
            executor=executor,
            verifier=verifier,
            max_retries=2,
        )

        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
        self.assertEqual(work_unit.metadata["retry_count"], 1)
        self.assertEqual(
            [stage.agent_id for stage in result.stages],
            ["developer", "tester", "debugger", "tester"],
        )
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


    def test_review_rework_cycle_retries_after_reviewer_feedback(self):
        executor = FakeExecutor()
        developer = AgentContract(id="developer", role="developer")
        tester = AgentContract(id="tester", role="tester")
        reviewers = [
            (AgentContract(id="reviewer-a", role="reviewer"), {}),
            (AgentContract(id="reviewer-b", role="reviewer"), {}),
        ]
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-review-rework", "review and fix feature")
        calls = []

        def reviewer_runner(*, review_work_unit_id, reviewer, context):
            calls.append((reviewer.id, context))
            approved = context["review_cycle"] == 2
            feedback = "" if approved else "please fix the implementation"
            from core.contracts.execution import ReviewDecision
            return ReviewDecision(approved=approved, feedback=feedback)

        result = MultiAgentWorkflow().run_with_review_rework(
            work_unit=work_unit,
            developer=developer,
            tester=tester,
            reviewers=reviewers,
            models=models,
            executor=executor,
            reviewer_runner=reviewer_runner,
            max_review_cycles=2,
        )

        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
        self.assertEqual(work_unit.metadata["review_cycle_count"], 2)
        self.assertEqual([stage.agent_id for stage in result.stages], [
            "developer", "tester", "developer", "tester"
        ])
        self.assertEqual(len(result.reviews), 4)
        self.assertEqual(calls[0][1]["artifact_ids"], ())
        self.assertIn("please fix the implementation", calls[2][1]["findings"])
        self.assertEqual(calls[2][1]["review_cycle"], 2)

    def test_review_rework_cycle_is_bounded(self):
        executor = FakeExecutor()
        developer = AgentContract(id="developer", role="developer")
        tester = AgentContract(id="tester", role="tester")
        reviewer = [(AgentContract(id="reviewer", role="reviewer"), {})]
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-review-limit", "never approved")

        def reviewer_runner(*, review_work_unit_id, reviewer, context):
            from core.contracts.execution import ReviewDecision
            return ReviewDecision(approved=False, feedback="still needs work")

        with self.assertRaises(RuntimeError):
            MultiAgentWorkflow().run_with_review_rework(
                work_unit=work_unit,
                developer=developer,
                tester=tester,
                reviewers=reviewer,
                models=models,
                executor=executor,
                reviewer_runner=reviewer_runner,
                max_review_cycles=2,
            )

        self.assertEqual(work_unit.status, WorkStatus.FAILED)
        self.assertEqual(work_unit.metadata["review_cycle_count"], 2)
        self.assertTrue(work_unit.metadata["rework_required"])


    def test_review_rework_escalates_to_human_and_can_be_approved(self):
        executor = FakeExecutor()
        developer = AgentContract(id="developer", role="developer")
        tester = AgentContract(id="tester", role="tester")
        reviewer = [(AgentContract(id="reviewer", role="reviewer"), {})]
        models = [ModelSpec("local", "local", frozenset())]
        work_unit = WorkUnit("wu-human-gate", "needs human review")

        def reviewer_runner(*, review_work_unit_id, reviewer, context):
            from core.contracts.execution import ReviewDecision
            return ReviewDecision(approved=False, feedback="needs a human decision")

        result = MultiAgentWorkflow().run_with_review_rework(
            work_unit=work_unit,
            developer=developer,
            tester=tester,
            reviewers=reviewer,
            models=models,
            executor=executor,
            reviewer_runner=reviewer_runner,
            max_review_cycles=1,
        )

        self.assertEqual(result.work_unit.status, WorkStatus.WAITING_HUMAN_APPROVAL)
        self.assertTrue(work_unit.metadata["human_review_required"])
        self.assertEqual(work_unit.metadata["review_cycle_count"], 1)

        resolved = MultiAgentWorkflow().resolve_human_review(
            work_unit=work_unit,
            approved=True,
            notes="Human approved the retained evidence.",
        )
        self.assertEqual(resolved.work_unit.status, WorkStatus.COMPLETED)
        self.assertFalse(work_unit.metadata["human_review_required"])
        self.assertEqual(work_unit.metadata["human_review_decision"], "approved")

    def test_human_review_rejection_is_terminal(self):
        work_unit = WorkUnit(
            "wu-human-reject",
            "reject escalation",
            status=WorkStatus.WAITING_HUMAN_APPROVAL,
        )
        result = MultiAgentWorkflow().resolve_human_review(
            work_unit=work_unit,
            approved=False,
            notes="Human rejected the proposed completion.",
        )
        self.assertEqual(result.work_unit.status, WorkStatus.FAILED)
        self.assertEqual(work_unit.metadata["human_review_decision"], "rejected")


    def test_verify_checkpoint_resumes_without_rerunning_stages(self):
        class InterruptingVerifier:
            def __init__(self):
                self.calls = 0

            def verify(self, *, work_unit, output):
                self.calls += 1
                if self.calls == 1:
                    raise ExecutionInterrupted("verification interrupted")
                return True

        class FreshVerifier:
            def verify(self, *, work_unit, output):
                return output == {"agent": "tester"}

        executor = FakeExecutor()
        stages = [
            AgentContract(id="developer", role="developer"),
            AgentContract(id="tester", role="tester"),
        ]
        models = [ModelSpec("local", "local", frozenset())]
        verifier = InterruptingVerifier()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = VYRELONRuntime()
            work_unit = WorkUnit("wu-verify-resume", "resume verification")
            with self.assertRaises(ExecutionInterrupted):
                runtime.run_multi_agent_workflow(
                    work_unit=work_unit,
                    stages=stages,
                    models=models,
                    executor=executor,
                    verifier=verifier,
                    project_root=root,
                )

            checkpoint = runtime.load_checkpoint(work_unit.id, root)
            self.assertEqual(checkpoint.next_action, "verify")
            self.assertEqual(checkpoint.metadata["next_stage_index"], 2)

            resumed = runtime.resume_multi_agent_workflow(
                work_unit.id,
                stages=stages,
                models=models,
                executor=FakeExecutor(),
                verifier=FreshVerifier(),
                project_root=root,
            )

            self.assertEqual(resumed.work_unit.status, WorkStatus.COMPLETED)
            self.assertEqual(resumed.stages, ())
            self.assertEqual(
                runtime.load_checkpoint(work_unit.id, root).resumable,
                False,
            )

    def test_review_checkpoint_resumes_without_rerunning_stages(self):
        class InterruptingReviewer:
            def __init__(self):
                self.calls = 0

            def __call__(self, *, review_work_unit_id, reviewer, context):
                self.calls += 1
                if self.calls == 1:
                    raise ExecutionInterrupted("review interrupted")
                from core.contracts.execution import ReviewDecision
                return ReviewDecision(approved=True, feedback="approved")

        executor = FakeExecutor()
        stages = [AgentContract(id="developer", role="developer")]
        reviewers = [(AgentContract(id="reviewer", role="reviewer"), {})]
        models = [ModelSpec("local", "local", frozenset())]
        reviewer = InterruptingReviewer()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = VYRELONRuntime()
            work_unit = WorkUnit("wu-review-resume", "resume review")
            with self.assertRaises(ExecutionInterrupted):
                runtime.run_multi_agent_workflow(
                    work_unit=work_unit,
                    stages=stages,
                    models=models,
                    executor=executor,
                    reviewers=reviewers,
                    reviewer_runner=reviewer,
                    project_root=root,
                )

            checkpoint = runtime.load_checkpoint(work_unit.id, root)
            self.assertEqual(checkpoint.next_action, "review")

            resumed = runtime.resume_multi_agent_workflow(
                work_unit.id,
                stages=stages,
                models=models,
                executor=FakeExecutor(),
                reviewers=reviewers,
                reviewer_runner=reviewer,
                project_root=root,
            )

            self.assertEqual(resumed.work_unit.status, WorkStatus.COMPLETED)
            self.assertEqual(resumed.stages, ())

    def test_review_rework_checkpoint_resumes_at_review(self):
        class InterruptingReviewer:
            def __init__(self):
                self.calls = 0

            def __call__(self, *, review_work_unit_id, reviewer, context):
                self.calls += 1
                if self.calls == 1:
                    raise ExecutionInterrupted("review interrupted")
                from core.contracts.execution import ReviewDecision
                return ReviewDecision(approved=True, feedback="approved")

        developer = AgentContract(id="developer", role="developer")
        tester = AgentContract(id="tester", role="tester")
        reviewers = [(AgentContract(id="reviewer", role="reviewer"), {})]
        models = [ModelSpec("local", "local", frozenset())]
        reviewer = InterruptingReviewer()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = VYRELONRuntime()
            work_unit = WorkUnit("wu-rework-review-resume", "resume bounded review")
            with self.assertRaises(ExecutionInterrupted):
                runtime.run_review_rework_workflow(
                    work_unit=work_unit,
                    developer=developer,
                    tester=tester,
                    reviewers=reviewers,
                    models=models,
                    executor=FakeExecutor(),
                    reviewer_runner=reviewer,
                    max_review_cycles=2,
                    project_root=root,
                )

            checkpoint = runtime.load_checkpoint(work_unit.id, root)
            self.assertEqual(checkpoint.workflow, "review_rework")
            self.assertEqual(checkpoint.next_action, "review")

            resumed = runtime.resume_review_rework_workflow(
                work_unit.id,
                developer=developer,
                tester=tester,
                reviewers=reviewers,
                models=models,
                executor=FakeExecutor(),
                reviewer_runner=reviewer,
                max_review_cycles=2,
                project_root=root,
            )

            self.assertEqual(resumed.work_unit.status, WorkStatus.COMPLETED)
            self.assertEqual([stage.agent_id for stage in resumed.stages], [])
            self.assertEqual(work_unit.metadata["review_cycle_count"], 1)

    def test_review_rework_checkpoint_resumes_next_rework_cycle(self):
        class RejectThenInterruptExecutor(FakeExecutor):
            def execute(self, *, agent, model_id, work_unit):
                self.calls.append((agent.id, model_id))
                if work_unit.metadata.get("review_cycle") == 2 and agent.id == "developer":
                    raise ExecutionInterrupted("rework interrupted")
                return {"agent": agent.id}

        class RejectFirstReviewer:
            def __init__(self):
                self.calls = 0

            def __call__(self, *, review_work_unit_id, reviewer, context):
                self.calls += 1
                from core.contracts.execution import ReviewDecision
                if context["review_cycle"] == 1:
                    return ReviewDecision(approved=False, feedback="fix before review")
                return ReviewDecision(approved=True, feedback="approved")

        developer = AgentContract(id="developer", role="developer")
        tester = AgentContract(id="tester", role="tester")
        reviewers = [(AgentContract(id="reviewer", role="reviewer"), {})]
        models = [ModelSpec("local", "local", frozenset())]
        reviewer = RejectFirstReviewer()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = VYRELONRuntime()
            work_unit = WorkUnit("wu-rework-cycle-resume", "resume next rework")
            with self.assertRaises(ExecutionInterrupted):
                runtime.run_review_rework_workflow(
                    work_unit=work_unit,
                    developer=developer,
                    tester=tester,
                    reviewers=reviewers,
                    models=models,
                    executor=RejectThenInterruptExecutor(),
                    reviewer_runner=reviewer,
                    max_review_cycles=2,
                    project_root=root,
                )

            checkpoint = runtime.load_checkpoint(work_unit.id, root)
            self.assertEqual(checkpoint.next_action, "rework")
            self.assertEqual(checkpoint.metadata["review_cycle"], 2)

            resumed = runtime.resume_review_rework_workflow(
                work_unit.id,
                developer=developer,
                tester=tester,
                reviewers=reviewers,
                models=models,
                executor=FakeExecutor(),
                reviewer_runner=reviewer,
                max_review_cycles=2,
                project_root=root,
            )

            self.assertEqual(resumed.work_unit.status, WorkStatus.COMPLETED)
            self.assertEqual([stage.agent_id for stage in resumed.stages], ["developer", "tester"])


if __name__ == "__main__":
    unittest.main()

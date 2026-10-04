import tempfile
import unittest
from pathlib import Path

from agents.catalog import build_agent_catalog
from core.contracts.ai import ModelSpec
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.governance import route_plan_steps, smallest_sufficient_path
from runtime.governance_runtime import GovernanceRuntime
from runtime.multi_agent import MultiAgentRuntime


class _Executor:
    def execute(self, *, agent, model_id, work_unit):
        work_unit.metadata.setdefault("execution_trace", []).append(agent.id)
        return {"agent": agent.id, "model": model_id}


class GovernanceRuntimeLifecycleTests(unittest.TestCase):
    def test_governance_runtime_owns_scope_plan_artifact_and_evidence_checks(self):
        work = WorkUnit(
            "wu-governance",
            "bounded change",
            scope_lock=__import__("core.contracts.scope", fromlist=["ScopeLock"]).ScopeLock(
                allowed_files=("src/a.py",)
            ),
        )
        runtime = GovernanceRuntime()
        runtime.validate_work_unit(work)
        steps = route_plan_steps(work)
        plan = __import__("core.contracts.planning", fromlist=["WorkPlan"]).WorkPlan(
            work.id, work.objective, steps
        )
        runtime.validate_plan(work, plan)
        self.assertEqual(steps[-1].agent_id, "reviewer")

    def test_smallest_sufficient_route_contains_all_governance_roles(self):
        route = smallest_sufficient_path("simple")
        self.assertEqual(
            route,
            ("file-picker", "planner", "editor", "executor", "reviewer"),
        )

    def test_native_runtime_executes_governance_route(self):
        work = WorkUnit("wu-route", "route a bounded change")
        agents = {agent.id: agent for agent in build_agent_catalog()}
        steps = MultiAgentRuntime.route_steps(work)
        executors = {agent_id: _Executor() for agent_id in agents}
        model = ModelSpec("local-default", "local", capabilities=frozenset({"general"}))

        with tempfile.TemporaryDirectory() as directory:
            result = MultiAgentRuntime().run(
                project_root=Path(directory),
                work_unit=work,
                steps=steps,
                agents=agents,
                models=[model],
                executors=executors,
            )

        self.assertTrue(result.completed)
        self.assertEqual(work.status, WorkStatus.COMPLETED)
        self.assertEqual(
            work.metadata["execution_agent_ids"],
            ["file-picker", "planner", "editor", "executor", "reviewer"],
        )

    def test_release_impact_stops_at_human_approval_boundary(self):
        work = WorkUnit(
            "wu-release",
            "release-impacting change",
            release_impact="release",
        )
        agents = {agent.id: agent for agent in build_agent_catalog()}
        executors = {agent_id: _Executor() for agent_id in agents}
        evidence = (
            EvidenceRecord(
                id="ev-release",
                work_unit_id=work.id,
                kind=EvidenceKind.VERIFIED,
                source="unittest",
                statement="governed route completed",
                command="python -m unittest",
                exit_code=0,
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            result = MultiAgentRuntime().run(
                project_root=Path(directory),
                work_unit=work,
                steps=MultiAgentRuntime.route_steps(work),
                agents=agents,
                models=[ModelSpec("local-default", "local")],
                executors=executors,
                evidence=evidence,
            )

        self.assertTrue(result.completed)
        self.assertEqual(work.status, WorkStatus.READY_FOR_APPROVAL)
        governance = GovernanceRuntime()
        with self.assertRaises(PermissionError):
            governance.release(work, authorized=True)
        with self.assertRaises(PermissionError):
            governance.approve(work)
        governance.approve(work, authorized=True, notes="explicit human approval")
        self.assertEqual(work.status, WorkStatus.USER_APPROVED)
        governance.release(work, authorized=True)
        self.assertEqual(work.status, WorkStatus.COMPLETED)
        self.assertTrue(work.metadata["released"])

    def test_release_impact_without_verified_evidence_is_blocked(self):
        work = WorkUnit("wu-no-evidence", "release-impacting change", release_impact="release")
        agents = {agent.id: agent for agent in build_agent_catalog()}
        executors = {agent_id: _Executor() for agent_id in agents}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                MultiAgentRuntime().run(
                    project_root=Path(directory),
                    work_unit=work,
                    steps=MultiAgentRuntime.route_steps(work),
                    agents=agents,
                    models=[ModelSpec("local-default", "local")],
                    executors=executors,
                )
        self.assertEqual(work.status, WorkStatus.BLOCKED)

    def test_hold_is_enforced_by_governance_runtime(self):
        work = WorkUnit("wu-hold", "paused work")
        work.transition(WorkStatus.EXECUTING)
        work.hold("waiting for user decision")
        with self.assertRaises(PermissionError):
            GovernanceRuntime().enforce_hold(work)
        with self.assertRaises(PermissionError):
            MultiAgentRuntime().run(
                project_root=Path("."),
                work_unit=work,
                steps=(),
                agents={},
                models=[],
                executors={},
            )


if __name__ == "__main__":
    unittest.main()

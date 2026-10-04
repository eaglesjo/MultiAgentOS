import tempfile
import unittest
from pathlib import Path

from agents.catalog import build_agent_catalog
from core.contracts.ai import ModelSpec
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.scope import ScopeLock
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.governance import (
    route_plan_steps,
    smallest_sufficient_path,
    specialist_route,
)
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
            scope_lock=ScopeLock(allowed_files=("src/a.py",)),
        )
        runtime = GovernanceRuntime()
        runtime.validate_work_unit(work)
        steps = route_plan_steps(work)
        plan = __import__(
            "core.contracts.planning",
            fromlist=["WorkPlan"],
        ).WorkPlan(work.id, work.objective, steps)
        runtime.validate_plan(work, plan)
        self.assertEqual(steps[-1].agent_id, "reviewer")

    def test_smallest_sufficient_route_contains_all_governance_roles(self):
        route = smallest_sufficient_path("simple")
        self.assertEqual(
            route,
            ("file-picker", "planner", "editor", "executor", "reviewer"),
        )

    def test_catalog_exposes_platform_oriented_taxonomy(self):
        agents = {agent.id: agent for agent in build_agent_catalog()}
        self.assertEqual(agents["react-developer"].taxonomy.platform, "web")
        self.assertEqual(agents["android-developer"].taxonomy.technology, "kotlin")
        self.assertEqual(agents["ios-developer"].taxonomy.technology, "swift")
        self.assertEqual(
            agents["ui-android"].taxonomy.parent_id,
            "ui-native",
        )
        self.assertEqual(
            agents["ui-ios"].taxonomy.parent_id,
            "ui-native",
        )
        self.assertEqual(
            agents["ui-research-android"].taxonomy.specialization,
            "ui",
        )
        self.assertEqual(
            agents["development-research-react"].taxonomy.specialization,
            "development",
        )

    def test_governance_agents_are_orthogonal_to_specialists(self):
        agents = {agent.id: agent for agent in build_agent_catalog()}
        self.assertEqual(agents["editor"].taxonomy.layer, "governance")
        self.assertEqual(agents["executor"].taxonomy.layer, "governance")
        self.assertEqual(agents["react-developer"].taxonomy.layer, "specialist")
        self.assertEqual(agents["ui-agent"].taxonomy.domain, "ui")

    def test_development_route_researches_before_platform_developer(self):
        work = WorkUnit(
            "wu-react",
            "update React login",
            work_type="development",
            target="react",
        )
        self.assertEqual(
            specialist_route(work),
            (
                "file-picker",
                "planner",
                "development",
                "development-research-react",
                "react-developer",
                "editor",
                "executor",
                "reviewer",
            ),
        )

    def test_react_native_development_route_is_explicit(self):
        work = WorkUnit(
            "wu-rn",
            "update React Native login",
            work_type="development",
            target="react-native",
        )
        self.assertEqual(
            specialist_route(work),
            (
                "file-picker",
                "planner",
                "development",
                "development-research-react-native",
                "react-native-developer",
                "editor",
                "executor",
                "reviewer",
            ),
        )

    def test_android_ui_route_uses_android_ui_research_and_compose_specialist(self):
        work = WorkUnit(
            "wu-android-ui",
            "update Android login UI",
            work_type="ui",
            target="android",
        )
        self.assertEqual(
            specialist_route(work),
            (
                "file-picker",
                "planner",
                "ui-agent",
                "ui-research-android",
                "ui-native",
                "ui-android",
                "editor",
                "executor",
                "tester",
                "reviewer",
            ),
        )

    def test_ios_ui_route_uses_ios_ui_research_and_swiftui_specialist(self):
        work = WorkUnit(
            "wu-ios-ui",
            "update iOS login UI",
            work_type="ui",
            target="ios",
        )
        self.assertEqual(
            specialist_route(work),
            (
                "file-picker",
                "planner",
                "ui-agent",
                "ui-research-ios",
                "ui-native",
                "ui-ios",
                "editor",
                "executor",
                "tester",
                "reviewer",
            ),
        )

    def test_web_ui_route_keeps_browser_agent_as_capability(self):
        work = WorkUnit(
            "wu-web-ui",
            "update React web UI",
            work_type="ui",
            target="react",
        )
        route = specialist_route(work)
        self.assertIn("ui-web", route)
        self.assertIn("browser-agent", route)
        self.assertNotEqual(route[2], "browser-agent")

    def test_native_runtime_executes_governance_route(self):
        work = WorkUnit("wu-route", "route a bounded change")
        agents = {agent.id: agent for agent in build_agent_catalog()}
        steps = MultiAgentRuntime.route_steps(work)
        executors = {agent_id: _Executor() for agent_id in agents}
        model = ModelSpec(
            "local-default",
            "local",
            capabilities=frozenset().union(
                *(agent.capabilities for agent in agents.values())
            ),
        )

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
                models=[
                    ModelSpec(
                        "local-default",
                        "local",
                        capabilities=frozenset().union(
                            *(agent.capabilities for agent in agents.values())
                        ),
                    )
                ],
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
        with self.assertRaises(ValueError):
            work.transition(WorkStatus.READY_FOR_APPROVAL)

    def test_release_impact_without_verified_evidence_is_blocked(self):
        work = WorkUnit(
            "wu-no-evidence",
            "release-impacting change",
            release_impact="release",
        )
        agents = {agent.id: agent for agent in build_agent_catalog()}
        executors = {agent_id: _Executor() for agent_id in agents}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                MultiAgentRuntime().run(
                    project_root=Path(directory),
                    work_unit=work,
                    steps=MultiAgentRuntime.route_steps(work),
                    agents=agents,
                    models=[
                        ModelSpec(
                            "local-default",
                            "local",
                            capabilities=frozenset().union(
                                *(agent.capabilities for agent in agents.values())
                            ),
                        )
                    ],
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


    def test_ui_taxonomy_has_explicit_cross_platform_and_native_branches(self):
        rn = specialist_route(WorkUnit("wu-rn-ui", "update RN UI", work_type="ui", target="react-native"))
        android = specialist_route(WorkUnit("wu-android-ui-branch", "update Android UI", work_type="ui", target="android"))
        ios = specialist_route(WorkUnit("wu-ios-ui-branch", "update iOS UI", work_type="ui", target="ios"))
        self.assertIn("ui-agent", rn)
        self.assertIn("ui-react-native", rn)
        self.assertNotIn("ui-native", rn)
        self.assertIn("ui-native", android)
        self.assertIn("ui-android", android)
        self.assertIn("ui-native", ios)
        self.assertIn("ui-ios", ios)

    def test_governance_rejects_wrong_specialist_route(self):
        work = WorkUnit("wu-route-check", "update Android UI", work_type="ui", target="android")
        wrong = ("file-picker", "planner", "ui-research-android", "ui-android", "editor", "executor", "tester", "reviewer")
        plan = __import__("core.contracts.planning", fromlist=["WorkPlan"]).WorkPlan(
            work.id, work.objective,
            tuple(__import__("core.contracts.planning", fromlist=["PlanStep"]).PlanStep(
                f"{agent}-{i}", agent, agent, scope_lock=work.scope_lock
            ) for i, agent in enumerate(wrong))
        )
        with self.assertRaises(ValueError):
            GovernanceRuntime().validate_plan(work, plan)

if __name__ == "__main__":
    unittest.main()

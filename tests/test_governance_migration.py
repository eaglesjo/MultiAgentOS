import unittest

from agents.catalog import build_agent_catalog
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.scope import ScopeLock
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.planning import PlanStep, WorkPlan
from runtime.governance import smallest_sufficient_path, validate_evidence, validate_scope
from runtime.multi_agent import MultiAgentRuntime


class GovernanceMigrationTests(unittest.TestCase):
    def test_catalog_contains_pet_tarot_execution_roles(self):
        agents = {agent.id: agent for agent in build_agent_catalog()}
        expected = {
            "file-picker",
            "planner",
            "web-researcher",
            "editor",
            "executor",
            "terminal-monitor",
            "reviewer",
            "browser-agent",
            "debugger",
        }
        self.assertTrue(expected.issubset(agents))
        self.assertIn("filesystem.write", agents["editor"].permissions)
        self.assertTrue(agents["reviewer"].scope_aware)

    def test_scope_lock_is_enforced(self):
        scope = ScopeLock(
            allowed_files=("src/a.py",),
            excluded_files=("src/secrets.py",),
        )
        self.assertTrue(validate_scope(scope).passed)
        self.assertTrue(scope.allows("src/a.py"))
        self.assertFalse(scope.allows("src/secrets.py"))
        self.assertFalse(scope.allows("src/b.py"))

    def test_scope_lock_rejects_overlap(self):
        scope = ScopeLock(allowed_files=("a.py",), excluded_files=("a.py",))
        self.assertFalse(validate_scope(scope).passed)

    def test_child_scope_cannot_escape_parent_scope(self):
        parent = ScopeLock(allowed_files=("src/a.py", "src/b.py"))
        self.assertTrue(parent.contains(ScopeLock(allowed_files=("src/a.py",))))
        self.assertFalse(parent.contains(ScopeLock(allowed_files=("src/c.py",))))
        self.assertFalse(parent.contains(ScopeLock()))
        with self.assertRaises(ValueError):
            parent.contains(
                ScopeLock(
                    allowed_files=("src/a.py",),
                    excluded_files=("src/a.py",),
                )
            )

    def test_evidence_is_bound_to_work_unit(self):
        work = WorkUnit("wu-1", "verify")
        evidence = EvidenceRecord(
            id="ev-1",
            work_unit_id="wu-1",
            kind=EvidenceKind.VERIFIED,
            source="pytest",
            statement="tests passed",
            command="pytest",
            exit_code=0,
        )
        self.assertTrue(validate_evidence(work, (evidence,), require_verified=True).passed)

    def test_hold_requires_explicit_resume_authorization(self):
        work = WorkUnit("wu-hold", "pause")
        work.transition(WorkStatus.EXECUTING)
        work.hold("awaiting user decision")
        with self.assertRaises(PermissionError):
            work.resume_from_hold()
        work.resume_from_hold(authorized=True)
        self.assertEqual(work.status, WorkStatus.EXECUTING)

    def test_plan_steps_carry_scope_lock(self):
        step = PlanStep(
            "edit",
            "bounded edit",
            "editor",
            scope_lock=ScopeLock(allowed_files=("src/a.py",)),
        )
        WorkPlan("wu-plan", "edit", (step,)).validate()
        self.assertTrue(step.scope_lock.allows("src/a.py"))
        self.assertFalse(step.scope_lock.allows("src/b.py"))

    def test_runtime_rejects_step_scope_outside_work_unit_scope(self):
        work = WorkUnit(
            "wu-scope-runtime",
            "bounded edit",
            scope_lock=ScopeLock(allowed_files=("src/a.py",)),
        )
        step = PlanStep(
            "edit",
            "edit outside parent scope",
            "editor",
            scope_lock=ScopeLock(allowed_files=("src/b.py",)),
        )
        with self.assertRaises(ValueError):
            MultiAgentRuntime().run(
                project_root=__import__("pathlib").Path("."),
                work_unit=work,
                steps=(step,),
                agents={},
                models=[],
                executors={},
            )

    def test_runtime_rejects_hold_without_authorization(self):
        work = WorkUnit("wu-runtime-hold", "pause")
        work.transition(WorkStatus.EXECUTING)
        work.hold("awaiting user decision")
        with self.assertRaises(PermissionError):
            MultiAgentRuntime().run(
                project_root=__import__("pathlib").Path("."),
                work_unit=work,
                steps=(),
                agents={},
                models=[],
                executors={},
            )

    def test_smallest_sufficient_routes(self):
        self.assertEqual(
            smallest_sufficient_path("simple"),
            ("file-picker", "planner", "editor", "executor", "reviewer"),
        )
        self.assertEqual(
            smallest_sufficient_path("external_research"),
            (
                "file-picker",
                "planner",
                "web-researcher",
                "editor",
                "executor",
                "reviewer",
            ),
        )


if __name__ == "__main__":
    unittest.main()

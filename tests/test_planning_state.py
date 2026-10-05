import tempfile
import unittest
from pathlib import Path

from core.contracts.planning import PlanStep
from core.contracts.scope import ScopeLock
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.planning import BasicPlanner
from core.state import WorkStateStore


class PlanningStateTests(unittest.TestCase):
    def test_plan_transitions_work_unit_and_validates_dependencies(self):
        work = WorkUnit("wu-plan", "build feature")
        plan = BasicPlanner().plan(
            work,
            [
                PlanStep("design", "design feature"),
                PlanStep("implement", "implement feature", depends_on=("design",)),
            ],
        )
        self.assertEqual(work.status, WorkStatus.PLANNING)
        self.assertEqual(plan.steps[1].depends_on, ("design",))

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            store = WorkStateStore(Path(temp) / "state")
            work = WorkUnit(
                "wu-state",
                "persist me",
                work_type="ui",
                target="ios",
                environment="macos",
                artifact_class="source",
                release_impact="production",
                scope_lock=ScopeLock(
                    allowed_files=("src/App.tsx",),
                    excluded_files=("src/secrets.ts",),
                ),
            )
            work.assign("developer")
            work.transition(WorkStatus.EXECUTING)
            path = store.save(work)
            restored = store.load("wu-state")
            self.assertTrue(path.exists())
        self.assertEqual(restored.status, WorkStatus.EXECUTING)
        self.assertEqual(restored.assigned_agents, ["developer"])
        self.assertEqual(restored.work_type, "ui")
        self.assertEqual(restored.target, "ios")
        self.assertEqual(restored.environment, "macos")
        self.assertEqual(restored.artifact_class, "source")
        self.assertEqual(restored.release_impact, "production")
        self.assertEqual(restored.scope_lock.allowed_files, ("src/App.tsx",))
        self.assertEqual(restored.scope_lock.excluded_files, ("src/secrets.ts",))

    def test_state_persistence_redacts_sensitive_values(self):
        with tempfile.TemporaryDirectory() as temp:
            store = WorkStateStore(Path(temp) / "state")
            work = WorkUnit(
                "wu-secret",
                "redact me",
                inputs={"api_key": "sk-test-secret"},
                metadata={"access_token": "Bearer test-secret-token"},
            )
            path = store.save(work)
            raw = path.read_text(encoding="utf-8")
            restored = store.load("wu-secret")

        self.assertNotIn("sk-test-secret", raw)
        self.assertNotIn("Bearer test-secret-token", raw)
        self.assertEqual(restored.inputs["api_key"], "[REDACTED]")
        self.assertEqual(restored.metadata["access_token"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()

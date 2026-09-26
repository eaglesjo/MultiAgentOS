import tempfile
import unittest
from pathlib import Path

from core.contracts.planning import PlanStep
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
            work = WorkUnit("wu-state", "persist me")
            work.assign("developer")
            work.transition(WorkStatus.EXECUTING)
            path = store.save(work)
            restored = store.load("wu-state")
            self.assertTrue(path.exists())
            self.assertEqual(restored.status, WorkStatus.EXECUTING)
            self.assertEqual(restored.assigned_agents, ["developer"])


if __name__ == "__main__":
    unittest.main()

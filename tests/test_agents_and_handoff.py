import unittest

from agents.catalog import build_agent_catalog
from agents.registry import build_registry
from core.contracts.agent import AgentContract
from core.handoff import HandoffManager, ReviewPanel


class AgentsAndHandoffTests(unittest.TestCase):
    def test_catalog_contains_common_and_react_native_specialists(self):
        agents = {agent.id for agent in build_agent_catalog(("react-native",))}
        self.assertIn("planner", agents)
        self.assertIn("developer", agents)
        self.assertIn("navigation", agents)

    def test_registry_builds_unique_agents(self):
        registry = build_registry(("android-native",))
        self.assertEqual(registry.get("kotlin-developer").kind, "specialist")

    def test_handoff_preserves_artifact_context(self):
        source = AgentContract(id="developer", role="developer")
        target = AgentContract(id="tester", role="tester")
        handoff = HandoffManager().create(
            "wu-1", source, target, "implementation complete",
            ["src/a.py"], ["edge case"]
        )
        self.assertEqual(handoff.to_agent, "tester")
        self.assertEqual(handoff.artifacts, ("src/a.py",))

    def test_review_panel_requires_all_reviewers(self):
        reviewers = [
            (AgentContract(id="r1", role="reviewer"), None),
            (AgentContract(id="r2", role="reviewer"), None),
        ]
        def runner(**kwargs):
            return type(
                "R", (),
                {
                    "approved": kwargs["reviewer"].id == "r1",
                    "reviewer_id": kwargs["reviewer"].id,
                    "feedback": "ok",
                },
            )()
        result = ReviewPanel().review("wu-1", reviewers, runner)
        self.assertFalse(result.approved)
        self.assertEqual(result.consensus, "changes-requested")


if __name__ == "__main__":
    unittest.main()

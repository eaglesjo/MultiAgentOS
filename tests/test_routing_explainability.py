import unittest

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.quota import QuotaDimension, QuotaSnapshot
from core.routing import AIRouter


class RoutingExplainabilityTests(unittest.TestCase):
    def test_explain_reports_selection_and_rejections(self):
        agent = AgentContract(
            id="developer",
            role="developer",
            capabilities=frozenset({"code", "react-native"}),
        )
        models = [
            ModelSpec("general", "provider-a", frozenset({"code"})),
            ModelSpec("specialist", "provider-b", frozenset({"code", "react-native"})),
        ]

        explanation = AIRouter().explain(agent, models)

        self.assertEqual(explanation.selected_model_id, "specialist")
        candidates = {item.model_id: item for item in explanation.candidates}
        self.assertTrue(candidates["specialist"].selected)
        self.assertFalse(candidates["general"].compatible)
        self.assertEqual(candidates["general"].missing_capabilities, frozenset({"react-native"}))
        self.assertIn("missing_capabilities", candidates["general"].rejection_reasons)

    def test_explain_reports_quota_rejection(self):
        agent = AgentContract(
            id="developer",
            role="developer",
            capabilities=frozenset({"code"}),
        )
        models = [
            ModelSpec("exhausted", "provider-a", frozenset({"code"})),
            ModelSpec("available", "provider-b", frozenset({"code"})),
        ]
        quota = QuotaSnapshot(
            model_id="exhausted",
            provider_id="provider-a",
            observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            dimensions=(QuotaDimension("requests", limit=100, remaining=0),),
        )

        explanation = AIRouter().explain(
            agent,
            models,
            quota_snapshots={"exhausted": quota},
        )

        self.assertEqual(explanation.selected_model_id, "available")
        exhausted = next(item for item in explanation.candidates if item.model_id == "exhausted")
        self.assertFalse(exhausted.quota_available)
        self.assertIn("quota_unavailable", exhausted.rejection_reasons)

    def test_assign_remains_compatible_with_explain(self):
        agent = AgentContract(
            id="developer",
            role="developer",
            capabilities=frozenset({"code"}),
        )
        models = [
            ModelSpec("first", "provider-a", frozenset({"code"})),
            ModelSpec("second", "provider-b", frozenset({"code"})),
        ]

        assignment = AIRouter().assign(agent, models, preferred_model_ids=["second"])
        explanation = AIRouter().explain(agent, models, preferred_model_ids=["second"])

        self.assertEqual(assignment.model_id, "second")
        self.assertEqual(explanation.assignment, assignment)


if __name__ == "__main__":
    unittest.main()

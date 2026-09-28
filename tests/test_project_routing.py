import json
import tempfile
import unittest
from pathlib import Path

from core.contracts.ai import ModelSpec
from core.routing import AIRouter
from profiles.resolver import ProfileResolver


class ProjectRoutingTests(unittest.TestCase):
    def test_react_native_profile_produces_specialist_agent_and_routes_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.80.0"}}),
                encoding="utf-8",
            )

            project, agents = ProfileResolver().resolve(root)
            developer = next(agent for agent in agents if agent.id == "developer")
            models = [
                ModelSpec(
                    id="general",
                    provider_id="test",
                    capabilities=frozenset({"code"}),
                ),
                ModelSpec(
                    id="rn-capable",
                    provider_id="test",
                    capabilities=frozenset({"code", "react-native"}),
                ),
            ]

            assignment = AIRouter().assign(developer.to_contract(), models)

            self.assertEqual(project.primary_technology_profile, "react-native")
            self.assertEqual(assignment.agent_id, "developer")
            self.assertEqual(assignment.model_id, "rn-capable")

    def test_routing_rejects_incompatible_models(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.80.0"}}),
                encoding="utf-8",
            )
            _, agents = ProfileResolver().resolve(root)
            developer = next(agent for agent in agents if agent.id == "developer")

            with self.assertRaises(LookupError):
                AIRouter().assign(
                    developer.to_contract(),
                    [
                        ModelSpec(
                            id="general",
                            provider_id="test",
                            capabilities=frozenset({"code"}),
                        )
                    ],
                )


if __name__ == "__main__":
    unittest.main()

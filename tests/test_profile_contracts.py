import tempfile
import unittest
from pathlib import Path

from core.contracts.profile import AgentProfile, ProjectProfile
from profiles.resolver import ProfileResolver


class ProfileContractTests(unittest.TestCase):
    def test_react_native_resolution_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"react-native":"0.80.0"}}',
                encoding="utf-8",
            )

            project, agents = ProfileResolver().resolve(root)

            self.assertIsInstance(project, ProjectProfile)
            self.assertEqual(project.technology_profile_ids, ("react-native",))
            self.assertIn("developer", project.agent_profile_ids)
            self.assertIn("architect", project.agent_profile_ids)
            self.assertEqual(agents[0].profile_ids, ("react-native",))

    def test_agent_profile_materializes_common_agent_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"react-native":"0.80.0"}}',
                encoding="utf-8",
            )

            _, agents = ProfileResolver().resolve(root)
            executor = next(agent for agent in agents if agent.id == "executor")

            contract = executor.to_contract()

            self.assertEqual(contract.id, "executor")
            self.assertEqual(contract.kind, "profile")
            self.assertIn("react-native", contract.metadata["profiles"])
            self.assertEqual(contract.metadata["agent_profile_id"], "executor")
            self.assertIn("execution", contract.capabilities)

    def test_project_without_detected_technology_still_has_common_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, agents = ProfileResolver().resolve(Path(tmp))

            self.assertEqual(project.technology_profile_ids, ())
            self.assertIn("executor", project.agent_profile_ids)
            self.assertTrue(all(isinstance(agent, AgentProfile) for agent in agents))

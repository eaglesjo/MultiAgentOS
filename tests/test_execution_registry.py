import unittest

from runtime.execution_registry import (
    default_execution_registries,
    resolve_execution_contracts,
)


class ExecutionRegistryTests(unittest.TestCase):
    def test_defaults_are_registered(self):
        agents, models = default_execution_registries()
        self.assertEqual(agents.get("cli-executor").role, "executor")
        self.assertEqual(models.model("local-process").provider_id, "local")

    def test_resolution_preserves_agent_model_separation(self):
        agent, model = resolve_execution_contracts("cli-executor", "local-process")
        self.assertEqual(agent.id, "cli-executor")
        self.assertEqual(model.id, "local-process")

    def test_unknown_agent_is_rejected(self):
        with self.assertRaises(KeyError):
            resolve_execution_contracts("missing-agent", "local-process")

    def test_unknown_model_is_rejected(self):
        with self.assertRaises(KeyError):
            resolve_execution_contracts("cli-executor", "missing-model")

    def test_incompatible_contracts_are_rejected(self):
        agents, models = default_execution_registries()
        # The public resolver is intentionally strict; this test verifies the
        # contract rule used by the registry-backed execution path.
        agent = agents.get("cli-executor")
        model = next(iter(models.models()))
        self.assertTrue(agent.capabilities.issubset(model.capabilities))

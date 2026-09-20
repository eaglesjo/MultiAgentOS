import unittest

from core.contracts import AgentContract, AIProvider, ModelSpec, WorkStatus, WorkUnit
from core.registry import AIRegistry, AgentRegistry
from core.routing import AIRouter


class CoreRuntimeTests(unittest.TestCase):
    def test_work_unit_lifecycle_and_assignment(self):
        work = WorkUnit(id="wu-001", objective="implement feature")
        work.assign("developer")
        work.transition(WorkStatus.EXECUTING)
        work.transition(WorkStatus.VERIFYING)
        work.transition(WorkStatus.COMPLETED)

        self.assertEqual(work.status, WorkStatus.COMPLETED)
        self.assertEqual(work.assigned_agents, ["developer"])

    def test_work_unit_rejects_invalid_transition(self):
        work = WorkUnit(id="wu-invalid", objective="invalid")
        with self.assertRaises(ValueError):
            work.transition(WorkStatus.COMPLETED)

    def test_agent_registry_rejects_duplicates(self):
        registry = AgentRegistry()
        agent = AgentContract(id="developer", role="developer")
        registry.register(agent)

        with self.assertRaises(ValueError):
            registry.register(agent)

    def test_ai_router_prefers_requested_compatible_model(self):
        agent = AgentContract(
            id="developer",
            role="developer",
            capabilities=frozenset({"code"}),
        )
        provider = AIProvider(
            id="provider-a",
            kind="cloud",
            models=(
                ModelSpec("slow", "provider-a", frozenset({"code"})),
                ModelSpec("fast", "provider-a", frozenset({"code", "review"})),
            ),
        )
        registry = AIRegistry()
        registry.register(provider)

        assignment = AIRouter().assign(
            agent, list(registry.models()), preferred_model_ids=["fast"]
        )
        self.assertEqual(assignment.model_id, "fast")

    def test_ai_router_falls_back_to_compatible_model(self):
        agent = AgentContract(
            id="reviewer",
            role="reviewer",
            capabilities=frozenset({"review"}),
        )
        provider = AIProvider(
            id="local",
            kind="local",
            models=(ModelSpec("local-review", "local", frozenset({"review"})),),
        )
        registry = AIRegistry()
        registry.register(provider)

        assignment = AIRouter().assign(agent, list(registry.models()))
        self.assertEqual(assignment.model_id, "local-review")


if __name__ == "__main__":
    unittest.main()

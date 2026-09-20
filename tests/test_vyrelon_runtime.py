import tempfile
import unittest
from pathlib import Path

from core.contracts import AgentContract, ModelSpec, WorkUnit, WorkStatus
from core.contracts.model_runtime import ModelResponse
from runtime.vyrelon import VYRELONRuntime


class FakeExecutor:
    def execute(self, *, agent, model_id, work_unit):
        return ModelResponse(text="done", model_id=model_id)


class VYRELONRuntimeTests(unittest.TestCase):
    def test_inspect_and_agent_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                '{"dependencies":{"react-native":"0.82.0"}}',
                encoding="utf-8",
            )
            runtime = VYRELONRuntime()
            self.assertTrue(runtime.inspect(root))
            self.assertIn("navigation", [a.id for a in runtime.agents(root).list()])

    def test_run_executes_through_orchestrator(self):
        runtime = VYRELONRuntime()
        agent = AgentContract(
            id="developer", role="developer",
            capabilities=frozenset({"code"}),
        )
        models = [ModelSpec("model-a", "provider-a", frozenset({"code"}))]
        result = runtime.run(
            WorkUnit("wu-runtime", "implement feature"),
            agent,
            models,
            FakeExecutor(),
        )
        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
        self.assertEqual(result.delegation.assignment.model_id, "model-a")


if __name__ == "__main__":
    unittest.main()

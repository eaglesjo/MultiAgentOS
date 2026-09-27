import tempfile
import unittest
from pathlib import Path

from core.contracts import AgentContract, ModelSpec, WorkUnit, WorkStatus
from core.contracts.model_runtime import ModelResponse
from core.contracts.ide import IDEKind
import json
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

    def test_run_persistent_saves_lifecycle_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = VYRELONRuntime()
            agent = AgentContract(
                id="executor", role="executor",
                capabilities=frozenset({"execution"}),
            )
            models = [ModelSpec("local-process", "vyrelon-local", frozenset({"execution"}))]
            result = runtime.run_persistent(
                root,
                WorkUnit("wu-persistent", "run persistent task"),
                agent,
                models,
                FakeExecutor(),
                preferred_model_ids=["local-process"],
            )
            persisted = runtime.state_store(root).load("wu-persistent")
            self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
            self.assertEqual(persisted.status, WorkStatus.COMPLETED)
            self.assertEqual(persisted.assigned_agents, ["executor"])
            self.assertEqual(persisted.metadata["cwd"], str(root))

    def test_ide_bridge_is_owned_by_vyrelon_runtime(self):
        runtime = VYRELONRuntime()
        server = runtime.start_ide_bridge(token="secret", port=0)
        try:
            self.assertIs(runtime.ide_bridge_server, server)
            self.assertEqual(server.server.server_address[0], "127.0.0.1")
            self.assertEqual(runtime.ide._contexts, {})
        finally:
            runtime.stop_ide_bridge()
        self.assertIsNone(runtime.ide_bridge_server)

    def test_run_model_uses_provider_neutral_adapter(self):
        class Adapter:
            def generate(self, model, request):
                return ModelResponse(text='hello', model_id=model.id)

        runtime = VYRELONRuntime()
        agent = AgentContract(
            id="writer", role="writer",
            capabilities=frozenset({"generation"}),
            model_ids=("model-a",),
        )
        model = ModelSpec(
            id="model-a", provider_id="provider-a",
            capabilities=frozenset({"generation"}),
            metadata={"adapter_id": "adapter-a"},
        )
        work = WorkUnit('wu-model-runtime', 'write something')
        result = runtime.run_model(
            work, agent, [model], {'adapter-a': Adapter()},
            preferred_model_ids=["model-a"],
        )
        self.assertEqual(result.output.text, 'hello')
        self.assertEqual(work.status, WorkStatus.COMPLETED)

    def test_run_configured_work_loads_project_config_and_agent(self):
        class Adapter:
            def generate_with_tools(self, model, request, tools):
                return ModelResponse(text="configured", model_id=model.id)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                '{"dependencies":{"react-native":"0.82.0"}}', encoding="utf-8"
            )
            config = root / ".multiagentos"
            config.mkdir()
            (config / "providers.json").write_text(json.dumps({
                "providers": [{
                    "id": "test-provider",
                    "kind": "openai",
                    "models": [{
                        "id": "test-model",
                        "capabilities": ["code"],
                        "metadata": {"adapter_id": "test-adapter"},
                    }],
                }]
            }), encoding="utf-8")
            runtime = VYRELONRuntime()
            result = runtime.run_configured_work(
                root,
                objective="implement configured task",
                agent_id="developer",
                preferred_model_ids=["test-model"],
                adapter_overrides={"test-adapter": Adapter()},
            )
            self.assertEqual(result.output.text, "configured")
            self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
            self.assertEqual(result.work_unit.metadata["runtime"], "configured-model")
            self.assertEqual(result.work_unit.metadata["agent_id"], "developer")

if __name__ == "__main__":
    unittest.main()

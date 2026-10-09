import tempfile
import unittest
from pathlib import Path

from core.contracts import AgentContract, ModelSpec, WorkUnit, WorkStatus
from core.contracts.model_runtime import ModelResponse
from core.contracts.ide import IDEKind, IDEContext, IDEWorkRequest
import json
from runtime import AgentExecutionRuntime as AgentExecutionRuntime


class FakeExecutor:
    def execute(self, *, agent, model_id, work_unit):
        return ModelResponse(text="done", model_id=model_id)


class AgentExecutionRuntimeTests(unittest.TestCase):
    def test_inspect_and_agent_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                '{"dependencies":{"react-native":"0.82.0"}}',
                encoding="utf-8",
            )
            runtime = AgentExecutionRuntime()
            self.assertTrue(runtime.inspect(root))
            self.assertIn("navigation", [a.id for a in runtime.agents(root).list()])

    def test_run_executes_through_orchestrator(self):
        runtime = AgentExecutionRuntime()
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
            runtime = AgentExecutionRuntime()
            agent = AgentContract(
                id="executor", role="executor",
                capabilities=frozenset({"execution"}),
            )
            models = [ModelSpec("local-process", "agent_execution_runtime-local", frozenset({"execution"}))]
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

    def test_ide_bridge_is_owned_by_agent_execution_runtime(self):
        runtime = AgentExecutionRuntime()
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

        runtime = AgentExecutionRuntime()
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
                        "capabilities": ["code", "react-native"],
                        "metadata": {"adapter_id": "test-adapter"},
                    }],
                }]
            }), encoding="utf-8")
            runtime = AgentExecutionRuntime()
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

    def test_ide_work_uses_persistent_tool_calling_runtime(self):
        class Adapter:
            def __init__(self):
                self.calls = 0

            def generate_with_tools(self, model, request, tools):
                self.calls += 1
                if self.calls == 1:
                    if "filesystem.read" not in {tool.id for tool in tools}:
                        raise AssertionError("filesystem.read tool was not registered")
                    return ModelResponse(text="", model_id=model.id, metadata={"tool_calls": [{"id": "read-1", "name": "filesystem.read", "arguments": {"path": "README.md"}}]})
                return ModelResponse(text="ide-tool-complete", model_id=model.id)

        class IDEAdapter:
            kind = IDEKind.VS_CODE
            def capabilities(self): return frozenset({"show_message"})
            def context(self): raise AssertionError("context should not be requested")
            def execute(self, command): return type("Result", (), {"ok": True, "output": command.arguments})()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text('{"dependencies":{"react-native":"0.82.0"}}', encoding="utf-8")
            (root / "README.md").write_text("runtime integration", encoding="utf-8")
            config = root / ".multiagentos"
            config.mkdir()
            (config / "providers.json").write_text(json.dumps({"providers": [{"id": "test-provider", "kind": "openai", "models": [{"id": "test-model", "capabilities": ["code", "react-native"], "metadata": {"adapter_id": "test-adapter"}}]}]}), encoding="utf-8")
            runtime = AgentExecutionRuntime()
            runtime.ide.register(IDEAdapter())
            result = runtime.submit_ide_work(IDEWorkRequest(context=IDEContext(kind=IDEKind.VS_CODE, project_root=str(root)), objective="inspect the project", agent_id="developer", model_ids=("test-model",)), adapter_overrides={"test-adapter": Adapter()})
            self.assertEqual(result["orchestration"].output.text, "ide-tool-complete")
            self.assertEqual(result["work_unit"].status, WorkStatus.COMPLETED)
            self.assertEqual(result["work_unit"].metadata["tool_rounds"], 2)
    def test_configured_runtime_persists_execution_events(self):
        class Adapter:
            def generate_with_tools(self, model, request, tools):
                return ModelResponse(text="evented", model_id=model.id)

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
                        "capabilities": ["code", "react-native"],
                        "metadata": {"adapter_id": "test-adapter"},
                    }],
                }]
            }), encoding="utf-8")
            runtime = AgentExecutionRuntime()
            result = runtime.run_configured_work(
                root,
                objective="persist execution evidence",
                agent_id="developer",
                preferred_model_ids=["test-model"],
                adapter_overrides={"test-adapter": Adapter()},
            )
            events = runtime.event_store(root).load(result.work_unit.id)
            self.assertEqual([item["kind"] for item in events], ["request", "message", "completed"])
            self.assertEqual([item["sequence"] for item in events], [1, 2, 3])
            self.assertEqual(events[-1]["payload"]["rounds"], 1)

    def test_failed_work_can_be_resumed_from_persisted_state(self):
        class FailingAdapter:
            def generate(self, model, request):
                raise RuntimeError("temporary failure")
            def generate_with_tools(self, model, request, tools):
                raise RuntimeError("temporary failure")

        class WorkingAdapter:
            def generate(self, model, request):
                return ModelResponse(text="resumed", model_id=model.id)
            def generate_with_tools(self, model, request, tools):
                return ModelResponse(text="resumed", model_id=model.id)

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
                        "capabilities": ["code", "react-native"],
                        "metadata": {"adapter_id": "test-adapter"},
                    }],
                }]
            }), encoding="utf-8")
            runtime = AgentExecutionRuntime()
            with self.assertRaises(RuntimeError):
                runtime.run_configured_work(
                    root,
                    objective="recover me",
                    agent_id="developer",
                    preferred_model_ids=["test-model"],
                    adapter_overrides={"test-adapter": FailingAdapter()},
                )
            store = runtime.state_store(root)
            work_id = store.list_ids()[-1]
            failed = store.load(work_id)
            self.assertEqual(failed.status, WorkStatus.FAILED)
            self.assertEqual(failed.metadata["error"], "temporary failure")
            result = runtime.resume_work(
                root,
                work_id,
                agent_id="developer",
                preferred_model_ids=["test-model"],
                adapter_overrides={"test-adapter": WorkingAdapter()},
            )
            self.assertEqual(result.output.text, "resumed")
            resumed = store.load(work_id)
            self.assertEqual(resumed.status, WorkStatus.COMPLETED)
            self.assertEqual(resumed.metadata["resume_count"], 1)

    def test_session_spans_work_units_and_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime()
            session = runtime.create_session(root, agent_id="developer")
            work = WorkUnit(id="session-work", objective="continue")
            work.transition(WorkStatus.EXECUTING)
            work.transition(WorkStatus.FAILED)
            runtime.state_store(root).save(work)
            runtime.attach_work_unit(root, session.spec.id, work.id)
            state = runtime.load_session(root, session.spec.id)
            self.assertEqual(state.work_unit_ids, ["session-work"])
            recovered_state, recoverable = runtime.session_recover(root, session.spec.id)
            self.assertEqual(recovered_state.status, "recoverable")
            self.assertEqual(tuple(item.id for item in recoverable), ("session-work",))


    def test_run_auto_persists_completed_work_unit(self):
        class AutoOrchestrator:
            def run_auto(self, *, work_unit, **kwargs):
                work_unit.transition(WorkStatus.EXECUTING)
                work_unit.transition(WorkStatus.VERIFYING)
                work_unit.transition(WorkStatus.COMPLETED)
                return ("selection", "result")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime(orchestrator=AutoOrchestrator())
            runtime.git.identity = lambda _: {
                "head": "a" * 40,
                "dirty": False,
            }
            work = WorkUnit("wu-auto-persist", "automatic workflow")
            result = runtime.run_auto(
                work,
                [],
                FakeExecutor(),
                project_root=root,
                repository_evidence=(),
            )
            persisted = runtime.state_store(root).load(work.id)

        self.assertEqual(result, ("selection", "result"))
        self.assertEqual(persisted.status, WorkStatus.COMPLETED)
        self.assertEqual(persisted.metadata["cwd"], str(root.resolve()))
        self.assertEqual(persisted.metadata["source_identity"]["head"], "a" * 40)

    def test_run_auto_persists_failed_work_unit_before_reraising(self):
        class FailingAutoOrchestrator:
            def run_auto(self, *, work_unit, **kwargs):
                work_unit.transition(WorkStatus.EXECUTING)
                work_unit.transition(WorkStatus.FAILED)
                work_unit.metadata["partial_progress"] = "agent selection completed"
                raise RuntimeError("automatic workflow failed")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime(orchestrator=FailingAutoOrchestrator())
            runtime.git.identity = lambda _: {
                "head": "b" * 40,
                "dirty": False,
            }
            work = WorkUnit("wu-auto-failed", "automatic workflow failure")
            with self.assertRaisesRegex(RuntimeError, "automatic workflow failed"):
                runtime.run_auto(
                    work,
                    [],
                    FakeExecutor(),
                    project_root=root,
                    repository_evidence=(),
                )
            persisted = runtime.state_store(root).load(work.id)

        self.assertEqual(persisted.status, WorkStatus.FAILED)
        self.assertEqual(persisted.metadata["error"], "automatic workflow failed")
        self.assertEqual(
            persisted.metadata["partial_progress"],
            "agent selection completed",
        )


    def test_run_adaptive_persists_completed_work_unit(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import runtime.agent_execution_runtime as runtime_module

        class Registry:
            def list(self):
                return []

        class Selector:
            def __init__(self, **kwargs):
                pass

            def select(self, *args, **kwargs):
                return SimpleNamespace(plan=object())

        class AdaptiveLoop:
            def __init__(self, **kwargs):
                pass

            def run(self, **kwargs):
                return (SimpleNamespace(success=True),)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime()
            runtime.workspace_identity = lambda _: {"head": "c" * 40, "dirty": False}
            work = WorkUnit("wu-adaptive-persist", "adaptive workflow")
            with patch.object(runtime_module, "build_registry", return_value=Registry()):
                with patch.object(runtime_module, "DeterministicAgentSelector", Selector):
                    with patch.object(runtime_module, "AdaptiveAgentExecutionLoop", AdaptiveLoop):
                        rounds = runtime.run_adaptive(root, work, [], {})

            persisted = runtime.state_store(root).load(work.id)

        self.assertEqual(len(rounds), 1)
        self.assertEqual(persisted.status, WorkStatus.COMPLETED)
        self.assertEqual(persisted.metadata["cwd"], str(root.resolve()))
        self.assertEqual(persisted.metadata["source_identity"]["head"], "c" * 40)

    def test_run_adaptive_persists_failed_work_unit_before_reraising(self):
        from unittest.mock import patch
        import runtime.agent_execution_runtime as runtime_module

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime()
            runtime.workspace_identity = lambda _: {"head": "d" * 40, "dirty": False}
            work = WorkUnit("wu-adaptive-failed", "adaptive workflow failure")
            with patch.object(runtime_module, "build_registry", side_effect=RuntimeError("adaptive selection failed")):
                with self.assertRaisesRegex(RuntimeError, "adaptive selection failed"):
                    runtime.run_adaptive(root, work, [], {})

            persisted = runtime.state_store(root).load(work.id)

        self.assertEqual(persisted.status, WorkStatus.FAILED)
        self.assertEqual(persisted.metadata["error"], "adaptive selection failed")
        self.assertEqual(persisted.metadata["cwd"], str(root.resolve()))

if __name__ == "__main__":
    unittest.main()

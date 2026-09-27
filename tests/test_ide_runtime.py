from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.ide import IDECommand, IDECommandKind, IDECommandResult, IDEContext, IDEEvent, IDEEventKind, IDEKind, IDEWorkRequest
from core.contracts.model_runtime import ModelResponse
from core.contracts.execution import AgentExecutor
from runtime.ide.registry import IDEAdapterRegistry
from runtime.ide.runtime import IDERuntime
from runtime.vyrelon import VYRELONRuntime


class FakeIDEAdapter:
    def __init__(self, kind: IDEKind) -> None:
        self._kind = kind

    @property
    def kind(self) -> IDEKind:
        return self._kind

    def capabilities(self) -> frozenset[str]:
        return frozenset({"context", "open_file"})

    def context(self) -> IDEContext:
        return IDEContext(kind=self._kind, project_root="/workspace")

    def execute(self, command: IDECommand) -> IDECommandResult:
        return IDECommandResult(ok=True, output=command.kind.value)


class IDERuntimeTests(unittest.TestCase):
    def test_registry_resolves_adapters_by_ide_kind(self) -> None:
        registry = IDEAdapterRegistry()
        xcode = FakeIDEAdapter(IDEKind.XCODE)
        vscode = FakeIDEAdapter(IDEKind.VS_CODE)
        registry.register(xcode)
        registry.register(vscode)
        self.assertIs(registry.get(IDEKind.XCODE), xcode)
        self.assertIs(registry.get(IDEKind.VS_CODE), vscode)
        self.assertEqual(registry.list(), (IDEKind.XCODE, IDEKind.VS_CODE))

    def test_runtime_delegates_to_adapter(self) -> None:
        runtime = IDERuntime()
        adapter = FakeIDEAdapter(IDEKind.VS_CODE)
        runtime.register(adapter)
        self.assertEqual(runtime.context(IDEKind.VS_CODE).kind, IDEKind.VS_CODE)
        result = runtime.execute(IDEKind.VS_CODE, IDECommand(kind=IDECommandKind.SHOW_MESSAGE))
        self.assertTrue(result.ok)

    def test_ide_event_is_distinct_from_vyrelon_command(self) -> None:
        runtime = IDERuntime()
        context = IDEContext(kind=IDEKind.VS_CODE, project_root="/workspace", file_path="/workspace/main.py")
        event = IDEEvent(kind=IDEEventKind.SELECTION_CHANGED, context=context, payload={"text": "hello"})
        self.assertIs(runtime.ingest_event(event), event)
        self.assertEqual(event.kind, IDEEventKind.SELECTION_CHANGED)

    def test_contract_is_provider_neutral(self) -> None:
        context = IDEContext(kind=IDEKind.ANDROID_STUDIO, project_root="/workspace", file_path="app/src/main/kotlin/Main.kt", selection_start=10, selection_end=20)
        command = IDECommand(kind=IDECommandKind.REPLACE_SELECTION, arguments={"text": "updated"}, context=context)
        self.assertEqual(command.context.kind, IDEKind.ANDROID_STUDIO)
        self.assertEqual(command.arguments["text"], "updated")



class FakeAgentExecutor(AgentExecutor):
    def execute(self, *, agent: AgentContract, model_id: str, work_unit):
        work_unit.metadata["executor_seen"] = True
        return ModelResponse(text=f"completed: {work_unit.objective}", model_id=model_id)


class IDEWorkExecutionTests(unittest.TestCase):
    def test_ide_work_reaches_agent_workunit_and_returns_to_ide(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = VYRELONRuntime()
            adapter = FakeIDEAdapter(IDEKind.VS_CODE)
            adapter.context = lambda: IDEContext(
                kind=IDEKind.VS_CODE,
                project_root=directory,
                file_path=str(Path(directory) / "main.py"),
            )
            runtime.ide.register(adapter)
            request = IDEWorkRequest(
                context=adapter.context(),
                objective="Explain the selected function",
                agent_id="coder",
                model_ids=("fake-model",),
            )

            runtime.agent_profile = lambda project_root, agent_id: AgentContract(
                id=agent_id,
                role="coder",
                model_ids=("fake-model",),
            )
            result = runtime.submit_ide_work(
                request,
                models=[ModelSpec(id="fake-model", provider_id="test")],
                executor=FakeAgentExecutor(),
            )

            work_unit = result["work_unit"]
            self.assertEqual(work_unit.status.value, "completed")
            self.assertTrue(work_unit.metadata["executor_seen"])
            self.assertEqual(work_unit.metadata["model_response"], "completed: Explain the selected function")
            ide_result = result["ide_result"]
            self.assertTrue(ide_result.ok)
            self.assertEqual(ide_result.output, "show_message")


if __name__ == "__main__":
    unittest.main()

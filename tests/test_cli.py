import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from core.chat_agent_bridge import ChatAgentResponse
from installer.init import ProjectInitializer
from multiagentos.cli import main
from runtime.status import project_status


class FakeChatAdapter:
    def __init__(self, label="fake"):
        self.label = label
        self.requests = []

    def respond(self, *, agent, instructions, request):
        self.requests.append(request)
        return ChatAgentResponse(summary=f"planned: {request.objective}", evidence=(self.label,))


class CLITests(unittest.TestCase):
    def test_detect(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.82.0"}}),
                encoding="utf-8",
            )
            self.assertEqual(main(["detect", str(root)]), 0)

    def test_status_uninitialized(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["status", temp]), 0)
            status = project_status(Path(temp))
            self.assertFalse(status["initialized"])
            self.assertEqual(status["components"], [])

    def test_status_reports_vyrelon_only(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)
            status = project_status(Path(temp))
            self.assertTrue(status["initialized"])
            self.assertEqual(status["components"], ["vyrelon"])
            self.assertEqual(status["agents"], [])
            self.assertEqual(status["chat"], {"agent_id": "chatgpt", "model": None})
            self.assertEqual(
                status["execution"],
                {"runtime": "process", "agent_id": "cli-executor", "model_id": "local-process"},
            )

    def test_status_reports_multi_agent_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["init", temp, "--component", "multi-agent"]), 0)
            status = project_status(Path(temp))
            self.assertTrue(status["initialized"])
            self.assertEqual(status["components"], ["multi-agent"])
            self.assertTrue(status["agents"])
            self.assertIsNone(status["execution"])

    def test_status_reports_durable_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)
            state = root / ".multiagentos" / "state"
            checkpoints = root / ".multiagentos" / "checkpoints"
            state.mkdir()
            checkpoints.mkdir()
            (state / "wu-1.json").write_text(json.dumps({
                "id": "wu-1", "objective": "demo", "status": "executing"
            }), encoding="utf-8")
            (checkpoints / "wu-1.json").write_text(json.dumps({
                "work_unit_id": "wu-1", "workflow": "orchestration",
                "stage": "executing", "status": "executing",
                "next_action": "resume_execution", "sequence": 2,
                "resumable": True
            }), encoding="utf-8")
            status = project_status(root)
            self.assertEqual(status["work_units"][0]["id"], "wu-1")
            self.assertEqual(status["checkpoints"][0]["next_action"], "resume_execution")

    def test_run_uses_project_execution_config(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)
            execution = root / ".multiagentos" / "execution.json"
            execution.write_text(json.dumps({
                "version": 1,
                "runtime": "process",
                "agent_id": "cli-executor",
                "model_id": "local-process",
            }), encoding="utf-8")
            self.assertEqual(
                main([
                    "run", "--path", temp, "--objective", "configured execution",
                    "--", "python", "-c", "print('ok')"
                ]),
                0,
            )
            state = project_status(root)
            self.assertEqual(state["work_units"][0]["status"], "completed")

    def test_run_supports_cli_agent_and_model_overrides(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)
            self.assertEqual(
                main([
                    "run", "--path", temp, "--agent", "cli-executor",
                    "--model", "local-process", "--objective", "override",
                    "--", "python", "-c", "print('ok')"
                ]),
                0,
            )
            state_path = next((root / ".multiagentos" / "state").glob("*.json"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["metadata"]["execution_agent_id"], "cli-executor")
            self.assertEqual(state["metadata"]["execution_model_id"], "local-process")

    def test_run_executes_command_and_persists_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)
            self.assertEqual(
                main(["run", "--path", temp, "--objective", "echo smoke test", "--", "python", "-c", "print('ok')"]),
                0,
            )
            status = project_status(root)
            self.assertEqual(len(status["work_units"]), 1)
            self.assertEqual(status["work_units"][0]["status"], "completed")
            self.assertEqual(status["checkpoints"][0]["resumable"], False)

    def test_resume_rejects_terminal_work_unit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)
            self.assertEqual(
                main(["run", "--path", temp, "--objective", "terminal", "--", "python", "-c", "print('done')"]),
                0,
            )
            work_unit_id = project_status(root)["work_units"][0]["id"]
            with self.assertRaises(ValueError):
                main(["resume", work_unit_id, "--path", temp])

    def test_chat_uses_configured_chat_agent_and_persists_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)

            import multiagentos.cli as cli_module
            original = cli_module.VYRELONRuntime.project_chat_adapter
            cli_module.VYRELONRuntime.project_chat_adapter = lambda self, project_root: (
                self, FakeChatAdapter()
            )
            try:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(
                        main([
                            "chat", "--path", temp, "--objective", "inspect this project",
                            "--session", "session-1"
                        ]),
                        0,
                    )
            finally:
                cli_module.VYRELONRuntime.project_chat_adapter = original

            payload = json.loads(output.getvalue())
            self.assertEqual(payload["chat_agent_id"], "chatgpt")
            self.assertEqual(payload["summary"], "planned: inspect this project")
            self.assertEqual(payload["session_id"], "session-1")
            session_path = root / ".multiagentos" / "sessions" / "session-1.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual([turn["role"] for turn in session["turns"]], ["user", "assistant"])

    def test_chat_execute_runs_explicit_command_through_vyrelon(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)

            import multiagentos.cli as cli_module
            from core.chat_agent_bridge import ChatAgentResponse

            class FakeAdapter:
                def respond(self, *, agent, instructions, request):
                    return ChatAgentResponse(
                        summary="execution plan prepared",
                        evidence=("fake chat response",),
                    )

            original = cli_module.VYRELONRuntime.project_chat_adapter
            cli_module.VYRELONRuntime.project_chat_adapter = lambda self, project_root: FakeAdapter()
            try:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(
                        main([
                            "chat", "--path", temp, "--execute",
                            "--objective", "run the smoke command",
                            "--session", "exec-1",
                            "--", "python", "-c", "print('chat-executed')",
                        ]),
                        0,
                    )
            finally:
                cli_module.VYRELONRuntime.project_chat_adapter = original

            payload = json.loads(output.getvalue())
            self.assertEqual(payload["mode"], "execute")
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["execution_agent_id"], "cli-executor")
            self.assertEqual(payload["execution_model_id"], "local-process")
            self.assertTrue(payload["execution_evidence"])
            state = project_status(root)
            self.assertEqual(len(state["work_units"]), 1)
            self.assertEqual(state["work_units"][0]["status"], "completed")
            session = json.loads(
                (root / ".multiagentos" / "sessions" / "exec-1.json").read_text(encoding="utf-8")
            )
            self.assertEqual(session["work_unit_id"], state["work_units"][0]["id"])

    def test_init(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["init", temp]), 0)
            self.assertTrue((Path(temp) / ".multiagentos" / "profile.json").exists())
            self.assertTrue((Path(temp) / ".multiagentos" / "agents.json").exists())
            self.assertTrue((Path(temp) / ".multiagentos" / "execution.json").exists())
            self.assertTrue((Path(temp) / ".multiagentos" / "chat.json").exists())


if __name__ == "__main__":
    unittest.main()

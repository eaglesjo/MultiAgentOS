import tempfile
import unittest
from pathlib import Path

from core.chat_agent_bridge import ChatAgentRequest, ChatAgentResponse
from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import ReviewDecision
from installer.init import ProjectInitializer
from runtime.chat_execution import execute_project_chat_request


class FakeChatAdapter:
    def respond(self, *, agent, instructions, request):
        return ChatAgentResponse(summary="planned", evidence=("adapter response",))


class Executor:
    def execute(self, *, agent, model_id, work_unit):
        return {"ok": True, "model": model_id}


class Verifier:
    def verify(self, *, work_unit, output):
        return True


class Reviewer:
    def review(self, *, work_unit, output):
        return ReviewDecision(approved=True, feedback="approved")


class ProjectChatExecutionTests(unittest.TestCase):
    def test_project_chat_request_uses_vyrelon_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ProjectInitializer().apply(root, component="vyrelon")
            # Replace the provider adapter resolution with a deterministic fake
            # while retaining the real project Chat Agent configuration.
            import runtime.chat_execution as module
            original = module.VYRELONRuntime.project_chat_adapter
            module.VYRELONRuntime.project_chat_adapter = lambda self, project_root: FakeChatAdapter()
            try:
                result = execute_project_chat_request(
                    root,
                    ChatAgentRequest(objective="execute the configured project task"),
                    agent=AgentContract(
                        id="developer",
                        role="developer",
                        capabilities=frozenset({"code"}),
                    ),
                    models=[ModelSpec("cloud-code", "provider", frozenset({"code"}))],
                    executor=Executor(),
                    verifier=Verifier(),
                    reviewer=Reviewer(),
                )
            finally:
                module.VYRELONRuntime.project_chat_adapter = original

            self.assertEqual(result.work_unit.status.value, "completed")
            self.assertEqual(result.work_unit.metadata["execution_authority"], "vyrelon")
            self.assertEqual(result.orchestration.delegation.assignment.model_id, "cloud-code")


if __name__ == "__main__":
    unittest.main()

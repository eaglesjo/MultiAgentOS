import unittest

from core.chat_agent_bridge import (
    ChatAgentBridge,
    ChatAgentRequest,
    ChatAgentResponse,
    VYRELON_AGENT_RULES,
)
from core.chat_agent_registry import default_chat_agents
from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.planning import PlanStep
from core.contracts.work_unit import WorkStatus
from core.contracts.execution import ReviewDecision


class FakeChatAgent:
    def __init__(self):
        self.instructions = None

    def respond(self, *, agent, instructions, request):
        self.instructions = instructions
        return ChatAgentResponse(
            summary="plan prepared",
            steps=(PlanStep(id="inspect", objective="Inspect the repository"),),
            findings=("repository state must be inspected first",),
            evidence=("request accepted by adapter",),
        )


class RecordingExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, *, agent, model_id, work_unit):
        self.calls.append((agent.id, model_id, work_unit.id))
        return {"status": "ok"}


class PassingVerifier:
    def verify(self, *, work_unit, output):
        return True


class PassingReviewer:
    def review(self, *, work_unit, output):
        return ReviewDecision(approved=True, feedback="approved")


class TestChatAgentBridge(unittest.TestCase):
    def test_primary_chatgpt_receives_vyrelon_rules(self):
        adapter = FakeChatAgent()
        bridge = ChatAgentBridge(default_chat_agents())

        work_unit, plan, _ = bridge.request(
            ChatAgentRequest(
                objective="Inspect the repository and prepare the next change."
            ),
            adapter,
        )

        self.assertEqual(work_unit.metadata["chat_agent_id"], "chatgpt")
        self.assertEqual(plan.steps[0].id, "inspect")
        for rule in VYRELON_AGENT_RULES:
            self.assertIn(rule, adapter.instructions)

    def test_another_chat_agent_can_drive_the_bridge(self):
        adapter = FakeChatAgent()
        bridge = ChatAgentBridge(default_chat_agents())

        work_unit, _, _ = bridge.request(
            ChatAgentRequest(objective="Review the current implementation."),
            adapter,
            agent_id="gemini",
        )

        self.assertEqual(work_unit.metadata["chat_agent_id"], "gemini")

    def test_instruction_lookup_uses_primary_by_default(self):
        bridge = ChatAgentBridge(default_chat_agents())
        self.assertIn("ChatGPT Agent", bridge.instructions())

    def test_chat_agent_request_can_enter_full_vyrelon_execution(self):
        adapter = FakeChatAgent()
        executor = RecordingExecutor()
        agent = AgentContract(
            id="developer",
            role="developer",
            capabilities=frozenset({"code"}),
        )
        models = [
            ModelSpec("cloud-code", "provider-a", frozenset({"code"})),
        ]
        bridge = ChatAgentBridge(default_chat_agents())

        result = bridge.execute(
            ChatAgentRequest(objective="Implement the requested change."),
            adapter,
            agent,
            models,
            executor,
            verifier=PassingVerifier(),
            reviewer=PassingReviewer(),
        )

        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
        self.assertEqual(
            executor.calls,
            [("developer", "cloud-code", result.work_unit.id)],
        )
        self.assertEqual(
            result.work_unit.metadata["execution_authority"],
            "vyrelon",
        )
        self.assertEqual(
            result.work_unit.metadata["verification_evidence"],
            ["VYRELON verifier accepted output"],
        )
        self.assertEqual(
            result.work_unit.metadata["review_evidence"],
            ["VYRELON reviewer approved output"],
        )


if __name__ == "__main__":
    unittest.main()

    
    def test_execution_checkpoint_can_resume(self):
        from pathlib import Path
        import tempfile
        from core.state import WorkStateStore
        from core.contracts.agent import AgentContract
        from core.contracts.ai import ModelSpec

        from core.lifecycle import ExecutionInterrupted

        class InterruptingExecutor:
            def execute(self, *, agent, model_id, work_unit):
                raise ExecutionInterrupted("simulated interruption")

        class PassingExecutor:
            def execute(self, *, agent, model_id, work_unit):
                return {"status": "resumed"}

        agent = AgentContract(id="developer", role="developer")
        models = [ModelSpec("cloud", "provider", frozenset())]
        bridge = ChatAgentBridge(default_chat_agents())

        with tempfile.TemporaryDirectory() as directory:
            store = WorkStateStore(Path(directory))
            request = ChatAgentRequest(
                objective="Resume this task.",
                work_unit_id="chat-resume-001",
            )
            with self.assertRaises(RuntimeError):
                bridge.execute(
                    request,
                    FakeChatAgent(),
                    agent,
                    models,
                    InterruptingExecutor(),
                    state_store=store,
                )

            saved = store.load("chat-resume-001")
            self.assertEqual(saved.status.value, "executing")
            self.assertEqual(saved.metadata["checkpoint"]["status"], "executing")

            result = bridge.resume(
                "chat-resume-001",
                state_store=store,
                agent=agent,
                models=models,
                executor=PassingExecutor(),
            )
            self.assertEqual(result.work_unit.status.value, "completed")

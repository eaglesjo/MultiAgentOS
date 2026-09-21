import unittest

from core.chat_agent_bridge import (
    ChatAgentBridge,
    ChatAgentRequest,
    ChatAgentResponse,
    VYRELON_AGENT_RULES,
)
from core.chat_agent_registry import default_chat_agents
from core.contracts.planning import PlanStep


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


if __name__ == "__main__":
    unittest.main()

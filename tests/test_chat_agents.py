import unittest

from core.chat_agent_registry import ChatAgentRegistry, default_chat_agents
from core.contracts.chat_agent import ChatAgentContract, ChatAgentProvider


class TestChatAgents(unittest.TestCase):
    def test_chatgpt_is_primary(self):
        registry = default_chat_agents()
        self.assertEqual(registry.primary().id, "chatgpt")

    def test_other_chat_agents_can_coexist(self):
        registry = default_chat_agents()
        self.assertEqual(
            {agent.id for agent in registry.list()},
            {"chatgpt", "gemini", "claude"},
        )

    def test_non_chatgpt_cannot_be_primary(self):
        with self.assertRaises(ValueError):
            ChatAgentContract(
                id="gemini-primary",
                provider=ChatAgentProvider.GEMINI,
                name="Gemini Agent",
                primary=True,
            ).validate()

    def test_registry_rejects_duplicate(self):
        registry = ChatAgentRegistry()
        agent = ChatAgentContract(
            id="chatgpt",
            provider=ChatAgentProvider.CHATGPT,
            name="ChatGPT Agent",
            primary=True,
        )
        registry.register(agent)
        with self.assertRaises(ValueError):
            registry.register(agent)


if __name__ == "__main__":
    unittest.main()

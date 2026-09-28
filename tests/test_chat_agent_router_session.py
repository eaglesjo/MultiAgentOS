import tempfile
import unittest
from pathlib import Path

from core.chat_agent_registry import default_chat_agents
from core.chat_agent_router import ChatAgentRouter, ChatAgentRoutingStrategy
from core.chat_session import ChatSession, ChatSessionStore


class ChatAgentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = ChatAgentRouter(default_chat_agents())

    def test_auto_prefers_primary_chatgpt(self):
        assignment = self.router.route(
            required_capabilities=frozenset({"conversation"})
        )
        self.assertEqual(assignment.agent.id, "chatgpt")
        self.assertEqual(assignment.strategy, ChatAgentRoutingStrategy.AUTO)

    def test_explicit_provider(self):
        assignment = self.router.route(
            preferred_agent_id="gemini",
            strategy=ChatAgentRoutingStrategy.EXPLICIT,
        )
        self.assertEqual(assignment.agent.id, "gemini")

    def test_fallback_uses_first_compatible_candidate(self):
        assignment = self.router.route(
            preferred_agent_id="gemini",
            fallback_agent_ids=("claude", "chatgpt"),
            required_capabilities=frozenset({"orchestration"}),
            strategy=ChatAgentRoutingStrategy.FALLBACK,
        )
        self.assertEqual(assignment.agent.id, "chatgpt")

    def test_incompatible_capability_fails(self):
        with self.assertRaises(LookupError):
            self.router.route(
                preferred_agent_id="gemini",
                required_capabilities=frozenset({"orchestration"}),
                strategy=ChatAgentRoutingStrategy.EXPLICIT,
            )


class ChatSessionStoreTests(unittest.TestCase):
    def test_session_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ChatSessionStore(Path(directory))
            session = ChatSession(
                id="session-001",
                chat_agent_id="chatgpt",
                work_unit_id="wu-001",
            )
            session.add_turn("user", "Inspect the repository.")
            session.add_turn("assistant", "Inspection requested.")
            path = store.save(session)

            restored = store.load("session-001")

            self.assertTrue(path.exists())
            self.assertEqual(restored.chat_agent_id, "chatgpt")
            self.assertEqual(restored.work_unit_id, "wu-001")
            self.assertEqual(len(restored.turns), 2)


if __name__ == "__main__":
    unittest.main()

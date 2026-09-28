import unittest

from core.contracts.chat_agent import ChatAgentProvider
from runtime.chat_adapter_registry import (
    ChatAdapterRegistry,
    default_chat_adapters,
)


class ChatAdapterRegistryTests(unittest.TestCase):
    def test_chatgpt_resolves_to_openai_adapter(self):
        adapter = default_chat_adapters().create(ChatAgentProvider.CHATGPT, model="test-model")
        self.assertEqual(adapter.model, "test-model")

    def test_unregistered_provider_is_rejected(self):
        registry = ChatAdapterRegistry()
        with self.assertRaises(LookupError):
            registry.create(ChatAgentProvider.GEMINI)

    def test_custom_provider_adapter_can_be_registered(self):
        registry = ChatAdapterRegistry()
        registry.register(ChatAgentProvider.GEMINI, lambda *, model=None: ("gemini", model))
        self.assertEqual(
            registry.create(ChatAgentProvider.GEMINI, model="gemini-test"),
            ("gemini", "gemini-test"),
        )

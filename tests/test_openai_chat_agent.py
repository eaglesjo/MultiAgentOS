import unittest

from integrations.openai.chat_agent import OpenAIChatAgentAdapter
from core.chat_agent_bridge import ChatAgentRequest
from core.chat_agent_registry import default_chat_agents


class FakeResponses:
    def __init__(self, text):
        self.text = text

    def create(self, **kwargs):
        self.kwargs = kwargs
        return type("Response", (), {"output_text": self.text})()


class FakeClient:
    def __init__(self, text):
        self.responses = FakeResponses(text)


class TestOpenAIChatAgentAdapter(unittest.TestCase):
    def test_structured_response(self):
        client = FakeClient(
            '{"summary":"inspect first","steps":[{"id":"inspect","objective":"Inspect the repository"}],"findings":["start with state"]}'
        )
        adapter = OpenAIChatAgentAdapter(client=client, model="test-model")
        result = adapter.respond(
            agent=default_chat_agents().get("chatgpt"),
            instructions="VYRELON rules",
            request=ChatAgentRequest(objective="Inspect the repository"),
        )
        self.assertEqual(result.summary, "inspect first")
        self.assertEqual(result.steps[0].id, "inspect")
        self.assertEqual(client.responses.kwargs["model"], "test-model")
        self.assertIn("VYRELON rules", client.responses.kwargs["instructions"])

    def test_invalid_json_falls_back_to_non_execution_step(self):
        adapter = OpenAIChatAgentAdapter(
            client=FakeClient("not json"),
            model="test-model",
        )
        result = adapter.respond(
            agent=default_chat_agents().get("chatgpt"),
            instructions="VYRELON rules",
            request=ChatAgentRequest(objective="Inspect"),
        )
        self.assertEqual(result.steps[0].objective, "Inspect")


if __name__ == "__main__":
    unittest.main()

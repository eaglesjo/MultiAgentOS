import unittest

from core.contracts import AgentContract, AIProvider, ModelRequest, ModelResponse, ModelSpec, WorkUnit
from core.registry import AIRegistry
from runtime.agent.model_backed import ModelBackedAgentExecutor
from runtime.model.invoker import ModelInvoker
from runtime.model.registry import ModelAdapterRegistry


class RecordingAdapter:
    def generate(self, model, request):
        return ModelResponse(
            text=f"{model.id}|{request.metadata['agent_id']}|{request.prompt}",
            model_id=model.id,
        )


class ModelBackedAgentTests(unittest.TestCase):
    def test_agent_executes_through_selected_model_adapter(self):
        ai = AIRegistry()
        ai.register(
            AIProvider(
                id="provider-a",
                kind="test",
                models=(
                    ModelSpec("model-a", "provider-a", frozenset({"code"}), {"adapter_id": "test"}),
                ),
            )
        )
        adapters = ModelAdapterRegistry()
        adapters.register("test", RecordingAdapter())

        executor = ModelBackedAgentExecutor(ai, ModelInvoker(adapters))
        result = executor.execute(
            agent=AgentContract(
                id="developer", role="developer",
                capabilities=frozenset({"code"}),
            ),
            model_id="model-a",
            work_unit=WorkUnit(
                id="wu-agent",
                objective="implement feature",
                inputs={"language": "python"},
            ),
        )

        self.assertEqual(result.model_id, "model-a")
        self.assertIn("developer", result.text)
        self.assertIn("implement feature", result.text)


if __name__ == "__main__":
    unittest.main()

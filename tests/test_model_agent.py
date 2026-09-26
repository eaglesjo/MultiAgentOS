from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse


class FakeAdapter:
    def __init__(self):
        self.requests = []

    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        self.requests.append((model, request))
        return ModelResponse(
            text="model-output",
            model_id=model.id,
            metadata={"adapter": "fake"},
        )


def test_model_agent_executor_routes_model_and_persists_response():
    from core.contracts.agent import AgentContract
    from core.contracts.work_unit import WorkUnit
    from runtime.agent.model import ModelAgentExecutor

    model = ModelSpec(
        id="test-model",
        provider_id="test-provider",
        capabilities=frozenset({"execution"}),
        metadata={"adapter_id": "fake"},
    )
    adapter = FakeAdapter()
    executor = ModelAgentExecutor(
        {"fake": adapter},
        [model],
        system_prompt="You are the executor.",
    )
    agent = AgentContract(
        id="executor",
        role="executor",
        capabilities=frozenset({"execution"}),
        model_ids=("test-model",),
    )
    work = WorkUnit("wu-model", "Explain the task")
    response = executor.execute(agent=agent, model_id="test-model", work_unit=work)

    assert response.text == "model-output"
    assert work.metadata["model_response"] == "model-output"
    assert work.metadata["model_adapter"] == "fake"
    assert adapter.requests[0][1].system == "You are the executor."

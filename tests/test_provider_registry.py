from core.contracts.ai import AIProvider, ModelSpec
from core.contracts.agent import AgentContract
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.work_unit import WorkUnit
from runtime.model.providers import AIProviderRegistry
from runtime.vyrelon import VYRELONRuntime


class FakeAdapter:
    def generate(self, model: ModelSpec, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            text=f"response:{model.id}",
            model_id=model.id,
            metadata={"adapter": "fake"},
        )


def test_provider_registry_resolves_provider_and_models():
    model = ModelSpec(
        id="provider-a-model",
        provider_id="provider-a",
        metadata={"adapter_id": "fake"},
    )
    provider = AIProvider(
        id="provider-a",
        kind="http",
        models=(model,),
        metadata={"display_name": "Provider A"},
    )
    registry = AIProviderRegistry()
    registry.register(provider)

    assert registry.get_provider("provider-a") == provider
    assert registry.get_model("provider-a-model") == model
    assert registry.list_provider_ids() == ("provider-a",)
    assert registry.list_model_ids() == ("provider-a-model",)


def test_provider_registry_rejects_model_owned_by_another_provider():
    model = ModelSpec(id="wrong-owner", provider_id="provider-b")
    provider = AIProvider(id="provider-a", kind="http", models=(model,))
    registry = AIProviderRegistry()

    try:
        registry.register(provider)
    except ValueError as exc:
        assert "belongs to provider-b" in str(exc)
    else:
        raise AssertionError("expected provider ownership validation")


def test_vyrelon_runs_registered_provider_model_configuration():
    model = ModelSpec(
        id="registered-model",
        provider_id="provider-a",
        capabilities=frozenset({"execution"}),
        metadata={"adapter_id": "fake"},
    )
    provider = AIProvider(
        id="provider-a",
        kind="http",
        models=(model,),
    )
    runtime = VYRELONRuntime()
    runtime.register_provider(provider)
    runtime.register_model_adapter("fake", FakeAdapter())

    agent = AgentContract(
        id="executor",
        role="executor",
        capabilities=frozenset({"execution"}),
        model_ids=("registered-model",),
    )
    work = WorkUnit("wu-registered", "Run registered model")

    result = runtime.run_registered_model(
        work_unit=work,
        agent=agent,
        preferred_model_ids=["registered-model"],
    )

    assert result.output.text == "response:registered-model"
    assert result.delegation.model_id == "registered-model"
    assert work.metadata["model_id"] == "registered-model"


def test_vyrelon_rejects_unknown_registered_model():
    runtime = VYRELONRuntime()
    work = WorkUnit("wu-missing", "Run missing model")
    agent = AgentContract(id="executor", role="executor")

    try:
        runtime.run_registered_model(
            work_unit=work,
            agent=agent,
            preferred_model_ids=["missing-model"],
        )
    except LookupError as exc:
        assert "Model not registered" in str(exc)
    else:
        raise AssertionError("expected unknown model validation")

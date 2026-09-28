from core.contracts.ai import ModelSpec
from core.contracts.agent import AgentContract
from core.routing import AIRouter
from runtime.capability import CapabilityRegistry, CapabilityStore


def test_registry_persists_declared_capabilities(tmp_path):
    registry = CapabilityRegistry(CapabilityStore(tmp_path / "capabilities"))
    model = ModelSpec(
        id="rn-model",
        provider_id="test",
        capabilities=frozenset({"execution", "code", "react-native"}),
    )
    profile = registry.profile(model)
    assert profile.capabilities == model.capabilities
    assert registry.store.exists(model.id)


def test_router_uses_capability_fit_before_quota(tmp_path):
    registry = CapabilityRegistry(CapabilityStore(tmp_path / "capabilities"))
    router = AIRouter()
    agent = AgentContract(
        id="developer",
        role="developer",
        capabilities=frozenset({"execution", "code", "react-native"}),
    )
    models = [
        ModelSpec(
            id="generic",
            provider_id="a",
            capabilities=frozenset({"execution", "code", "react-native"}),
        ),
        ModelSpec(
            id="missing-rn",
            provider_id="b",
            capabilities=frozenset({"execution", "code"}),
        ),
    ]
    assignment = router.assign(
        agent,
        models,
        capability_registry=registry,
    )
    assert assignment.model_id == "generic"


def test_router_rejects_missing_required_capability(tmp_path):
    registry = CapabilityRegistry(CapabilityStore(tmp_path / "capabilities"))
    router = AIRouter()
    agent = AgentContract(
        id="ios",
        role="ios",
        capabilities=frozenset({"code", "swift"}),
    )
    models = [
        ModelSpec(id="python", provider_id="a", capabilities=frozenset({"code", "python"})),
        ModelSpec(id="swift", provider_id="b", capabilities=frozenset({"code", "swift"})),
    ]
    assert router.assign(agent, models, capability_registry=registry).model_id == "swift"

from agents.registry import build_registry
from core.contracts.agent_capability import AgentCapabilityProfile
from runtime.agent_capability import AgentCapabilityRegistry


def test_registry_builds_profiles_from_agent_catalog():
    registry = AgentCapabilityRegistry(build_registry())
    profile = registry.profile("react-native-developer")
    assert isinstance(profile, AgentCapabilityProfile)
    assert "react-native" in profile.capabilities
    assert "filesystem.write" in profile.tools


def test_registry_explains_missing_agent_capabilities():
    registry = AgentCapabilityRegistry(build_registry())
    match = registry.match(
        "ios-developer",
        capabilities=frozenset({"code", "swift", "react-native"}),
        tools=frozenset({"filesystem.write"}),
    )
    assert not match.compatible
    assert match.missing_capabilities == frozenset({"react-native"})
    assert match.missing_tools == frozenset()


def test_registry_returns_only_compatible_agents():
    registry = AgentCapabilityRegistry(build_registry())
    profiles = registry.compatible(
        capabilities=frozenset({"code", "react-native"}),
        tools=frozenset({"filesystem.write"}),
    )
    ids = {profile.agent_id for profile in profiles}
    assert "react-native-developer" in ids
    assert "ios-developer" not in ids
    assert "android-developer" not in ids


def test_registry_preserves_agent_model_preferences():
    from core.contracts.agent import AgentContract
    agent = AgentContract(
        id="model-aware-agent",
        role="developer",
        capabilities=frozenset({"code"}),
        model_ids=("model-a", "model-b"),
    )
    registry = AgentCapabilityRegistry()
    registry.register(agent)
    assert registry.profile(agent.id).model_ids == ("model-a", "model-b")

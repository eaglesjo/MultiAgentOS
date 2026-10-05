from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.agent_model_resolver import AgentModelResolver
from runtime.capability import CapabilityRegistry, CapabilityStore


def test_resolver_enforces_agent_model_allowlist(tmp_path):
    agent = AgentContract("rn", "developer", frozenset({"code", "react-native"}), model_ids=("preferred",))
    models = [ModelSpec("preferred", "a", frozenset({"code", "react-native"})),
              ModelSpec("stronger-but-forbidden", "b", frozenset({"code", "react-native", "tools"}))]
    result = AgentModelResolver().resolve(agent, models)
    assert result.model_id == "preferred"
    assert [item.model_id for item in result.explanation.candidates] == ["preferred"]


def test_resolver_uses_capability_registry_for_agent_model_fit(tmp_path):
    registry = CapabilityRegistry(CapabilityStore(tmp_path / "capabilities"))
    agent = AgentContract("developer", "developer", frozenset({"code", "react-native"}))
    models = [ModelSpec("generic", "a", frozenset({"code"})),
              ModelSpec("rn", "b", frozenset({"code", "react-native"}))]
    result = AgentModelResolver().resolve(agent, models, capability_registry=registry)
    assert result.model_id == "rn"


def test_resolver_exposes_rejection_reason_for_incompatible_model():
    agent = AgentContract("ios", "developer", frozenset({"code", "swift"}))
    models = [ModelSpec("python", "a", frozenset({"code", "python"})),
              ModelSpec("swift", "b", frozenset({"code", "swift"}))]
    result = AgentModelResolver().resolve(agent, models)
    rejected = next(item for item in result.explanation.candidates if item.model_id == "python")
    assert rejected.compatible is False
    assert "missing_capabilities" in rejected.rejection_reasons

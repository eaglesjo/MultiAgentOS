import os
from unittest.mock import patch

from core.contracts.ai import AIProvider, ModelSpec
from runtime.model.materializer import NativeProviderMaterializer
from runtime.policy import ExecutionPolicy


def provider(kind, provider_id):
    return AIProvider(
        id=provider_id,
        kind=kind,
        models=(ModelSpec(f"{provider_id}-model", provider_id, metadata={"adapter_id": provider_id}),),
    )


def test_materializer_builds_all_native_adapters():
    result = NativeProviderMaterializer(
        policy=ExecutionPolicy(allow_network=True)
    ).materialize(
        (provider("openai", "oai"), provider("anthropic", "claude"), provider("gemini", "google"))
    )
    assert result.adapters.list() == ("oai", "claude", "google")


def test_materializer_validates_credentials_without_exposing_values():
    providers = (
        AIProvider(
            id="oai",
            kind="openai",
            models=(),
            metadata={"api_key_env": "CUSTOM_OPENAI_KEY"},
        ),
    )
    with patch.dict(os.environ, {"CUSTOM_OPENAI_KEY": "secret-value"}):
        result = NativeProviderMaterializer().materialize(
            providers, validate_credentials=True
        )
    assert result.credential_checks[0].environment_variable == "CUSTOM_OPENAI_KEY"
    assert result.credential_checks[0].present is True
    assert "secret-value" not in repr(result.credential_checks)


def test_materialized_openai_adapter_uses_declared_endpoint_and_key_env():
    provider_config = AIProvider(
        id="oai",
        kind="openai",
        models=(ModelSpec("gpt-test", "oai", metadata={"adapter_id": "oai"}),),
        metadata={"endpoint": "http://localhost/test", "api_key_env": "MY_KEY"},
    )
    result = NativeProviderMaterializer(
        policy=ExecutionPolicy(allow_network=True)
    ).materialize((provider_config,))
    adapter = result.adapters.get("oai")
    assert adapter.endpoint == "http://localhost/test"
    assert adapter.api_key_env == "MY_KEY"

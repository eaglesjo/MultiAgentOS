import json
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.model.runtime_loader import ProviderRuntimeLoader
from runtime.policy import ExecutionPolicy


def test_provider_runtime_loader_connects_config_registry_and_adapters():
    payload = {
        "providers": [
            {
                "id": "oai",
                "kind": "openai",
                "metadata": {"api_key_env": "TEST_KEY"},
                "models": [
                    {
                        "id": "model",
                        "capabilities": ["tool_calling"],
                        "metadata": {"adapter_id": "oai"},
                    }
                ],
            }
        ]
    }
    with TemporaryDirectory() as directory:
        path = Path(directory) / "providers.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        runtime = ProviderRuntimeLoader(
            policy=ExecutionPolicy(allow_network=True)
        ).load(path)
    assert runtime.providers.get_model("model").provider_id == "oai"
    assert runtime.adapters.get("oai").api_key_env == "TEST_KEY"

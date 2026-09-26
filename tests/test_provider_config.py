import json
from pathlib import Path
from tempfile import TemporaryDirectory

from core.contracts.ai import AIProvider
from runtime.model.config import ProviderConfigLoader
from runtime.model.providers import AIProviderRegistry


def test_provider_config_loader_builds_registry():
    payload = {
        "providers": [
            {
                "id": "provider-a",
                "kind": "http",
                "metadata": {"environment": "test"},
                "models": [
                    {
                        "id": "model-a",
                        "capabilities": ["execution", "reasoning"],
                        "metadata": {"adapter_id": "fake"},
                    }
                ],
            }
        ]
    }

    with TemporaryDirectory() as directory:
        path = Path(directory) / "providers.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        registry = ProviderConfigLoader().load(path)

    assert registry.list_provider_ids() == ("provider-a",)
    assert registry.list_model_ids() == ("model-a",)
    assert registry.get_model("model-a").provider_id == "provider-a"
    assert registry.get_model("model-a").metadata["adapter_id"] == "fake"


def test_provider_config_loader_reuses_existing_registry():
    registry = AIProviderRegistry()
    registry.register(AIProvider(id="existing", kind="cli"))

    with TemporaryDirectory() as directory:
        path = Path(directory) / "providers.json"
        path.write_text(
            json.dumps(
                {
                    "providers": [
                        {
                            "id": "loaded",
                            "kind": "http",
                            "models": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        loaded = ProviderConfigLoader().load(path, registry)

    assert loaded is registry
    assert loaded.list_provider_ids() == ("existing", "loaded")


def test_provider_config_loader_rejects_invalid_root():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "providers.json"
        path.write_text("[]", encoding="utf-8")
        try:
            ProviderConfigLoader().load(path)
        except ValueError as exc:
            assert "root must be an object" in str(exc)
        else:
            raise AssertionError("expected invalid root error")

import unittest

from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from runtime.model.cli import CLIModelAdapter
from runtime.model.invoker import ModelInvoker
from runtime.model.registry import ModelAdapterRegistry


class EchoAdapter:
    def generate(self, model, request):
        return ModelResponse(text=request.prompt, model_id=model.id)


class ModelRuntimeTests(unittest.TestCase):
    def test_registry_and_invoker(self):
        registry = ModelAdapterRegistry()
        registry.register("echo", EchoAdapter())
        model = ModelSpec("model-a", "provider-a", metadata={"adapter_id": "echo"})

        response = ModelInvoker(registry).generate(
            model, ModelRequest(prompt="hello")
        )
        self.assertEqual(response.text, "hello")
        self.assertEqual(response.model_id, "model-a")

    def test_generic_cli_adapter(self):
        model = ModelSpec("local-cli", "local")
        response = CLIModelAdapter(
            command=("python", "-c", "import sys; print(sys.stdin.read().upper())")
        ).generate(model, ModelRequest(prompt="hello"))
        self.assertEqual(response.text.strip(), "HELLO")

    def test_registry_rejects_duplicate_adapter(self):
        registry = ModelAdapterRegistry()
        registry.register("echo", EchoAdapter())
        with self.assertRaises(ValueError):
            registry.register("echo", EchoAdapter())


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from unittest.mock import patch

from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest
from runtime.model.http import HTTPModelAdapter
from runtime.policy import ExecutionPolicy


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({"result": {"text": "hello"}}).encode("utf-8")


class HTTPModelAdapterTests(unittest.TestCase):
    def test_generic_json_endpoint(self):
        adapter = HTTPModelAdapter(
            endpoint="https://example.invalid/model",
            request_template={
                "model": "{model_id}",
                "input": {"prompt": "{prompt}", "system": "{system}"},
            },
            response_path=("result", "text"),
        )
        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = adapter.generate(
                ModelSpec("model-a", "provider-a"),
                ModelRequest(prompt="hello", system="system"),
            )
        self.assertEqual(result.text, "hello")

    def test_network_policy_can_disable_adapter(self):
        adapter = HTTPModelAdapter(
            endpoint="https://example.invalid/model",
            policy=ExecutionPolicy(allow_network=False),
        )
        with self.assertRaises(PermissionError):
            adapter.generate(ModelSpec("model-a", "provider-a"), ModelRequest(prompt="hello"))


if __name__ == "__main__":
    unittest.main()

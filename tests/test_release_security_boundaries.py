import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from unittest.mock import patch

from runtime.model.native import OpenAIResponsesToolAdapter
from runtime.discovery import ProviderDiscoveryAdapter
from runtime.policy import ExecutionPolicy


class ReleaseSecurityBoundaryTests(unittest.TestCase):
    def test_native_http_error_does_not_expose_api_key(self):
        adapter = OpenAIResponsesToolAdapter(
            policy=ExecutionPolicy(allow_network=True)
        )
        request = __import__("core.contracts.model_runtime", fromlist=["ModelRequest"]).ModelRequest(prompt="ping")
        model = __import__("core.contracts.ai", fromlist=["ModelSpec"]).ModelSpec(
            "gpt-test", "openai", frozenset({"chat"})
        )
        error = HTTPError(
            "https://api.openai.com/v1/responses?key=SECRET_SHOULD_NOT_LEAK",
            401,
            "unauthorized",
            {},
            __import__("io").BytesIO(b"secret")
        )
        with patch("runtime.model.native.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                adapter.generate(model, request)
        self.assertNotIn("SECRET_SHOULD_NOT_LEAK", str(caught.exception))

    def test_discovery_http_error_does_not_expose_api_key(self):
        adapter = ProviderDiscoveryAdapter(
            policy=ExecutionPolicy(allow_network=True)
        )
        provider = __import__("core.contracts.ai", fromlist=["AIProvider"]).AIProvider(
            id="gemini",
            kind="gemini",
            models=(),
            metadata={},
        )
        error = HTTPError(
            "https://generativelanguage.googleapis.com/v1beta/models?key=SECRET_SHOULD_NOT_LEAK",
            403,
            "forbidden",
            {},
            __import__("io").BytesIO(b"secret")
        )
        with patch("runtime.discovery.urllib.request.urlopen", side_effect=error):
            with patch.dict("os.environ", {"GEMINI_API_KEY": "SECRET_SHOULD_NOT_LEAK"}):
                result, discovery_error = adapter.discover_safe(provider)
        self.assertIsNone(result)
        self.assertIsNotNone(discovery_error)
        self.assertNotIn("SECRET_SHOULD_NOT_LEAK", discovery_error.message)


if __name__ == "__main__":
    unittest.main()

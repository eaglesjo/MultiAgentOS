import unittest
from pathlib import Path
import tempfile

from core.contracts.ai import AIProvider, ModelSpec
from core.contracts.capability import CapabilityConfidence
from core.contracts.discovery import ProviderDiscoveryResult
from core.contracts.quota import QuotaConfidence
from runtime.discovery import ProviderDiscoveryAdapter


class ProviderDiscoveryTests(unittest.TestCase):
    def provider(self):
        return AIProvider(
            id="demo",
            kind="http",
            models=(
                ModelSpec("demo-model", "demo", frozenset({"code"})),
            ),
            metadata={
                "discovery": {
                    "endpoint": "https://example.test/discovery",
                    "models_path": ["data"],
                    "quota_path": ["quotas"],
                }
            },
        )

    def test_discovery_normalizes_capabilities_and_actual_quota(self):
        payload = {
            "data": [
                {
                    "id": "demo-model",
                    "capabilities": ["code", "chat"],
                    "supports_tools": True,
                }
            ],
            "quotas": [
                {
                    "model_id": "demo-model",
                    "dimensions": [
                        {
                            "name": "requests",
                            "limit": 100,
                            "used": 25,
                            "remaining": 75,
                        }
                    ],
                }
            ],
        }
        adapter = ProviderDiscoveryAdapter(fetch=lambda endpoint, headers: payload)
        result = adapter.discover(self.provider())

        self.assertIsInstance(result, ProviderDiscoveryResult)
        self.assertEqual(result.capabilities[0].model_id, "demo-model")
        self.assertIn("tools", result.capabilities[0].capabilities)
        self.assertEqual(result.capabilities[0].confidence, CapabilityConfidence.DECLARED)
        self.assertEqual(result.quotas[0].dimension("requests").remaining, 75)
        self.assertEqual(result.quotas[0].confidence, QuotaConfidence.ACTUAL)

    def test_builtin_gemini_discovery_normalizes_model_name(self):
        provider = AIProvider(id="gemini", kind="gemini", models=(ModelSpec("gemini-3.8-flash", "gemini"),))
        payload = {"models": [{"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]}]}
        seen = {}
        def fetch(endpoint, headers):
            seen["endpoint"] = endpoint
            seen["headers"] = headers
            return payload
        adapter = ProviderDiscoveryAdapter(fetch=fetch)
        result = adapter.discover(provider)
        self.assertEqual(result.capabilities[0].model_id, "gemini-3.8-flash")
        self.assertIn("chat", result.capabilities[0].capabilities)
        self.assertEqual(seen["endpoint"], "https://generativelanguage.googleapis.com/v1beta/models")

    def test_discovery_without_endpoint_is_non_network_and_empty(self):
        provider = AIProvider(
            id="local",
            kind="local",
            models=(ModelSpec("local-model", "local"),),
        )
        adapter = ProviderDiscoveryAdapter(fetch=lambda endpoint, headers: self.fail("network"))
        result = adapter.discover(provider)
        self.assertEqual(result.source, "model_spec")
        self.assertEqual(result.capabilities, ())

    def test_discovery_error_is_safe_and_structured(self):
        adapter = ProviderDiscoveryAdapter(
            fetch=lambda endpoint, headers: (_ for _ in ()).throw(OSError("offline"))
        )
        result, error = adapter.discover_safe(self.provider())
        self.assertIsNone(result)
        self.assertEqual(error.provider_id, "demo")
        self.assertTrue(error.retryable)


if __name__ == "__main__":
    unittest.main()

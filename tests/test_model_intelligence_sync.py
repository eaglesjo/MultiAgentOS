import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.contracts.ai import AIProvider, ModelSpec
from core.contracts.capability import CapabilityConfidence, ModelCapabilityProfile
from core.contracts.quota import QuotaConfidence, QuotaDimension, QuotaSnapshot
from runtime.capability import CapabilityRegistry, CapabilityStore
from runtime.discovery import ProviderDiscoveryAdapter
from runtime.quota import QuotaIntelligence, QuotaStore


class ModelIntelligenceSyncTests(unittest.TestCase):
    def test_capability_merge_preserves_declared_and_observed_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = CapabilityRegistry(CapabilityStore(Path(tmp)))
            model = ModelSpec("demo-model", "demo", frozenset({"code"}))

            discovered = registry.merge(ModelCapabilityProfile(
                model_id=model.id,
                provider_id=model.provider_id,
                capabilities=frozenset({"chat", "tools"}),
                confidence=CapabilityConfidence.DECLARED,
                source="provider_discovery",
            ))
            self.assertEqual(
                discovered.capabilities,
                frozenset({"code", "chat", "tools"}),
            )

            observed = registry.observe_response(
                model,
                {"tool_calls": [], "usage": {"input_tokens": 10}},
            )
            self.assertEqual(
                observed.capabilities,
                frozenset({"code", "chat", "tools"}),
            )
            self.assertEqual(observed.confidence, CapabilityConfidence.OBSERVED)

    def test_quota_merge_does_not_replace_actual_with_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = QuotaStore(Path(tmp))
            now = datetime.now(timezone.utc)
            actual = QuotaSnapshot(
                model_id="demo-model",
                provider_id="demo",
                observed_at=now,
                dimensions=(QuotaDimension(
                    name="requests",
                    limit=100,
                    used=20,
                    remaining=80,
                    confidence=QuotaConfidence.ACTUAL,
                    source="provider_headers",
                ),),
            )
            store.save(actual)

            observed = QuotaSnapshot(
                model_id="demo-model",
                provider_id="demo",
                observed_at=now,
                dimensions=(QuotaDimension(
                    name="requests",
                    used=21,
                    confidence=QuotaConfidence.OBSERVED,
                    source="response_usage",
                ),),
            )
            merged = store.merge(observed)
            dimension = merged.dimension("requests")
            self.assertEqual(dimension.remaining, 80)
            self.assertEqual(dimension.confidence, QuotaConfidence.ACTUAL)

    def test_discovery_normalizes_provider_methods_to_common_capabilities(self):
        provider = AIProvider(
            id="gemini",
            kind="gemini",
            models=(ModelSpec("demo-model", "gemini"),),
        )
        payload = {
            "models": [{
                "name": "models/demo-model",
                "supportedGenerationMethods": [
                    "generateContent",
                    "embedContent",
                    "countTokens",
                ],
            }]
        }
        result = ProviderDiscoveryAdapter(
            fetch=lambda endpoint, headers: payload
        ).discover(provider)
        self.assertEqual(
            result.capabilities[0].capabilities,
            frozenset({"chat", "embeddings", "token_count"}),
        )

    def test_runtime_usage_merges_with_discovered_quota(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = QuotaStore(Path(tmp))
            now = datetime.now(timezone.utc)
            store.save(QuotaSnapshot(
                model_id="demo-model",
                provider_id="demo",
                observed_at=now,
                dimensions=(QuotaDimension(
                    name="requests",
                    limit=100,
                    used=20,
                    remaining=80,
                    confidence=QuotaConfidence.ACTUAL,
                    source="discovery",
                ),),
            ))
            intelligence = QuotaIntelligence(store)
            model = ModelSpec("demo-model", "demo")
            snapshot = intelligence.observe_response(
                model,
                {"usage": {"input_tokens": 12, "output_tokens": 8}},
            )
            self.assertEqual(snapshot.dimension("requests").remaining, 80)
            self.assertEqual(snapshot.dimension("requests").confidence, QuotaConfidence.ACTUAL)
            self.assertEqual(snapshot.dimension("input_tokens").used, 12)
            self.assertEqual(snapshot.dimension("output_tokens").used, 8)


if __name__ == "__main__":
    unittest.main()

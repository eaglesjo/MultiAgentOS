import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.health import HealthStatus, ModelHealth, ModelHealthRegistry, ModelHealthStore
from core.routing import AIRouter


class ModelHealthTests(unittest.TestCase):
    def test_quota_failure_is_quarantined(self):
        with TemporaryDirectory() as directory:
            registry = ModelHealthRegistry(ModelHealthStore(Path(directory)))
            error = RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
            error.status_code = 429
            health = registry.record_failure("gemini", "google", error)
            self.assertEqual(health.status, HealthStatus.QUOTA_EXHAUSTED)
            self.assertFalse(registry.available("gemini"))

    def test_rate_limit_uses_cooldown(self):
        with TemporaryDirectory() as directory:
            registry = ModelHealthRegistry(ModelHealthStore(Path(directory)))
            error = RuntimeError("429 rate limit")
            error.status_code = 429
            health = registry.record_failure("model", "provider", error)
            self.assertEqual(health.status, HealthStatus.RATE_LIMITED)
            self.assertIsNotNone(health.cooldown_until)
            self.assertFalse(registry.available("model"))

    def test_success_recovers_model(self):
        with TemporaryDirectory() as directory:
            registry = ModelHealthRegistry(ModelHealthStore(Path(directory)))
            error = RuntimeError("503 temporarily unavailable")
            error.status_code = 503
            registry.record_failure("model", "provider", error)
            health = registry.record_success("model", "provider")
            self.assertEqual(health.status, HealthStatus.HEALTHY)
            self.assertTrue(registry.available("model"))
            self.assertEqual(health.consecutive_failures, 0)

    def test_auth_failure_has_no_automatic_cooldown(self):
        with TemporaryDirectory() as directory:
            registry = ModelHealthRegistry(ModelHealthStore(Path(directory)))
            error = RuntimeError("401 invalid api key")
            error.status_code = 401
            health = registry.record_failure("model", "provider", error)
            self.assertEqual(health.status, HealthStatus.AUTH_FAILED)
            self.assertIsNone(health.cooldown_until)
            self.assertFalse(registry.available("model"))

    def test_routing_skips_unhealthy_model(self):
        with TemporaryDirectory() as directory:
            registry = ModelHealthRegistry(ModelHealthStore(Path(directory)))
            error = RuntimeError("503 overloaded")
            error.status_code = 503
            registry.record_failure("bad", "provider-a", error)
            now = datetime.now(timezone.utc)
            models = [
                ModelSpec("bad", "provider-a", frozenset({"code"})),
                ModelSpec("good", "provider-b", frozenset({"code"})),
            ]
            agent = AgentContract("coder", "coder", frozenset({"code"}), model_ids=())
            snapshots = {"bad": registry.get("bad")}
            assignment = AIRouter().assign(agent, models, health_snapshots=snapshots)
            self.assertEqual(assignment.model_id, "good")

    def test_expired_cooldown_is_available(self):
        with TemporaryDirectory() as directory:
            store = ModelHealthStore(Path(directory))
            store.save(ModelHealth(
                model_id="model",
                provider_id="provider",
                status=HealthStatus.RATE_LIMITED,
                cooldown_until=datetime.now(timezone.utc) - timedelta(seconds=1),
            ))
            self.assertTrue(ModelHealthRegistry(store).available("model"))


if __name__ == "__main__":
    unittest.main()

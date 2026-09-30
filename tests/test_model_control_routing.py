import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.health import HealthStatus, ModelHealth
from core.contracts.quota import QuotaConfidence, QuotaDimension, QuotaSnapshot
from core.routing import AIRouter, RoutingStrategy
from runtime.model_control import ModelControlPlane


class ModelControlRoutingTests(unittest.TestCase):
    def test_control_plane_unifies_capability_health_and_quota_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            control = ModelControlPlane(root)
            model = ModelSpec("model-a", "provider-a", frozenset({"chat", "tools"}))
            control.capability_registry.profile(model)
            control.health_registry.record_success(model.id, model.provider_id)
            control.quota_store.save(QuotaSnapshot(
                model_id=model.id,
                provider_id=model.provider_id,
                observed_at=datetime.now(timezone.utc),
                dimensions=(
                    QuotaDimension(
                        name="requests",
                        limit=100,
                        used=10,
                        remaining=90,
                        confidence=QuotaConfidence.ACTUAL,
                        source="test",
                    ),
                ),
            ))

            state = control.state(model)
            self.assertTrue(state.available)
            self.assertEqual(state.capabilities, frozenset({"chat", "tools"}))
            self.assertEqual(state.quota_score, 0.9)
            self.assertEqual(state.health.status, HealthStatus.HEALTHY)

    def test_router_rejects_control_plane_unavailable_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            control = ModelControlPlane(root)
            model = ModelSpec("model-a", "provider-a", frozenset({"chat"}))
            healthy = ModelSpec("model-b", "provider-b", frozenset({"chat"}))
            control.health_registry.store.save(ModelHealth(
                model_id=model.id,
                provider_id=model.provider_id,
                status=HealthStatus.TEMPORARILY_UNAVAILABLE,
                cooldown_until=datetime.now(timezone.utc) + timedelta(minutes=5),
            ))
            agent = AgentContract("agent", "developer", frozenset({"chat"}))
            explanation = AIRouter().explain(
                agent,
                [model, healthy],
                strategy=RoutingStrategy.POOL,
                health_snapshots={model.id: control.state(model).health},
                capability_registry=control.capability_registry,
            )
            candidate = explanation.candidates[0]
            self.assertFalse(candidate.health_available)
            self.assertIn("unhealthy", candidate.rejection_reasons)
            with self.assertRaises(LookupError):
                AIRouter().assign(
                    agent,
                    [model],
                    strategy=RoutingStrategy.POOL,
                    health_snapshots={model.id: control.state(model).health},
                    capability_registry=control.capability_registry,
                )

    def test_control_plane_quota_exhaustion_is_a_routing_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            control = ModelControlPlane(root)
            model = ModelSpec("model-a", "provider-a", frozenset({"chat"}))
            control.quota_store.save(QuotaSnapshot(
                model_id=model.id,
                provider_id=model.provider_id,
                observed_at=datetime.now(timezone.utc),
                dimensions=(
                    QuotaDimension(
                        name="requests",
                        limit=100,
                        used=100,
                        remaining=0,
                        confidence=QuotaConfidence.ACTUAL,
                        source="test",
                    ),
                ),
            ))
            healthy = ModelSpec("model-b", "provider-b", frozenset({"chat"}))
            agent = AgentContract("agent", "developer", frozenset({"chat"}))
            explanation = AIRouter().explain(
                agent,
                [model, healthy],
                strategy=RoutingStrategy.POOL,
                quota_snapshots={model.id: control.state(model).quota},
                capability_registry=control.capability_registry,
            )
            self.assertFalse(explanation.candidates[0].quota_available)
            self.assertIn("quota_unavailable", explanation.candidates[0].rejection_reasons)


if __name__ == "__main__":
    unittest.main()

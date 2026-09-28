import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.contracts.ai import ModelSpec
from core.contracts.quota import QuotaDimension, QuotaSnapshot
from runtime.model_control import ModelControlPlane


class ModelControlPlaneTests(unittest.TestCase):
    def test_combines_health_and_quota(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            control = ModelControlPlane(root)
            model = ModelSpec("model-a", "provider-a", frozenset({"code"}))
            snapshot = QuotaSnapshot(
                model_id="model-a",
                provider_id="provider-a",
                observed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                dimensions=(QuotaDimension("requests", limit=100, remaining=80),),
            )
            control.quota_store.save(snapshot)
            state = control.state(model)
            self.assertTrue(state.available)
            self.assertEqual(state.quota_score, 0.8)
            self.assertIsNone(state.health)

    def test_records_success_and_failure_events(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            control = ModelControlPlane(root)
            model = ModelSpec("model-a", "provider-a")
            control.record_success(model, {"attempts": ("model-a",)})
            error = RuntimeError("503 service unavailable")
            error.status_code = 503
            control.record_failure(model, error)
            events = control.events.recent()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event"], "success")
            self.assertEqual(events[1]["event"], "failure")
            self.assertEqual(events[1]["status"], "temporarily_unavailable")

    def test_dashboard_exposes_operational_state(self):
        with TemporaryDirectory() as directory:
            control = ModelControlPlane(Path(directory))
            models = [ModelSpec("model-a", "provider-a")]
            row = control.dashboard(models)[0]
            self.assertEqual(row["health"], "healthy")
            self.assertTrue(row["available"])
            self.assertEqual(row["quota_score"], 0.5)


if __name__ == "__main__":
    unittest.main()

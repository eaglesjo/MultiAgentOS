from datetime import timezone

from core.contracts.ai import ModelSpec
from core.contracts.quota import QuotaConfidence
from runtime.quota import QuotaIntelligence, QuotaStore


def test_provider_reported_rate_limits_are_actual(tmp_path):
    model = ModelSpec(id="gpt-test", provider_id="openai")
    intelligence = QuotaIntelligence(QuotaStore(tmp_path))
    snapshot = intelligence.observe_response(
        model,
        {
            "rate_limits": {
                "requests": {"limit": 100, "remaining": 73, "reset_seconds": 42}
            }
        },
    )
    requests = snapshot.dimension("requests")
    assert requests is not None
    assert requests.remaining == 73
    assert requests.used == 27
    assert requests.confidence is QuotaConfidence.ACTUAL
    assert requests.reset_at is not None
    assert requests.reset_at.tzinfo is timezone.utc


def test_configured_limits_estimate_remaining_from_usage(tmp_path):
    model = ModelSpec(
        id="gemini-test",
        provider_id="gemini",
        metadata={"quota_limits": {"requests": {"limit": 1000}}},
    )
    intelligence = QuotaIntelligence(QuotaStore(tmp_path))
    first = intelligence.observe_response(model, {"usage": {"total_tokens": 10}})
    second = intelligence.observe_response(model, {"usage": {"total_tokens": 20}})
    # Requests are independently observed and accumulate across snapshots.
    requests = second.dimension("requests")
    assert requests is not None
    assert requests.used == 2
    assert requests.remaining == 998
    assert requests.confidence is QuotaConfidence.ESTIMATED

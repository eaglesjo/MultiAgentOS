from datetime import datetime, timedelta, timezone

from core.contracts.quota import QuotaDimension, QuotaSnapshot
from runtime.quota import quota_available, quota_score


def snapshot(name, remaining, reset_at=None):
    return QuotaSnapshot(
        model_id=name,
        provider_id="test",
        observed_at=datetime.now(timezone.utc),
        dimensions=(QuotaDimension("requests", limit=100, remaining=remaining, reset_at=reset_at),),
    )


def test_quota_available_allows_unknown():
    assert quota_available(snapshot("x", None))


def test_quota_available_rejects_zero():
    assert not quota_available(snapshot("x", 0))


def test_quota_score_reflects_remaining_capacity():
    assert quota_score(snapshot("x", 80)) > quota_score(snapshot("y", 20))


def test_expired_reset_restores_quota_availability():
    reset_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert quota_available(snapshot("x", 0, reset_at=reset_at))
    assert quota_score(snapshot("x", 0, reset_at=reset_at)) == 0.5

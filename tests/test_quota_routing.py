from datetime import datetime, timedelta, timezone

from core.contracts.ai import ModelSpec
from core.contracts.agent import AgentContract
from core.routing import AIRouter


def agent():
    return AgentContract(id="coder", name="coder", capabilities=frozenset({"code"}), model_ids=())


def test_router_skips_exhausted_quota(tmp_path):
    router = AIRouter()
    models = (
        ModelSpec(id="empty", provider_id="a", capabilities=frozenset({"code"})),
        ModelSpec(id="healthy", provider_id="b", capabilities=frozenset({"code"})),
    )
    from core.contracts.quota import QuotaDimension, QuotaSnapshot
    now = datetime.now(timezone.utc)
    snapshots = {
        "empty": QuotaSnapshot("empty", "a", now, (
            QuotaDimension("requests", limit=100, used=100, remaining=0),
        )),
        "healthy": QuotaSnapshot("healthy", "b", now, (
            QuotaDimension("requests", limit=100, used=10, remaining=90),
        )),
    }
    assignment = router.assign(agent(), models, quota_snapshots=snapshots)
    assert assignment.model_id == "healthy"


def test_router_prefers_more_remaining_capacity():
    router = AIRouter()
    models = (
        ModelSpec(id="low", provider_id="a", capabilities=frozenset({"code"})),
        ModelSpec(id="high", provider_id="b", capabilities=frozenset({"code"})),
    )
    from core.contracts.quota import QuotaDimension, QuotaSnapshot
    now = datetime.now(timezone.utc)
    snapshots = {
        "low": QuotaSnapshot("low", "a", now, (QuotaDimension("requests", limit=100, remaining=20),)),
        "high": QuotaSnapshot("high", "b", now, (QuotaDimension("requests", limit=100, remaining=80),)),
    }
    assert router.assign(agent(), models, quota_snapshots=snapshots).model_id == "high"


def test_unknown_quota_remains_eligible():
    router = AIRouter()
    model = ModelSpec(id="unknown", provider_id="a", capabilities=frozenset({"code"}))
    assert router.assign(agent(), (model,), quota_snapshots={}).model_id == "unknown"

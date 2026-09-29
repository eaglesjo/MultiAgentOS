"""Unified Model Control Plane for AGENT_EXECUTION_RUNTIME.

Quota answers "how much capacity remains?".
Health answers "can this model currently be trusted to serve?".
The control plane combines both without conflating their semantics.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.contracts.ai import ModelSpec
from core.contracts.health import ModelHealth, ModelHealthRegistry, ModelHealthStore
from core.contracts.quota import QuotaSnapshot
from runtime.quota import QuotaStore, quota_available, quota_score


@dataclass(frozen=True)
class ModelControlState:
    model_id: str
    provider_id: str
    health: ModelHealth | None
    quota: QuotaSnapshot | None

    @property
    def available(self) -> bool:
        return (
            (self.health is None or self.health.available)
            and (self.quota is None or quota_available(self.quota))
        )

    @property
    def quota_score(self) -> float:
        return quota_score(self.quota) if self.quota is not None else 0.5


class ModelControlEventStore:
    """Append-only operational events; never stores credentials or prompt contents."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        model: ModelSpec,
        event: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "model_id": model.id,
            "provider_id": model.provider_id,
            "event": event,
            "status": status,
            "metadata": metadata or {},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")

    def recent(self, limit: int = 100) -> tuple[dict[str, Any], ...]:
        if not self.path.exists():
            return ()
        lines = self.path.read_text(encoding="utf-8").splitlines()
        result = []
        for line in lines[-max(0, limit):]:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return tuple(result)


class ModelControlPlane:
    """Project-scoped facade over model quota, health, and operational events."""

    def __init__(self, project_root: Path) -> None:
        root = Path(project_root) / ".multiagentos"
        self.root = root
        self.quota_store = QuotaStore(root / "quota")
        self.health_registry = ModelHealthRegistry(ModelHealthStore(root / "health"))
        self.events = ModelControlEventStore(root / "control" / "events.jsonl")

    def state(self, model: ModelSpec) -> ModelControlState:
        return ModelControlState(
            model_id=model.id,
            provider_id=model.provider_id,
            health=self.health_registry.get(model.id),
            quota=self.quota_store.load(model.id) if self.quota_store.exists(model.id) else None,
        )

    def states(self, models: list[ModelSpec]) -> tuple[ModelControlState, ...]:
        return tuple(self.state(model) for model in models)

    def record_success(self, model: ModelSpec, metadata: dict[str, Any] | None = None) -> ModelControlState:
        health = self.health_registry.record_success(model.id, model.provider_id)
        self.events.append(
            model=model,
            event="success",
            status=health.status.value,
            metadata={"attempts": (metadata or {}).get("attempts", ())},
        )
        return self.state(model)

    def record_failure(self, model: ModelSpec, exc: Exception) -> ModelControlState:
        health = self.health_registry.record_failure(model.id, model.provider_id, exc)
        status = health.status.value if health is not None else "unclassified"
        self.events.append(
            model=model,
            event="failure",
            status=status,
            metadata={"error_type": type(exc).__name__, "error": str(exc)},
        )
        return self.state(model)

    def dashboard(self, models: list[ModelSpec]) -> tuple[dict[str, Any], ...]:
        rows = []
        for state in self.states(models):
            health = state.health
            quota = state.quota
            rows.append({
                "model": state.model_id,
                "provider": state.provider_id,
                "available": state.available,
                "health": health.status.value if health else "healthy",
                "cooldown_until": health.cooldown_until.isoformat() if health and health.cooldown_until else None,
                "consecutive_failures": health.consecutive_failures if health else 0,
                "quota_score": state.quota_score,
                "quota_dimensions": len(quota.dimensions) if quota else 0,
            })
        return tuple(rows)

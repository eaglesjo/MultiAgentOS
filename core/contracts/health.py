"""Persistent model health and cooldown registry for AGENT_EXECUTION_RUNTIME."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    AUTH_FAILED = "auth_failed"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ModelHealth:
    model_id: str
    provider_id: str
    status: HealthStatus = HealthStatus.HEALTHY
    consecutive_failures: int = 0
    successes: int = 0
    last_error: str | None = None
    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None
    cooldown_until: datetime | None = None
    metadata: dict[str, Any] | None = None

    @property
    def available(self) -> bool:
        if self.status in {HealthStatus.AUTH_FAILED, HealthStatus.DISABLED}:
            return False
        if self.cooldown_until is None:
            return self.status is HealthStatus.HEALTHY
        return self.cooldown_until <= datetime.now(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def classify_failure(exc: Exception) -> HealthStatus | None:
    status = getattr(exc, "status_code", getattr(exc, "status", None))
    code = str(getattr(exc, "code", "")).lower()
    message = str(exc).lower()
    combined = f"{code} {message}"
    if status in {401, 403}:
        return HealthStatus.AUTH_FAILED
    if any(token in combined for token in (
        "quota_exceeded", "quota exceeded", "daily quota",
        "resource_exhausted", "resource exhausted",
    )):
        return HealthStatus.QUOTA_EXHAUSTED
    if status == 429 or any(token in combined for token in (
        "rate_limit", "rate-limit", "too_many_requests",
    )):
        return HealthStatus.RATE_LIMITED
    if status in {408, 500, 502, 503, 504} or any(token in combined for token in (
        "temporarily_unavailable", "service_unavailable",
        "overloaded", "timeout",
    )):
        return HealthStatus.TEMPORARILY_UNAVAILABLE
    return None


class ModelHealthStore:
    """Persist one health record per model without storing credentials."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, model_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in model_id)
        return self.root / f"{safe}.json"

    def save(self, health: ModelHealth) -> Path:
        payload = {
            "model_id": health.model_id,
            "provider_id": health.provider_id,
            "status": health.status.value,
            "consecutive_failures": health.consecutive_failures,
            "successes": health.successes,
            "last_error": health.last_error,
            "last_failure_at": health.last_failure_at.isoformat() if health.last_failure_at else None,
            "last_success_at": health.last_success_at.isoformat() if health.last_success_at else None,
            "cooldown_until": health.cooldown_until.isoformat() if health.cooldown_until else None,
            "metadata": health.metadata or {},
        }
        path = self.path_for(health.model_id)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def load(self, model_id: str) -> ModelHealth:
        data = json.loads(self.path_for(model_id).read_text(encoding="utf-8"))
        return ModelHealth(
            model_id=data["model_id"],
            provider_id=data["provider_id"],
            status=HealthStatus(data.get("status", HealthStatus.HEALTHY.value)),
            consecutive_failures=int(data.get("consecutive_failures", 0)),
            successes=int(data.get("successes", 0)),
            last_error=data.get("last_error"),
            last_failure_at=_parse_dt(data.get("last_failure_at")),
            last_success_at=_parse_dt(data.get("last_success_at")),
            cooldown_until=_parse_dt(data.get("cooldown_until")),
            metadata=dict(data.get("metadata", {})),
        )

    def exists(self, model_id: str) -> bool:
        return self.path_for(model_id).exists()

    def list_model_ids(self) -> tuple[str, ...]:
        return tuple(sorted(path.stem for path in self.root.glob("*.json")))


class ModelHealthRegistry:
    """Track model failures independently from quota and quarantine unhealthy models."""

    def __init__(self, store: ModelHealthStore) -> None:
        self.store = store

    def get(self, model_id: str) -> ModelHealth | None:
        if not self.store.exists(model_id):
            return None
        return self.store.load(model_id)

    def available(self, model_id: str) -> bool:
        health = self.get(model_id)
        return health is None or health.available

    def record_success(self, model_id: str, provider_id: str) -> ModelHealth:
        previous = self.get(model_id)
        health = ModelHealth(
            model_id=model_id,
            provider_id=provider_id,
            status=HealthStatus.HEALTHY,
            consecutive_failures=0,
            successes=(previous.successes if previous else 0) + 1,
            last_error=None,
            last_failure_at=previous.last_failure_at if previous else None,
            last_success_at=_now(),
            cooldown_until=None,
            metadata=dict(previous.metadata or {}) if previous else {},
        )
        self.store.save(health)
        return health

    def record_failure(self, model_id: str, provider_id: str, exc: Exception) -> ModelHealth | None:
        status = classify_failure(exc)
        if status is None:
            return None
        previous = self.get(model_id)
        failures = (previous.consecutive_failures if previous else 0) + 1
        cooldown = self._cooldown(status, failures, exc)
        health = ModelHealth(
            model_id=model_id,
            provider_id=provider_id,
            status=status,
            consecutive_failures=failures,
            successes=previous.successes if previous else 0,
            last_error=str(exc),
            last_failure_at=_now(),
            last_success_at=previous.last_success_at if previous else None,
            cooldown_until=cooldown,
            metadata={"failure_type": status.value},
        )
        self.store.save(health)
        return health

    @staticmethod
    def _cooldown(status: HealthStatus, failures: int, exc: Exception) -> datetime | None:
        now = _now()
        if status is HealthStatus.AUTH_FAILED:
            return None
        reset_at = _parse_dt(getattr(exc, "reset_at", None))
        if reset_at is None:
            metadata = getattr(exc, "metadata", None)
            if isinstance(metadata, dict):
                reset_at = _parse_dt(metadata.get("reset_at"))
                if reset_at is None:
                    reset_seconds = metadata.get("retry_after") or metadata.get("reset_seconds")
                    try:
                        if reset_seconds is not None:
                            reset_at = now + timedelta(seconds=float(reset_seconds))
                    except (TypeError, ValueError):
                        pass
        if reset_at is not None and reset_at > now:
            return reset_at
        if status is HealthStatus.QUOTA_EXHAUSTED:
            return None
        seconds = min(300, 15 * (2 ** min(failures - 1, 4)))
        return now + timedelta(seconds=seconds)

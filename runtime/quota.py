"""Persistent quota intelligence for VYRELON model routing."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.contracts.ai import ModelSpec
from core.contracts.quota import QuotaConfidence, QuotaDimension, QuotaSnapshot


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class QuotaStore:
    """Persist the latest quota snapshot per model without storing credentials."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, model_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in model_id)
        return self.root / f"{safe}.json"

    def save(self, snapshot: QuotaSnapshot) -> Path:
        payload = {
            "model_id": snapshot.model_id,
            "provider_id": snapshot.provider_id,
            "observed_at": snapshot.observed_at.isoformat(),
            "scope": snapshot.scope,
            "metadata": snapshot.metadata,
            "dimensions": [
                {
                    "name": item.name,
                    "limit": item.limit,
                    "used": item.used,
                    "remaining": item.remaining,
                    "reset_at": item.reset_at.isoformat() if item.reset_at else None,
                    "window_seconds": item.window_seconds,
                    "confidence": item.confidence.value,
                    "source": item.source,
                }
                for item in snapshot.dimensions
            ],
        }
        path = self.path_for(snapshot.model_id)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def load(self, model_id: str) -> QuotaSnapshot:
        data = json.loads(self.path_for(model_id).read_text(encoding="utf-8"))
        dimensions = tuple(
            QuotaDimension(
                name=item["name"],
                limit=item.get("limit"),
                used=item.get("used"),
                remaining=item.get("remaining"),
                reset_at=_parse_dt(item.get("reset_at")),
                window_seconds=item.get("window_seconds"),
                confidence=QuotaConfidence(item.get("confidence", "unknown")),
                source=item.get("source", "unknown"),
            )
            for item in data.get("dimensions", ())
        )
        observed_at = _parse_dt(data.get("observed_at")) or _now()
        return QuotaSnapshot(
            model_id=data["model_id"],
            provider_id=data["provider_id"],
            observed_at=observed_at,
            dimensions=dimensions,
            scope=data.get("scope", "model"),
            metadata=dict(data.get("metadata", {})),
        )

    def exists(self, model_id: str) -> bool:
        return self.path_for(model_id).exists()

    def list_model_ids(self) -> tuple[str, ...]:
        return tuple(sorted(path.stem for path in self.root.glob("*.json")))


class QuotaIntelligence:
    """Turn provider metadata and configured limits into normalized snapshots."""

    def __init__(self, store: QuotaStore) -> None:
        self.store = store

    def observe_response(self, model: ModelSpec, metadata: dict[str, Any]) -> QuotaSnapshot:
        dimensions: list[QuotaDimension] = []
        raw_limits = model.metadata.get("quota_limits", {})
        configured = raw_limits if isinstance(raw_limits, dict) else {}
        raw_actual = metadata.get("rate_limits", {})
        actual = raw_actual if isinstance(raw_actual, dict) else {}
        usage = metadata.get("usage", {})
        usage = usage if isinstance(usage, dict) else {}

        for name, value in actual.items():
            if not isinstance(value, dict):
                continue
            limit = _number(value.get("limit"))
            remaining = _number(value.get("remaining"))
            reset_at = _parse_dt(value.get("reset_at"))
            reset_seconds = _number(value.get("reset_seconds"))
            if reset_at is None and reset_seconds is not None:
                reset_at = datetime.fromtimestamp(
                    _now().timestamp() + float(reset_seconds), tz=timezone.utc
                )
            used = limit - remaining if limit is not None and remaining is not None else None
            dimensions.append(
                QuotaDimension(
                    name=name,
                    limit=limit,
                    used=used,
                    remaining=remaining,
                    reset_at=reset_at,
                    confidence=QuotaConfidence.ACTUAL,
                    source=str(value.get("source", "provider")),
                )
            )

        usage_map = {
            "requests": 1,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
        for name, increment in usage_map.items():
            if increment is None or any(item.name == name for item in dimensions):
                continue
            limit_spec = configured.get(name)
            if not isinstance(limit_spec, dict):
                dimensions.append(
                    QuotaDimension(name=name, used=_number(increment), confidence=QuotaConfidence.OBSERVED, source="response_usage")
                )
                continue
            limit = _number(limit_spec.get("limit"))
            prior_used = 0
            if self.store.exists(model.id):
                previous = self.store.load(model.id).dimension(name)
                prior_used = float(previous.used or 0) if previous else 0
            used = prior_used + float(increment)
            remaining = max(0, limit - used) if limit is not None else None
            dimensions.append(
                QuotaDimension(
                    name=name,
                    limit=limit,
                    used=used,
                    remaining=remaining,
                    reset_at=_parse_dt(limit_spec.get("reset_at")),
                    window_seconds=int(limit_spec["window_seconds"]) if limit_spec.get("window_seconds") else None,
                    confidence=QuotaConfidence.ESTIMATED if limit is not None else QuotaConfidence.OBSERVED,
                    source="configured_limit",
                )
            )

        merged: dict[str, QuotaDimension] = {}
        if self.store.exists(model.id):
            for item in self.store.load(model.id).dimensions:
                merged[item.name] = item
        for item in dimensions:
            merged[item.name] = item

        snapshot = QuotaSnapshot(
            model_id=model.id,
            provider_id=model.provider_id,
            observed_at=_now(),
            dimensions=tuple(merged.values()),
            scope=str(model.metadata.get("quota_scope", "model")),
        )
        self.store.save(snapshot)
        return snapshot


def _number(value: object) -> int | float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def quota_available(snapshot: QuotaSnapshot, threshold: float = 0.05) -> bool:
    """Return whether any known limiting dimension has usable capacity."""
    known = [item for item in snapshot.dimensions if item.remaining is not None]
    if not known:
        return True
    return all(
        float(item.remaining) > 0
        and (
            item.limit in (None, 0)
            or float(item.remaining) / float(item.limit) > threshold
        )
        for item in known
    )


def quota_score(snapshot: QuotaSnapshot) -> float:
    """Return a normalized 0..1 score for routing among known quotas."""
    known = [
        item
        for item in snapshot.dimensions
        if item.remaining is not None and item.limit not in (None, 0)
    ]
    if not known:
        return 0.5
    return max(0.0, min(1.0, min(float(item.remaining) / float(item.limit) for item in known)))

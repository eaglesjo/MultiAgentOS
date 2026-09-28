"""Persistent model capability registry."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.ai import ModelSpec
from core.contracts.capability import (
    CapabilityConfidence,
    CapabilityMatch,
    ModelCapabilityProfile,
)


class CapabilityStore:
    """Project-scoped JSON persistence for normalized model capabilities."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, model_id: str) -> Path:
        safe = model_id.replace("/", "__").replace(":", "__")
        return self.root / f"{safe}.json"

    def exists(self, model_id: str) -> bool:
        return self.path(model_id).exists()

    def save(self, profile: ModelCapabilityProfile) -> None:
        self.path(profile.model_id).write_text(
            json.dumps(
                {
                    "model_id": profile.model_id,
                    "provider_id": profile.provider_id,
                    "capabilities": sorted(profile.capabilities),
                    "confidence": profile.confidence.value,
                    "source": profile.source,
                    "metadata": profile.metadata,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

    def load(self, model_id: str) -> ModelCapabilityProfile:
        data = json.loads(self.path(model_id).read_text(encoding="utf-8"))
        return ModelCapabilityProfile(
            model_id=str(data["model_id"]),
            provider_id=str(data["provider_id"]),
            capabilities=frozenset(str(item) for item in data.get("capabilities", [])),
            confidence=CapabilityConfidence(str(data.get("confidence", "unknown"))),
            source=str(data.get("source", "unknown")),
            metadata=dict(data.get("metadata", {})),
        )


class CapabilityRegistry:
    """Resolve and persist model capability profiles."""

    def __init__(self, store: CapabilityStore) -> None:
        self.store = store

    def profile(self, model: ModelSpec) -> ModelCapabilityProfile:
        if self.store.exists(model.id):
            stored = self.store.load(model.id)
            if stored.provider_id == model.provider_id:
                return stored
        capabilities = frozenset(str(item) for item in model.capabilities)
        profile = ModelCapabilityProfile(
            model_id=model.id,
            provider_id=model.provider_id,
            capabilities=capabilities,
            confidence=CapabilityConfidence.DECLARED,
            source="model_spec",
        )
        self.store.save(profile)
        return profile

    def match(self, model: ModelSpec, requirements: frozenset[str]) -> CapabilityMatch:
        profile = self.profile(model)
        matched = profile.capabilities & requirements
        missing = requirements - profile.capabilities
        return CapabilityMatch(
            model_id=model.id,
            required=requirements,
            matched=matched,
            missing=missing,
            score=profile.match_score(requirements),
            confidence=profile.confidence,
        )

    def matches(
        self,
        models: list[ModelSpec],
        requirements: frozenset[str],
    ) -> dict[str, CapabilityMatch]:
        return {model.id: self.match(model, requirements) for model in models}

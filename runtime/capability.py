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

    def merge(self, profile: ModelCapabilityProfile) -> ModelCapabilityProfile:
        """Merge a discovered or observed profile with the persisted profile."""
        if self.store.exists(profile.model_id):
            current = self.store.load(profile.model_id)
            if current.provider_id != profile.provider_id:
                raise ValueError(f"Capability provider mismatch for {profile.model_id}")
            confidence = (
                CapabilityConfidence.OBSERVED
                if CapabilityConfidence.OBSERVED in {current.confidence, profile.confidence}
                else CapabilityConfidence.DECLARED
                if CapabilityConfidence.DECLARED in {current.confidence, profile.confidence}
                else CapabilityConfidence.UNKNOWN
            )
            metadata = dict(current.metadata)
            metadata.update(profile.metadata)
            merged = ModelCapabilityProfile(
                model_id=profile.model_id,
                provider_id=profile.provider_id,
                capabilities=frozenset(current.capabilities | profile.capabilities),
                confidence=confidence,
                source=f"{current.source}+{profile.source}",
                metadata=metadata,
            )
        else:
            merged = profile
        self.store.save(merged)
        return merged

    def observe_response(self, model: ModelSpec, metadata: dict[str, object]) -> ModelCapabilityProfile:
        """Record capabilities directly evidenced by a successful model response."""
        observed = {"chat"}
        if "tool_calls" in metadata or metadata.get("tools_used") is True:
            observed.add("tools")
        if metadata.get("structured_output") is True:
            observed.add("structured_output")
        return self.merge(ModelCapabilityProfile(
            model_id=model.id,
            provider_id=model.provider_id,
            capabilities=frozenset(observed),
            confidence=CapabilityConfidence.OBSERVED,
            source="runtime_observation",
            metadata={"observed_capabilities": sorted(observed)},
        ))

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

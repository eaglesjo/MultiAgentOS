"""Persistent artifact registry for VYRELON workflows."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.handoff import ArtifactContract


class ArtifactStore:
    """Persist artifact metadata separately from transient model output."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, artifact: ArtifactContract) -> Path:
        artifact.validate()
        path = self.root / f"{artifact.id}.json"
        payload = {
            "id": artifact.id,
            "kind": artifact.kind,
            "producer_agent_id": artifact.producer_agent_id,
            "content_ref": artifact.content_ref,
            "summary": artifact.summary,
            "media_type": artifact.media_type,
            "metadata": artifact.metadata,
        }
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        return path

    def load(self, artifact_id: str) -> ArtifactContract:
        path = self.root / f"{artifact_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return ArtifactContract(
            id=data["id"],
            kind=data["kind"],
            producer_agent_id=data["producer_agent_id"],
            content_ref=data["content_ref"],
            summary=data.get("summary", ""),
            media_type=data.get("media_type", "text/plain"),
            metadata=dict(data.get("metadata", {})),
        )

"""Append-only durable project memory store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.contracts.memory import MemoryKind, ProjectMemory
from core.security import redact_sensitive


class ProjectMemoryStore:
    """Persist project context separately from execution evidence."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        content: str,
        *,
        kind: MemoryKind = MemoryKind.NOTE,
        source: str = "runtime",
        metadata: dict[str, object] | None = None,
    ) -> ProjectMemory:
        if not content.strip():
            raise ValueError("memory content must not be empty")
        memory = ProjectMemory(
            memory_id=f"mem-{uuid4().hex}",
            kind=kind,
            content=str(redact_sensitive(content)),
            source=str(redact_sensitive(source)),
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=redact_sensitive(dict(metadata or {})),
        )
        path = self.root / "memory.jsonl"
        payload = {
            "memory_id": memory.memory_id,
            "kind": memory.kind.value,
            "content": memory.content,
            "source": memory.source,
            "created_at": memory.created_at,
            "metadata": memory.metadata,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return memory

    def search(self, query: str = "", *, limit: int = 20) -> tuple[ProjectMemory, ...]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        path = self.root / "memory.jsonl"
        if not path.exists():
            return ()
        needle = query.strip().casefold()
        results: list[ProjectMemory] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if needle and needle not in str(payload.get("content", "")).casefold():
                continue
            results.append(ProjectMemory(
                memory_id=str(payload["memory_id"]),
                kind=MemoryKind(str(payload["kind"])),
                content=str(payload["content"]),
                source=str(payload["source"]),
                created_at=str(payload["created_at"]),
                metadata=dict(payload.get("metadata") or {}),
            ))
        return tuple(results[-limit:][::-1])

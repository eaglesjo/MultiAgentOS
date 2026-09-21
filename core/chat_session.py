"""Persistent conversational session state for VYRELON Chat Agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from datetime import datetime, timezone


@dataclass
class ChatSession:
    id: str
    chat_agent_id: str
    work_unit_id: str | None = None
    turns: list[dict[str, object]] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    updated_at: str = ""

    def add_turn(self, role: str, content: str, **metadata: object) -> None:
        self.turns.append(
            {"role": role, "content": content, "metadata": metadata}
        )
        self.updated_at = datetime.now(timezone.utc).isoformat()


class ChatSessionStore:
    """Store Chat Agent conversation state separately from provider credentials."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, session: ChatSession) -> Path:
        if not session.updated_at:
            session.updated_at = datetime.now(timezone.utc).isoformat()
        path = self.root / f"{session.id}.json"
        payload = {
            "id": session.id,
            "chat_agent_id": session.chat_agent_id,
            "work_unit_id": session.work_unit_id,
            "turns": session.turns,
            "metadata": session.metadata,
            "updated_at": session.updated_at,
        }
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        return path

    def load(self, session_id: str) -> ChatSession:
        path = self.root / f"{session_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return ChatSession(
            id=data["id"],
            chat_agent_id=data["chat_agent_id"],
            work_unit_id=data.get("work_unit_id"),
            turns=list(data.get("turns", [])),
            metadata=dict(data.get("metadata", {})),
            updated_at=data.get("updated_at", ""),
        )

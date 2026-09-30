"""Durable execution cursor and model/message state."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.execution_cursor import ExecutionCursor
from core.security import redact_sensitive


class ExecutionStateStore:
    """Persist resumable execution position and normalized conversation state."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.cursor_root = root / "cursors"
        self.message_root = root / "messages"
        self.cursor_root.mkdir(parents=True, exist_ok=True)
        self.message_root.mkdir(parents=True, exist_ok=True)

    def save_cursor(self, cursor: ExecutionCursor) -> Path:
        path = self.cursor_root / f"{cursor.work_unit_id}.json"
        path.write_text(
            json.dumps({
                "work_unit_id": cursor.work_unit_id,
                "event_sequence": cursor.event_sequence,
                "round_number": cursor.round_number,
                "agent_id": cursor.agent_id,
                "model_id": cursor.model_id,
                "conversation_revision": cursor.conversation_revision,
                "next_tool_call_id": cursor.next_tool_call_id,
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def load_cursor(self, work_unit_id: str) -> ExecutionCursor:
        data = json.loads(
            (self.cursor_root / f"{work_unit_id}.json").read_text(encoding="utf-8")
        )
        return ExecutionCursor(
            work_unit_id=data["work_unit_id"],
            event_sequence=int(data["event_sequence"]),
            round_number=int(data["round_number"]),
            agent_id=data["agent_id"],
            model_id=data.get("model_id"),
            conversation_revision=int(data.get("conversation_revision", 0)),
            next_tool_call_id=data.get("next_tool_call_id"),
        )

    def append_message(
        self,
        work_unit_id: str,
        *,
        role: str,
        round_number: int,
        content: object,
        metadata: dict[str, object] | None = None,
    ) -> int:
        path = self.message_root / f"{work_unit_id}.jsonl"
        revision = self.next_message_revision(work_unit_id)
        payload = {
            "revision": revision,
            "role": role,
            "round_number": round_number,
            "content": redact_sensitive(content),
            "metadata": redact_sensitive(dict(metadata or {})),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return revision

    def load_messages(self, work_unit_id: str) -> tuple[dict[str, object], ...]:
        path = self.message_root / f"{work_unit_id}.jsonl"
        if not path.exists():
            return ()
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    def next_message_revision(self, work_unit_id: str) -> int:
        messages = self.load_messages(work_unit_id)
        return int(messages[-1].get("revision") or 0) + 1 if messages else 1

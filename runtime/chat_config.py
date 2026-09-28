"""Project-scoped conversational Chat Agent configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChatConfig:
    version: int
    agent_id: str
    model: str | None = None

    def validate(self) -> None:
        if self.version != 1:
            raise ValueError(f"unsupported chat config version: {self.version}")
        if not self.agent_id.strip():
            raise ValueError("chat agent id must not be empty")
        if self.model is not None and not self.model.strip():
            raise ValueError("chat model must not be empty when provided")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {"version": self.version, "agent_id": self.agent_id, "model": self.model}


DEFAULT_CHAT_CONFIG = ChatConfig(version=1, agent_id="chatgpt", model=None)


def load_chat_config(project_root: Path) -> ChatConfig:
    path = project_root / ".multiagentos" / "chat.json"
    if not path.is_file():
        raise FileNotFoundError(f"VYRELON chat config not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("chat config must be a JSON object")
    config = ChatConfig(
        version=int(data.get("version", 0)),
        agent_id=str(data.get("agent_id", "")),
        model=data.get("model"),
    )
    config.validate()
    return config


def write_default_chat_config(project_root: Path) -> Path:
    target = project_root / ".multiagentos"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "chat.json"
    if not path.exists():
        path.write_text(
            json.dumps(DEFAULT_CHAT_CONFIG.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return path

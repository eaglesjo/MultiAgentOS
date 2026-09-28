"""Project-scoped execution configuration for VYRELON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecutionConfig:
    version: int
    runtime: str
    agent_id: str
    model_id: str

    def validate(self) -> None:
        if self.version != 1:
            raise ValueError(f"unsupported execution config version: {self.version}")
        if not self.runtime.strip():
            raise ValueError("execution runtime must not be empty")
        if not self.agent_id.strip():
            raise ValueError("execution agent id must not be empty")
        if not self.model_id.strip():
            raise ValueError("execution model id must not be empty")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "version": self.version,
            "runtime": self.runtime,
            "agent_id": self.agent_id,
            "model_id": self.model_id,
        }


DEFAULT_EXECUTION_CONFIG = ExecutionConfig(
    version=1,
    runtime="process",
    agent_id="cli-executor",
    model_id="local-process",
)


def load_execution_config(project_root: Path) -> ExecutionConfig:
    path = project_root / ".multiagentos" / "execution.json"
    if not path.is_file():
        raise FileNotFoundError(f"VYRELON execution config not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("execution config must be a JSON object")
    config = ExecutionConfig(
        version=int(data.get("version", 0)),
        runtime=str(data.get("runtime", "")),
        agent_id=str(data.get("agent_id", "")),
        model_id=str(data.get("model_id", "")),
    )
    config.validate()
    return config


def write_default_execution_config(project_root: Path) -> Path:
    target = project_root / ".multiagentos"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "execution.json"
    if not path.exists():
        path.write_text(
            json.dumps(DEFAULT_EXECUTION_CONFIG.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
    return path

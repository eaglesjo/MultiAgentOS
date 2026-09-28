"""Contracts for chat-facing AI agents used with VYRELON."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ChatAgentProvider(str, Enum):
    CHATGPT = "chatgpt"
    GEMINI = "gemini"
    CLAUDE = "claude"
    OTHER = "other"


@dataclass(frozen=True)
class ChatAgentContract:
    """A conversational agent that can drive or collaborate with VYRELON."""

    id: str
    provider: ChatAgentProvider
    name: str
    capabilities: frozenset[str] = frozenset()
    instruction_profile: str = "default"
    metadata: dict[str, object] = field(default_factory=dict)
    primary: bool = False

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("chat agent id must not be empty")
        if not self.name.strip():
            raise ValueError("chat agent name must not be empty")
        if self.primary and self.provider is not ChatAgentProvider.CHATGPT:
            raise ValueError("the default primary chat agent must be ChatGPT")

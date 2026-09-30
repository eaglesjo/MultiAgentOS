"""Explicit idempotency contract for durable tool replay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IdempotencyMode(StrEnum):
    NONE = "none"
    KEYED = "keyed"


@dataclass(frozen=True)
class IdempotencyContract:
    mode: IdempotencyMode
    key: str | None = None
    scope: str = "work_unit"

    def __post_init__(self) -> None:
        if self.mode == IdempotencyMode.KEYED and not self.key:
            raise ValueError("keyed idempotency requires a key")

    @property
    def replay_safe(self) -> bool:
        return self.mode == IdempotencyMode.KEYED and bool(self.key)

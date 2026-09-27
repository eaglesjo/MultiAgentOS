"""Provider-neutral IDE integration contracts for VYRELON."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class IDEKind(StrEnum):
    XCODE = "xcode"
    VS_CODE = "vs_code"
    ANDROID_STUDIO = "android_studio"


class IDEEventKind(StrEnum):
    CONTEXT_CHANGED = "context_changed"
    SELECTION_CHANGED = "selection_changed"
    FILE_OPENED = "file_opened"
    FILE_SAVED = "file_saved"
    WORKSPACE_OPENED = "workspace_opened"


class IDECommandKind(StrEnum):
    OPEN_WORKSPACE = "open_workspace"
    OPEN_FILE = "open_file"
    INSERT_TEXT = "insert_text"
    REPLACE_SELECTION = "replace_selection"
    RUN_COMMAND = "run_command"
    SHOW_MESSAGE = "show_message"
    SHOW_DIFF = "show_diff"


@dataclass(frozen=True)
class IDEContext:
    """Normalized editor/workspace context supplied by an IDE adapter."""

    kind: IDEKind
    project_root: str
    workspace_id: str | None = None
    file_path: str | None = None
    selection_start: int | None = None
    selection_end: int | None = None
    language_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class IDEEvent:
    """Normalized event sent from an IDE adapter to VYRELON."""

    kind: IDEEventKind
    context: IDEContext
    payload: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class IDECommand:
    """Normalized command sent from VYRELON to an IDE adapter."""

    kind: IDECommandKind
    arguments: dict[str, object] = field(default_factory=dict)
    context: IDEContext | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class IDECommandResult:
    """Normalized result returned by an IDE adapter."""

    ok: bool
    output: object = None
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class IDEAdapter(Protocol):
    """Thin IDE-specific bridge; VYRELON never imports an IDE SDK."""

    @property
    def kind(self) -> IDEKind:
        ...

    def capabilities(self) -> frozenset[str]:
        ...

    def context(self) -> IDEContext:
        ...

    def execute(self, command: IDECommand) -> IDECommandResult:
        ...


class IDEEventSink(Protocol):
    """Consumer for normalized IDE events flowing into VYRELON."""

    def handle(self, event: IDEEvent) -> object:
        ...

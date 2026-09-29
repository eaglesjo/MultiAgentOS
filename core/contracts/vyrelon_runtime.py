"""Compatibility shim for the legacy VYRELON runtime contract module.

New code should import from core.contracts.agent_execution_runtime.
"""

from core.contracts.agent_execution_runtime import (
    FallbackPolicy,
    ProtocolAdapter,
    RuntimeEvent,
    RuntimeEventKind,
    SessionSpec,
    SessionState,
    ToolRequest,
    ToolResult,
    ToolSideEffect,
    ToolSpec,
)

__all__ = [
    "FallbackPolicy",
    "ProtocolAdapter",
    "RuntimeEvent",
    "RuntimeEventKind",
    "SessionSpec",
    "SessionState",
    "ToolRequest",
    "ToolResult",
    "ToolSideEffect",
    "ToolSpec",
]

"""Canonical Agent Execution Runtime facade.

The legacy runtime.vyrelon module remains available for compatibility.
"""

from runtime.vyrelon import VYRELONRuntime


class AgentExecutionRuntime(VYRELONRuntime):
    """Canonical public name for the MultiAgentOS execution boundary."""


__all__ = ["AgentExecutionRuntime"]

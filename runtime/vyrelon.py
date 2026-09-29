"""Compatibility facade for the legacy VYRELON runtime name.

New code should import AgentExecutionRuntime from runtime.
"""

from runtime.agent_execution_runtime import AgentExecutionRuntime

VYRELONRuntime = AgentExecutionRuntime

__all__ = ["VYRELONRuntime"]

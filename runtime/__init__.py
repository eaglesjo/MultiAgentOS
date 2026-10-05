"""MultiAgentOS runtime facade exports.

The package intentionally avoids importing the high-level runtime facade during
package initialization. Runtime submodules are imported by core modules, so an
eager import here would create a core -> runtime -> core import cycle.

The facade remains available through lazy attribute resolution:
    from runtime import AgentExecutionRuntime
"""

__all__ = ["AgentExecutionRuntime"]


def __getattr__(name: str):
    if name == "AgentExecutionRuntime":
        from runtime.agent_execution_runtime import AgentExecutionRuntime

        return AgentExecutionRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

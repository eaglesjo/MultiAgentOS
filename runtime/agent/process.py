"""Process-backed AgentExecutor for the VYRELON lifecycle."""

from __future__ import annotations

from core.contracts.agent import AgentContract
from core.contracts.work_unit import WorkUnit
from runtime.process import ProcessResult, ProcessRuntime


class ProcessAgentExecutor:
    """Execute an agent's work through the local process runtime."""

    def __init__(self, command: list[str]) -> None:
        self.command = list(command)

    def execute(
        self, *, agent: AgentContract, model_id: str, work_unit: WorkUnit
    ) -> ProcessResult:
        work_unit.metadata["executor_agent"] = agent.id
        work_unit.metadata["model_id"] = model_id
        return ProcessRuntime().run(self.command, cwd=work_unit.metadata.get("cwd"))

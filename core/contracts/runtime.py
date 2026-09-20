"""Runtime contracts for executing work without coupling to a vendor."""

from dataclasses import dataclass
from typing import Protocol

from core.contracts.agent import AgentContract
from core.contracts.work_unit import WorkUnit


@dataclass(frozen=True)
class ExecutionRequest:
    agent: AgentContract
    model_id: str
    work_unit: WorkUnit


class RuntimeExecutor(Protocol):
    def execute(self, request: ExecutionRequest) -> object:
        ...

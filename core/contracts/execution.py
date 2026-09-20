"""Vendor-neutral execution and verification contracts."""

from typing import Protocol

from core.contracts.agent import AgentContract
from core.contracts.work_unit import WorkUnit


class AgentExecutor(Protocol):
    def execute(self, *, agent: AgentContract, model_id: str, work_unit: WorkUnit) -> object:
        ...


class ResultVerifier(Protocol):
    def verify(self, *, work_unit: WorkUnit, output: object) -> bool:
        ...

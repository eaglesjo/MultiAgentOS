"""Vendor-neutral execution, verification, and review contracts."""

from dataclasses import dataclass
from typing import Protocol

from core.contracts.agent import AgentContract
from core.contracts.work_unit import WorkUnit


class AgentExecutor(Protocol):
    def execute(self, *, agent: AgentContract, model_id: str, work_unit: WorkUnit) -> object:
        ...


class ResultVerifier(Protocol):
    def verify(self, *, work_unit: WorkUnit, output: object) -> bool:
        ...


@dataclass(frozen=True)
class ReviewDecision:
    approved: bool
    feedback: str = ""


class ResultReviewer(Protocol):
    def review(self, *, work_unit: WorkUnit, output: object) -> ReviewDecision:
        ...

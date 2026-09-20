"""VYRELON core contracts."""

from core.contracts.agent import AgentContract
from core.contracts.ai import AIProvider, ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier, ReviewDecision
from core.contracts.model_runtime import ModelAdapter, ModelRequest, ModelResponse
from core.contracts.runtime import ExecutionRequest, RuntimeExecutor
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.profile import DetectionResult, ProfileSpec
from core.contracts.planning import PlanStep, WorkPlan

__all__ = [
    "AgentContract", "AIProvider", "ModelSpec",
    "AgentExecutor", "ResultVerifier", "ResultReviewer", "ReviewDecision",
    "ModelAdapter", "ModelRequest", "ModelResponse",
    "ExecutionRequest", "RuntimeExecutor",
    "DetectionResult", "ProfileSpec", "PlanStep", "WorkPlan",
    "WorkStatus", "WorkUnit",
]

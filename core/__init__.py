"""VYRELON orchestration core."""

from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier, ReviewDecision
from core.contracts.model_runtime import ModelAdapter, ModelRequest, ModelResponse
from core.contracts.profile import DetectionResult, ProfileSpec
from core.contracts.runtime import ExecutionRequest, RuntimeExecutor
from core.delegation import Delegation, DelegationEngine
from core.lifecycle import LifecycleCoordinator, LifecycleError
from core.orchestrator import OrchestrationResult, Orchestrator
from core.registry import AIRegistry, AgentRegistry
from core.routing import AIRouter, Assignment, RoutingStrategy

__all__ = [
    "AIRegistry", "AgentRegistry", "AIRouter", "Assignment", "RoutingStrategy",
    "AgentExecutor", "ResultVerifier", "ResultReviewer", "ReviewDecision",
    "ModelAdapter", "ModelRequest", "ModelResponse",
    "ExecutionRequest", "RuntimeExecutor",
    "DetectionResult", "ProfileSpec",
    "Delegation", "DelegationEngine",
    "LifecycleCoordinator", "LifecycleError",
    "OrchestrationResult", "Orchestrator",
]

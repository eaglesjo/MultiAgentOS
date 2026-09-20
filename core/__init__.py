"""VYRELON orchestration core."""

from core.chat_agent_registry import ChatAgentRegistry, default_chat_agents
from core.contracts.chat_agent import ChatAgentContract, ChatAgentProvider
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier, ReviewDecision
from core.contracts.model_runtime import ModelAdapter, ModelRequest, ModelResponse
from core.contracts.profile import DetectionResult, ProfileSpec
from core.contracts.runtime import ExecutionRequest, RuntimeExecutor
from core.delegation import Delegation, DelegationEngine
from core.lifecycle import LifecycleCoordinator, LifecycleError
from core.orchestrator import OrchestrationResult, Orchestrator
from core.planning import BasicPlanner
from core.state import WorkStateStore
from core.registry import AIRegistry, AgentRegistry
from core.routing import AIRouter, Assignment, RoutingStrategy

__all__ = [
    "AIRegistry", "AgentRegistry", "ChatAgentRegistry", "ChatAgentContract", "ChatAgentProvider", "AIRouter", "Assignment", "RoutingStrategy",
    "AgentExecutor", "ResultVerifier", "ResultReviewer", "ReviewDecision",
    "ModelAdapter", "ModelRequest", "ModelResponse",
    "ExecutionRequest", "RuntimeExecutor",
    "DetectionResult", "ProfileSpec",
    "Delegation", "DelegationEngine",
    "LifecycleCoordinator", "LifecycleError",
    "OrchestrationResult", "Orchestrator", "BasicPlanner", "WorkStateStore",
]

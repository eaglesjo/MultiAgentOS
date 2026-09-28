"""Provider-neutral bridge between a Chat Agent and the VYRELON runtime."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4
from typing import Protocol

from core.chat_agent_registry import ChatAgentRegistry
from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.chat_agent import ChatAgentContract
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.planning import PlanStep, WorkPlan
from core.contracts.work_unit import WorkUnit
from core.orchestrator import OrchestrationResult, Orchestrator
from core.planning import BasicPlanner
from core.state import WorkStateStore
from core.chat_session import ChatSession, ChatSessionStore


VYRELON_AGENT_RULES: tuple[str, ...] = (
    "VYRELON is the execution authority.",
    "Never report an action as completed without execution evidence.",
    "Inspect relevant repository and runtime state before changing anything.",
    "Preserve user intent and do not silently expand scope.",
    "Respect repository boundaries; borrowed material is adapted into the target repository.",
    "Keep credentials and secrets outside source code and persistent project state.",
    "Use least privilege and obey VYRELON execution policy.",
    "Verify changes with appropriate tests or checks before declaring completion.",
    "Maintain WorkUnit, plan, artifact, finding, and handoff state.",
    "Consequential Git and GitHub mutations follow VYRELON approval policy.",
    "No Chat Agent provider has authority above VYRELON contracts.",
    "Required independent reviewers must not be bypassed.",
)


def build_agent_instructions(agent: ChatAgentContract) -> str:
    """Build the common instruction envelope for a connected Chat Agent."""
    rules = "\n".join(f"{index}. {rule}" for index, rule in enumerate(VYRELON_AGENT_RULES, 1))
    return (
        f"You are {agent.name}, a VYRELON Chat Agent.\n"
        f"Provider: {agent.provider.value}.\n"
        f"Instruction profile: {agent.instruction_profile}.\n\n"
        "Follow these mandatory VYRELON Agent Rules:\n"
        f"{rules}\n\n"
        "VYRELON is the execution authority. Use the capabilities exposed by VYRELON "
        "rather than inventing tool execution or bypassing runtime policy."
    )


@dataclass(frozen=True)
class ChatAgentRequest:
    """A user task entering VYRELON through a Chat Agent."""

    objective: str
    inputs: dict[str, object] | None = None
    work_unit_id: str | None = None


@dataclass(frozen=True)
class ChatAgentResponse:
    """Structured response returned by a Chat Agent adapter."""

    summary: str
    steps: tuple[PlanStep, ...] = ()
    findings: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChatAgentExecutionResult:
    """The complete result of turning a Chat Agent turn into VYRELON execution."""

    work_unit: WorkUnit
    plan: WorkPlan
    chat_response: ChatAgentResponse
    orchestration: OrchestrationResult


class ChatAgentAdapter(Protocol):
    """Provider adapter implemented by a connected Chat Agent."""

    def respond(
        self,
        *,
        agent: ChatAgentContract,
        instructions: str,
        request: ChatAgentRequest,
    ) -> ChatAgentResponse:
        """Return a structured response without directly owning VYRELON execution."""


class ChatAgentBridge:
    """Translate Chat Agent turns into VYRELON WorkUnits, Plans, and execution."""

    def __init__(
        self,
        registry: ChatAgentRegistry,
        planner: BasicPlanner | None = None,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        self.registry = registry
        self.planner = planner or BasicPlanner()
        self.orchestrator = orchestrator or Orchestrator()

    def instructions(self, agent_id: str | None = None) -> str:
        agent = self.registry.get(agent_id) if agent_id else self.registry.primary()
        return build_agent_instructions(agent)

    def request(
        self,
        request: ChatAgentRequest,
        adapter: ChatAgentAdapter,
        agent_id: str | None = None,
    ) -> tuple[WorkUnit, WorkPlan, ChatAgentResponse]:
        agent = self.registry.get(agent_id) if agent_id else self.registry.primary()
        if not request.objective.strip():
            raise ValueError("chat agent objective must not be empty")

        work_unit = WorkUnit(
            id=request.work_unit_id or f"chat-{agent.id}-{uuid4().hex}",
            objective=request.objective,
            inputs=dict(request.inputs or {}),
        )
        response = adapter.respond(
            agent=agent,
            instructions=build_agent_instructions(agent),
            request=request,
        )
        plan = self.planner.plan(work_unit, list(response.steps))
        work_unit.metadata["chat_agent_id"] = agent.id
        work_unit.metadata["chat_agent_summary"] = response.summary
        work_unit.metadata["chat_agent_findings"] = list(response.findings)
        work_unit.metadata["chat_agent_evidence"] = list(response.evidence)
        work_unit.artifacts.extend(response.artifacts)
        return work_unit, plan, response

    def execute(
        self,
        request: ChatAgentRequest,
        adapter: ChatAgentAdapter,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        *,
        chat_agent_id: str | None = None,
        preferred_model_ids: list[str] | None = None,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        routing_strategy="pool",
        state_store: WorkStateStore | None = None,
        session_store: ChatSessionStore | None = None,
        session: ChatSession | None = None,
    ) -> ChatAgentExecutionResult:
        """Run a Chat Agent request through the VYRELON execution lifecycle.

        The Chat Agent supplies intent and planning. The supplied AgentContract,
        model pool, executor, verifier, and reviewer determine actual execution.
        """
        work_unit, plan, response = self.request(
            request, adapter, agent_id=chat_agent_id
        )
        work_unit.metadata["execution_authority"] = "vyrelon"
        work_unit.metadata["execution_agent_id"] = agent.id
        if session is not None:
            session.work_unit_id = work_unit.id
            session.metadata["execution_agent_id"] = agent.id
        checkpoint_sequence = 0

        def checkpoint(unit: WorkUnit) -> None:
            nonlocal checkpoint_sequence
            checkpoint_sequence += 1
            unit.metadata["checkpoint"] = {
                "status": unit.status.value,
                "sequence": checkpoint_sequence,
            }
            if state_store is not None:
                state_store.checkpoint(
                    unit,
                    workflow="chat_execution",
                    stage=unit.status.value,
                    sequence=checkpoint_sequence,
                    next_action=(
                        "resume_execution"
                        if unit.status.value not in {"completed", "failed"}
                        else None
                    ),
                    agent_ids=(agent.id,),
                    model_ids=tuple(model.id for model in models),
                    resumable=unit.status.value not in {"completed", "failed"},
                )
            if session is not None:
                session.metadata["lifecycle_status"] = unit.status.value
                if session_store is not None:
                    session_store.save(session)
        checkpoint(work_unit)
        orchestration = self.orchestrator.run(
            work_unit=work_unit,
            agent=agent,
            models=models,
            executor=executor,
            preferred_model_ids=preferred_model_ids,
            verifier=verifier,
            reviewer=reviewer,
            routing_strategy=routing_strategy,
            checkpoint=checkpoint,
        )
        work_unit.metadata["execution_evidence"] = [
            f"VYRELON execution completed with agent {agent.id}",
            f"assigned model: {orchestration.delegation.assignment.model_id}",
        ]
        if verifier is not None:
            work_unit.metadata["verification_evidence"] = ["VYRELON verifier accepted output"]
        if reviewer is not None:
            work_unit.metadata["review_evidence"] = ["VYRELON reviewer approved output"]
        return ChatAgentExecutionResult(
            work_unit=work_unit,
            plan=plan,
            chat_response=response,
            orchestration=orchestration,
        )

    
    def resume(
        self,
        work_unit_id: str,
        *,
        state_store: WorkStateStore,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
    ) -> OrchestrationResult:
        """Resume a persisted WorkUnit after interruption."""
        work_unit = state_store.load(work_unit_id)
        if work_unit.status.value == "completed":
            raise ValueError(f"work unit is already completed: {work_unit_id}")
        if work_unit.status.value == "failed":
            raise ValueError(f"failed work unit requires explicit retry policy: {work_unit_id}")

        checkpoint_sequence = 0

        def checkpoint(unit: WorkUnit) -> None:
            nonlocal checkpoint_sequence
            checkpoint_sequence += 1
            unit.metadata["checkpoint"] = {
                "status": unit.status.value,
                "sequence": checkpoint_sequence,
            }
            state_store.checkpoint(
                unit,
                workflow="chat_execution",
                stage=unit.status.value,
                sequence=checkpoint_sequence,
                next_action=(
                    "resume_execution"
                    if unit.status.value not in {"completed", "failed"}
                    else None
                ),
                agent_ids=(agent.id,),
                model_ids=tuple(model.id for model in models),
                resumable=unit.status.value not in {"completed", "failed"},
            )

        return self.orchestrator.run(
            work_unit=work_unit,
            agent=agent,
            models=models,
            executor=executor,
            preferred_model_ids=preferred_model_ids,
            verifier=verifier,
            reviewer=reviewer,
            routing_strategy=routing_strategy,
            checkpoint=checkpoint,
        )

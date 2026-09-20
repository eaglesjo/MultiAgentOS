"""Provider-neutral bridge between a Chat Agent and the VYRELON runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.chat_agent_registry import ChatAgentRegistry
from core.contracts.chat_agent import ChatAgentContract
from core.contracts.planning import PlanStep, WorkPlan
from core.contracts.work_unit import WorkUnit
from core.planning import BasicPlanner


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
    """Translate Chat Agent turns into VYRELON WorkUnits and Plans."""

    def __init__(
        self,
        registry: ChatAgentRegistry,
        planner: BasicPlanner | None = None,
    ) -> None:
        self.registry = registry
        self.planner = planner or BasicPlanner()

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
            id=request.work_unit_id or f"chat-{agent.id}",
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

"""Sequential multi-agent handoff workflow for VYRELON."""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.handoff import ArtifactContract, HandoffArtifact, ReviewResult
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.delegation import Delegation, DelegationEngine
from core.handoff import HandoffManager, ReviewPanel
from core.routing import RoutingStrategy


@dataclass(frozen=True)
class AgentStageResult:
    agent_id: str
    delegation: Delegation
    output: object
    handoff: HandoffArtifact | None = None
    artifacts: tuple[ArtifactContract, ...] = ()


@dataclass(frozen=True)
class MultiAgentWorkflowResult:
    work_unit: WorkUnit
    stages: tuple[AgentStageResult, ...]
    final_output: object
    reviews: tuple[ReviewResult, ...] = ()


class MultiAgentWorkflow:
    """Run one WorkUnit through cooperating agents under VYRELON authority.

    Agents never transfer execution authority directly to one another. VYRELON
    performs each delegation and records the handoff artifact between stages.
    """

    def __init__(
        self,
        delegation: DelegationEngine | None = None,
        handoffs: HandoffManager | None = None,
        review_panel: ReviewPanel | None = None,
    ) -> None:
        self.delegation = delegation or DelegationEngine()
        self.handoffs = handoffs or HandoffManager()
        self.review_panel = review_panel or ReviewPanel()

    def run(
        self,
        *,
        work_unit: WorkUnit,
        stages: list[AgentContract],
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        reviewers: list[tuple[AgentContract, object]] | None = None,
        reviewer_runner=None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        artifact_store=None,
    ) -> MultiAgentWorkflowResult:
        if not stages:
            raise ValueError("multi-agent workflow requires at least one stage")

        results: list[AgentStageResult] = []
        previous_agent: AgentContract | None = None
        previous_output: object = None

        for agent in stages:
            delegation = self.delegation.delegate(
                work_unit,
                agent,
                models,
                preferred_model_ids,
                routing_strategy,
            )
            output = executor.execute(
                agent=agent,
                model_id=delegation.assignment.model_id,
                work_unit=work_unit,
            )
            stage_artifacts = tuple(
                artifact for artifact in work_unit.metadata.get("artifacts", ())
                if isinstance(artifact, ArtifactContract)
            )
            for artifact in stage_artifacts:
                artifact.validate()
                if artifact_store is not None:
                    artifact_store.save(artifact)
            work_unit.metadata.setdefault("artifact_ids", []).extend(
                artifact.id for artifact in stage_artifacts
            )
            work_unit.artifacts.extend(
                artifact.id for artifact in stage_artifacts if artifact.id not in work_unit.artifacts
            )
            handoff = None
            if previous_agent is not None:
                handoff = self.handoffs.create(
                    work_unit.id,
                    previous_agent,
                    agent,
                    summary=f"Handoff from {previous_agent.id} to {agent.id}",
                    artifacts=work_unit.artifacts,
                    findings=tuple(work_unit.metadata.get("findings", ())),
                )
                work_unit.metadata.setdefault("handoffs", []).append({
                    "from_agent": handoff.from_agent,
                    "to_agent": handoff.to_agent,
                    "summary": handoff.summary,
                })
            results.append(AgentStageResult(agent.id, delegation, output, handoff, stage_artifacts))
            previous_agent = agent
            previous_output = output

        if verifier is not None:
            work_unit.transition(WorkStatus.VERIFYING)
            if not verifier.verify(work_unit=work_unit, output=previous_output):
                work_unit.transition(WorkStatus.FAILED)
                raise RuntimeError(f"verification failed for work unit: {work_unit.id}")

        reviews: tuple[ReviewResult, ...] = ()
        if reviewers:
            if reviewer_runner is None:
                raise ValueError("reviewer_runner is required when reviewers are provided")
            if work_unit.status != WorkStatus.VERIFYING:
                work_unit.transition(WorkStatus.VERIFYING)
            work_unit.transition(WorkStatus.REVIEWING)
            panel = self.review_panel.review(
                work_unit.id,
                reviewers,
                reviewer_runner,
            )
            reviews = panel.reviews
            work_unit.metadata["review_consensus"] = panel.consensus
            if not panel.approved:
                work_unit.transition(WorkStatus.FAILED)
                raise RuntimeError(f"review rejected work unit: {work_unit.id}")

        if verifier is not None or reviewers:
            work_unit.transition(WorkStatus.HANDOFF)
        work_unit.transition(WorkStatus.COMPLETED)
        work_unit.metadata["execution_agent_ids"] = [stage.agent_id for stage in results]
        work_unit.metadata["multi_agent_stage_count"] = len(results)
        return MultiAgentWorkflowResult(
            work_unit=work_unit,
            stages=tuple(results),
            final_output=previous_output,
            reviews=reviews,
        )

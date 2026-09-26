"""Sequential multi-agent handoff workflow for VYRELON."""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.handoff import ArtifactContract, HandoffArtifact, ReviewContext, ReviewResult
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.resume import WorkflowResumeContext
from core.delegation import Delegation, DelegationEngine
from core.handoff import HandoffManager, ReviewPanel
from core.routing import RoutingStrategy


def _checkpoint_value(value: object) -> object:
    """Return a JSON-safe execution snapshot for durable recovery."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _checkpoint_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_checkpoint_value(item) for item in value]
    return {"repr": repr(value), "type": type(value).__name__}


@dataclass(frozen=True)
class AgentStageResult:
    agent_id: str
    delegation: Delegation
    output: object
    handoff: HandoffArtifact | None = None
    artifacts: tuple[ArtifactContract, ...] = ()
    findings: tuple[str, ...] = ()


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

    def run_with_debug_retry(
        self,
        *,
        work_unit: WorkUnit,
        developer: AgentContract,
        tester: AgentContract,
        debugger: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier,
        max_retries: int = 2,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        artifact_store=None,
    ) -> MultiAgentWorkflowResult:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        stages: list[AgentStageResult] = []
        previous_output = None
        for attempt in range(max_retries + 1):
            agent = developer if attempt == 0 else debugger
            delegation = self.delegation.delegate(work_unit, agent, models, preferred_model_ids, routing_strategy)
            output = executor.execute(agent=agent, model_id=delegation.assignment.model_id, work_unit=work_unit)
            stages.append(AgentStageResult(agent.id, delegation, output))
            tester_delegation = self.delegation.delegate(
                work_unit, tester, models, preferred_model_ids, routing_strategy
            )
            previous_output = executor.execute(
                agent=tester,
                model_id=tester_delegation.assignment.model_id,
                work_unit=work_unit,
            )
            stages.append(
                AgentStageResult(tester.id, tester_delegation, previous_output)
            )
            work_unit.transition(WorkStatus.VERIFYING)
            if verifier.verify(work_unit=work_unit, output=previous_output):
                work_unit.transition(WorkStatus.HANDOFF)
                work_unit.transition(WorkStatus.COMPLETED)
                work_unit.metadata["retry_count"] = attempt
                return MultiAgentWorkflowResult(work_unit, tuple(stages), previous_output)
            work_unit.metadata.setdefault("findings", []).append(f"verification failed on attempt {attempt + 1}")
            if attempt < max_retries:
                work_unit.transition(WorkStatus.EXECUTING)
                work_unit.metadata["stage_input"] = {
                    "from_agent": tester.id,
                    "artifacts": tuple(work_unit.artifacts),
                    "findings": tuple(work_unit.metadata.get("findings", ())),
                }
        work_unit.transition(WorkStatus.FAILED)
        work_unit.metadata["retry_count"] = max_retries + 1
        raise RuntimeError(f"verification failed after {max_retries + 1} attempts for work unit: {work_unit.id}")
    def run_with_review_rework(
        self,
        *,
        work_unit: WorkUnit,
        developer: AgentContract,
        tester: AgentContract,
        reviewers: list[tuple[AgentContract, object]],
        models: list[ModelSpec],
        executor: AgentExecutor,
        reviewer_runner,
        verifier: ResultVerifier | None = None,
        max_review_cycles: int = 2,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        artifact_store=None,
        checkpoint=None,
        start_cycle: int = 0,
        resume_action: str | None = None,
        resume_output: object = None,
    ) -> MultiAgentWorkflowResult:
        """Run Developer -> Tester -> Review and bounded reviewer-requested rework."""
        if max_review_cycles < 1:
            raise ValueError("max_review_cycles must be >= 1")
        if not reviewers:
            raise ValueError("reviewers are required")
        if reviewer_runner is None:
            raise ValueError("reviewer_runner is required")

        if start_cycle < 0 or start_cycle > max_review_cycles:
            raise ValueError("start_cycle must be within review cycle bounds")
        if resume_action not in {None, "verify", "review", "rework"}:
            raise ValueError("unsupported review-rework resume action")
        if resume_action in {"verify", "review"} and start_cycle >= max_review_cycles:
            raise ValueError("resume cycle must be within review cycle bounds")

        stages: list[AgentStageResult] = []
        reviews: list[ReviewResult] = []
        previous_agent: AgentContract | None = tester if resume_action in {"verify", "review"} else None
        previous_output: object = resume_output if resume_action in {"verify", "review"} else None

        for cycle in range(start_cycle, max_review_cycles):
            work_unit.metadata["review_cycle"] = cycle + 1
            work_unit.metadata["checkpoint_next_action"] = "rework"
            if checkpoint is not None:
                checkpoint(work_unit, stage="rework", sequence=cycle,
                           next_action="rework", agent_ids=(developer.id, tester.id, *[agent.id for agent, _ in reviewers]),
                           model_ids=tuple(model.id for model in models))
            if resume_action not in {"verify", "review"}:
                for agent in (developer, tester):
                        work_unit.metadata["stage_input"] = {
                        "from_agent": previous_agent.id if previous_agent else None,
                        "artifacts": tuple(work_unit.artifacts),
                        "findings": tuple(work_unit.metadata.get("findings", ())),
                        "review_cycle": cycle + 1,
                    }
                    delegation = self.delegation.delegate(
                        work_unit, agent, models, preferred_model_ids, routing_strategy
                    )
                    output = executor.execute(
                        agent=agent,
                        model_id=delegation.assignment.model_id,
                        work_unit=work_unit,
                    )
                    stage_findings = tuple(work_unit.metadata.get("stage_findings", ()))
                    stage_artifacts = tuple(
                        artifact for artifact in work_unit.metadata.get("artifacts", ())
                        if isinstance(artifact, ArtifactContract)
                    )
                    for artifact in stage_artifacts:
                        artifact.validate()
                        if artifact_store is not None:
                            artifact_store.save(artifact)
                    for artifact in stage_artifacts:
                        if artifact.id not in work_unit.artifacts:
                            work_unit.artifacts.append(artifact.id)
                    work_unit.metadata.setdefault("artifact_ids", [])
                    for artifact in stage_artifacts:
                        if artifact.id not in work_unit.metadata["artifact_ids"]:
                            work_unit.metadata["artifact_ids"].append(artifact.id)
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
                            "review_cycle": cycle + 1,
                        })
                    stages.append(
                        AgentStageResult(
                            agent.id, delegation, output, handoff,
                            stage_artifacts, stage_findings
                        )
                    )
                    previous_agent = agent
                    previous_output = output

            if verifier is not None:
                work_unit.metadata["checkpoint_output"] = _checkpoint_value(previous_output)
                work_unit.metadata["checkpoint_next_action"] = "verify"
                if checkpoint is not None:
                    checkpoint(work_unit, stage="verification", sequence=cycle + 1,
                               next_action="verify", agent_ids=(developer.id, tester.id, *[agent.id for agent, _ in reviewers]),
                               model_ids=tuple(model.id for model in models))
                work_unit.transition(WorkStatus.VERIFYING)
                if not verifier.verify(work_unit=work_unit, output=previous_output):
                    work_unit.metadata.setdefault("findings", []).append(
                        f"verification failed before review cycle {cycle + 1}"
                    )
                    if cycle + 1 < max_review_cycles:
                        work_unit.transition(WorkStatus.EXECUTING)
                        continue
                    work_unit.transition(WorkStatus.FAILED)
                    work_unit.metadata["review_cycle_count"] = cycle + 1
                    raise RuntimeError(
                        f"verification failed after {cycle + 1} review cycles for work unit: {work_unit.id}"
                    )
            elif work_unit.status == WorkStatus.EXECUTING:
                work_unit.transition(WorkStatus.VERIFYING)

            work_unit.metadata["checkpoint_next_action"] = "review"
            if checkpoint is not None:
                checkpoint(work_unit, stage="review", sequence=cycle + 1,
                           next_action="review", agent_ids=(developer.id, tester.id, *[agent.id for agent, _ in reviewers]),
                           model_ids=tuple(model.id for model in models))
            work_unit.transition(WorkStatus.REVIEWING)
            review_context = ReviewContext(
                work_unit_id=work_unit.id,
                artifact_ids=tuple(work_unit.artifacts),
                findings=tuple(work_unit.metadata.get("findings", ())),
                last_agent_id=previous_agent.id if previous_agent else None,
                review_cycle=cycle + 1,
                metadata={"objective": work_unit.objective},
            )
            panel = self.review_panel.review(
                work_unit.id,
                reviewers,
                reviewer_runner,
                context=review_context,
            )
            reviews.extend(panel.reviews)
            work_unit.metadata.setdefault("review_history", []).append({
                "cycle": cycle + 1,
                "approved": panel.approved,
                "consensus": panel.consensus,
                "feedback": [review.feedback for review in panel.reviews],
            })
            if panel.approved:
                work_unit.metadata["review_cycle_count"] = cycle + 1
                work_unit.metadata["review_consensus"] = panel.consensus
                work_unit.transition(WorkStatus.HANDOFF)
                work_unit.transition(WorkStatus.COMPLETED)
                work_unit.metadata["execution_agent_ids"] = [stage.agent_id for stage in stages]
                work_unit.metadata["multi_agent_stage_count"] = len(stages)
                return MultiAgentWorkflowResult(
                    work_unit, tuple(stages), previous_output, tuple(reviews)
                )

            for review in panel.reviews:
                if review.feedback.strip():
                    work_unit.metadata.setdefault("findings", []).append(
                        f"{review.reviewer_id}: {review.feedback}"
                    )

            if cycle + 1 < max_review_cycles:
                work_unit.metadata["rework_required"] = True
                work_unit.transition(WorkStatus.EXECUTING)
                if checkpoint is not None:
                    checkpoint(work_unit, stage="rework", sequence=cycle + 1,
                               next_action="rework", agent_ids=(developer.id, tester.id, *[agent.id for agent, _ in reviewers]),
                               model_ids=tuple(model.id for model in models))
                continue

            work_unit.metadata["review_cycle_count"] = cycle + 1
            work_unit.metadata["review_consensus"] = panel.consensus
            work_unit.metadata["rework_required"] = True
            work_unit.metadata["human_review_required"] = True
            work_unit.metadata["human_review_reason"] = (
                f"review rejected after {cycle + 1} cycles"
            )
            work_unit.metadata["resume_context"] = WorkflowResumeContext(
                workflow="review_rework",
                work_unit_id=work_unit.id,
                review_cycle=cycle + 1,
                max_review_cycles=max_review_cycles,
                developer_id=developer.id,
                tester_id=tester.id,
                reviewer_ids=tuple(agent.id for agent, _ in reviewers),
                model_ids=tuple(model.id for model in models),
                artifact_ids=tuple(work_unit.artifacts),
                findings=tuple(work_unit.metadata.get("findings", ())),
                last_agent_id=previous_agent.id if previous_agent else None,
            ).to_metadata()
            work_unit.transition(WorkStatus.WAITING_HUMAN_APPROVAL)
            if checkpoint is not None:
                checkpoint(work_unit, stage="human_gate", sequence=cycle + 1,
                           next_action="human_review", agent_ids=(developer.id, tester.id, *[agent.id for agent, _ in reviewers]),
                           model_ids=tuple(model.id for model in models), resumable=True)
            return MultiAgentWorkflowResult(
                work_unit, tuple(stages), previous_output, tuple(reviews)
            )

        raise RuntimeError("review rework loop exited without a terminal result")

    def resolve_human_review(
        self,
        *,
        work_unit: WorkUnit,
        approved: bool,
        notes: str = "",
    ) -> MultiAgentWorkflowResult:
        """Resolve a bounded-workflow escalation with an explicit human decision."""
        if work_unit.status is not WorkStatus.WAITING_HUMAN_APPROVAL:
            raise ValueError("work unit is not waiting for human approval")

        work_unit.metadata["human_review_required"] = False
        work_unit.metadata["human_review_decision"] = "approved" if approved else "rejected"
        if notes.strip():
            work_unit.metadata["human_review_notes"] = notes

        if approved:
            work_unit.metadata["rework_required"] = False
            work_unit.transition(WorkStatus.HANDOFF)
            work_unit.transition(WorkStatus.COMPLETED)
        else:
            work_unit.metadata["rework_required"] = False
            work_unit.transition(WorkStatus.FAILED)

        return MultiAgentWorkflowResult(
            work_unit=work_unit,
            stages=(),
            final_output=None,
            reviews=(),
        )

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
        checkpoint=None,
        start_stage_index: int = 0,
        resume_action: str | None = None,
        resume_output: object = None,
    ) -> MultiAgentWorkflowResult:
        if not stages:
            raise ValueError("multi-agent workflow requires at least one stage")

        if start_stage_index < 0 or start_stage_index > len(stages):
            raise ValueError("start_stage_index must be within the stage list")

        if resume_action not in {None, "verify", "review"}:
            raise ValueError("unsupported multi-agent resume action")
        if resume_action is not None and start_stage_index != len(stages):
            raise ValueError("resume_action requires all execution stages to be complete")

        results: list[AgentStageResult] = []
        previous_agent: AgentContract | None = stages[start_stage_index - 1] if start_stage_index else None
        previous_output: object = resume_output if resume_action is not None else None
        previous_artifacts: tuple[ArtifactContract, ...] = ()
        previous_findings: tuple[str, ...] = tuple(work_unit.metadata.get("findings", ()))

        for stage_index, agent in enumerate(stages[start_stage_index:], start=start_stage_index):
            work_unit.metadata["checkpoint_stage_index"] = stage_index
            work_unit.metadata["checkpoint_next_action"] = "execute_stage"
            if checkpoint is not None:
                checkpoint(work_unit, stage=agent.id, sequence=stage_index,
                           next_action="execute_stage",
                           agent_ids=tuple(a.id for a in stages),
                           model_ids=tuple(model.id for model in models))
            work_unit.metadata["stage_input"] = {
                "from_agent": previous_agent.id if previous_agent else None,
                "artifacts": tuple(a.id for a in previous_artifacts),
                "findings": previous_findings,
            }
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
            work_unit.metadata["checkpoint_output"] = _checkpoint_value(output)
            work_unit.metadata["checkpoint_stage_index"] = stage_index + 1
            work_unit.metadata["checkpoint_next_action"] = (
                "execute_stage" if stage_index + 1 < len(stages) else "verify"
            )
            if checkpoint is not None:
                checkpoint(work_unit, stage=agent.id, sequence=stage_index + 1,
                           next_action=work_unit.metadata["checkpoint_next_action"],
                           agent_ids=tuple(a.id for a in stages),
                           model_ids=tuple(model.id for model in models))
            stage_findings = tuple(work_unit.metadata.get("stage_findings", ()))
            previous_findings = stage_findings
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
            previous_artifacts = stage_artifacts
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
            results.append(AgentStageResult(agent.id, delegation, output, handoff, stage_artifacts, stage_findings))
            previous_agent = agent
            previous_output = output

        if verifier is not None and resume_action != "review":
            work_unit.metadata["checkpoint_next_action"] = "verify"
            work_unit.metadata["checkpoint_output"] = _checkpoint_value(previous_output)
            if checkpoint is not None:
                checkpoint(work_unit, stage="verification", sequence=len(stages),
                           next_action="verify", agent_ids=tuple(a.id for a in stages),
                           model_ids=tuple(model.id for model in models))
            work_unit.transition(WorkStatus.VERIFYING)
            if not verifier.verify(work_unit=work_unit, output=previous_output):
                work_unit.transition(WorkStatus.FAILED)
                if checkpoint is not None:
                    checkpoint(work_unit, stage="verification", sequence=len(stages),
                               next_action=None, agent_ids=tuple(a.id for a in stages),
                               model_ids=tuple(model.id for model in models), resumable=False)
                raise RuntimeError(f"verification failed for work unit: {work_unit.id}")

        if resume_action == "verify" and work_unit.status == WorkStatus.EXECUTING:
            work_unit.transition(WorkStatus.VERIFYING)
        elif resume_action == "review" and work_unit.status == WorkStatus.EXECUTING:
            work_unit.transition(WorkStatus.VERIFYING)

        reviews: tuple[ReviewResult, ...] = ()
        if reviewers:
            if reviewer_runner is None:
                raise ValueError("reviewer_runner is required when reviewers are provided")
            work_unit.metadata["checkpoint_next_action"] = "review"
            if checkpoint is not None:
                checkpoint(work_unit, stage="review", sequence=len(stages),
                           next_action="review", agent_ids=tuple(a.id for a in stages),
                           model_ids=tuple(model.id for model in models))
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
                work_unit.metadata["findings"] = [
                    *work_unit.metadata.get("findings", []),
                    *[review.feedback for review in panel.reviews if review.feedback.strip()],
                ]
                work_unit.transition(WorkStatus.FAILED)
                if checkpoint is not None:
                    checkpoint(work_unit, stage="review", sequence=len(stages),
                               next_action=None, agent_ids=tuple(a.id for a in stages),
                               model_ids=tuple(model.id for model in models), resumable=False)
                raise RuntimeError(f"review rejected work unit: {work_unit.id}")

        if verifier is not None or reviewers:
            work_unit.transition(WorkStatus.HANDOFF)
        work_unit.transition(WorkStatus.COMPLETED)
        work_unit.metadata["execution_agent_ids"] = [stage.agent_id for stage in results]
        work_unit.metadata["multi_agent_stage_count"] = len(results)
        work_unit.metadata["checkpoint_next_action"] = None
        if checkpoint is not None:
            checkpoint(
                work_unit,
                stage="completed",
                sequence=len(stages),
                next_action=None,
                agent_ids=tuple(a.id for a in stages),
                model_ids=tuple(model.id for model in models),
                resumable=False,
            )
        return MultiAgentWorkflowResult(
            work_unit=work_unit,
            stages=tuple(results),
            final_output=previous_output,
            reviews=reviews,
        )

from dataclasses import dataclass

from core.agent_selection_policy import SelectionDecision
from core.contracts.agent import AgentContract
from core.contracts.agent_selection import AgentCandidate
from core.contracts.evidence import EvidenceRecord
from core.contracts.work_unit import WorkUnit
from core.routing import AIRouter, RoutingStrategy
from runtime.model.ai_runtime import AIRuntime
from runtime.agent_selection import ModelBackedAgentSelector


@dataclass(frozen=True)
class AIRouterBackedAgentSelector:
    """Use AIRouter to choose the model behind the Agent-selection strategy."""

    router: AIRouter
    runtime: AIRuntime
    selector_agent: AgentContract
    models: tuple
    preferred_model_ids: tuple[str, ...] = ()
    routing_strategy: RoutingStrategy | str = RoutingStrategy.AUTO

    def select(
        self,
        *,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
        candidates: tuple[AgentCandidate, ...],
    ) -> SelectionDecision:
        assignment = self.router.assign(
            self.selector_agent,
            list(self.models),
            preferred_model_ids=list(self.preferred_model_ids) or None,
            strategy=self.routing_strategy,
        )
        selector = ModelBackedAgentSelector(
            runtime=self.runtime,
            model_id=assignment.model_id,
        )
        return selector.select(
            work_unit=work_unit,
            evidence=evidence,
            candidates=candidates,
        )

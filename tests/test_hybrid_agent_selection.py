"""End-to-end test for deterministic selection, AIRouter, LLM proposal, and policy."""

from core.agent_selector import DeterministicAgentSelector
from core.contracts.agent import AgentContract, AgentTaxonomy
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelResponse
from core.contracts.work_unit import WorkUnit
from core.agent_selection_policy import AgentSelectionPolicy
from core.routing import AIRouter
from runtime.airouter_agent_selector import AIRouterLLMSelector
from runtime.model.ai_runtime import AIRuntime


class _Adapter:
    def generate(self, model, request):
        return ModelResponse(
            text=(
                '{"selected_agents":['
                '"file-picker","planner","development",'
                '"development-research-android","android-developer",'
                '"editor","executor","reviewer"],'
                '"confidence":0.94,'
                '"reasons":["LLM confirmed the deterministic Android route"]}'
            ),
            model_id=model.id,
        )


def test_full_hybrid_selection_pipeline():
    selector_agent = AgentContract(
        id="agent-selector",
        role="agent-selector",
        kind="governance",
        taxonomy=AgentTaxonomy(layer="governance"),
    )
    model = ModelSpec("selector-model", "test")
    runtime = AIRuntime(
        models={"selector-model": model},
        adapters={"selector-model": _Adapter()},
    )
    llm_selector = AIRouterLLMSelector(
        router=AIRouter(),
        runtime=runtime,
        selector_agent=selector_agent,
        models=(model,),
    )
    work_unit = WorkUnit(
        id="wu-full-hybrid",
        objective="Implement Android settings",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )

    selection = DeterministicAgentSelector(
        llm_selector=llm_selector,
        selection_policy=AgentSelectionPolicy(confidence_threshold=1.0),
    ).select(work_unit)

    assert selection.plan.selection_mode == "hybrid"
    assert selection.plan.confidence == 0.94
    assert selection.plan.selected_agents[0] == "file-picker"
    assert selection.plan.selected_agents[-1] == "reviewer"
    assert work_unit.assigned_agents == list(selection.plan.route)

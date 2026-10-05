"""End-to-end test for deterministic selection, AIRouter, model proposal, and policy."""

from core.agent_selector import DeterministicAgentSelector
from core.contracts.agent import AgentContract, AgentTaxonomy
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelResponse
from core.contracts.work_unit import WorkUnit
from core.agent_selection_policy import AgentSelectionPolicy
from core.routing import AIRouter
from runtime.airouter_agent_selector import AIRouterBackedAgentSelector
from runtime.agent_selection import ModelBackedAgentSelector
from runtime.model.ai_runtime import AIRuntime


class _Adapter:
    def generate(self, model, request):
        import json

        payload = json.loads(request.prompt)
        stage_index = payload.get("stage_index")
        candidates = payload.get("candidate_pool", [])
        if stage_index is None:
            selected = [item["agent_id"] for item in candidates]
        else:
            ranked = payload.get("stage_rankings", {}).get(str(stage_index), [])
            selected = [ranked[0]["agent_id"]] if ranked else [candidates[0]["agent_id"]]
        return ModelResponse(
            text=json.dumps({
                "selected_agents": selected,
                "confidence": 0.94,
                "reasons": ["Model confirmed the deterministic Android stage"],
            }),
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
    selection_strategy = AIRouterBackedAgentSelector(
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

    from agents.registry import build_registry
    selection = DeterministicAgentSelector(
        registry=build_registry(("android-native",)),
        selection_strategy=selection_strategy,
        selection_policy=AgentSelectionPolicy(confidence_threshold=1.0),
    ).select(work_unit)

    assert selection.plan.selection_mode == "hybrid"
    assert selection.plan.confidence == 0.94
    assert selection.plan.selected_agents[0] == "file-picker"
    assert selection.plan.selected_agents[-1] == "reviewer"
    assert work_unit.assigned_agents == list(selection.plan.route)


def test_stage_selector_accepts_full_route_response_and_extracts_stage_candidate():
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
    selector = ModelBackedAgentSelector(
        runtime=runtime,
        model_id="selector-model",
    )
    work_unit = WorkUnit(
        id="wu-stage-selector",
        objective="Implement Android settings",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )
    from core.contracts.agent_selection import AgentCandidate
    candidates = (
        AgentCandidate(
            agent_id="android-developer",
            score=0.70,
            stage_indices=(4,),
        ),
    )

    decision = selector.select_stage(
        work_unit=work_unit,
        evidence=(),
        candidates=candidates,
        stage_index=4,
    )

    assert decision.selected_agents == ("android-developer",)

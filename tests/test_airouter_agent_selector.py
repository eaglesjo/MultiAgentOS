"""Tests for AIRouter-backed Agent selection."""

from core.contracts.agent import AgentContract, AgentTaxonomy
from core.contracts.agent_selection import AgentCandidate
from core.contracts.ai import ModelSpec
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.model_runtime import ModelResponse
from core.contracts.work_unit import WorkUnit
from core.routing import AIRouter
from runtime.airouter_agent_selector import AIRouterBackedAgentSelector
from runtime.model.ai_runtime import AIRuntime


class _SelectorAdapter:
    def generate(self, model, request):
        return ModelResponse(
            text='{"selected_agents":["android-developer"],"confidence":0.93,"reasons":["best match"]}',
            model_id=model.id,
        )


def test_airouter_selects_model_before_llm_agent_selection():
    selector_agent = AgentContract(
        id="agent-selector",
        role="agent-selector",
        kind="governance",
        taxonomy=AgentTaxonomy(layer="governance"),
    )
    model = ModelSpec(
        id="selector-model",
        provider_id="test",
        capabilities=frozenset(),
    )
    runtime = AIRuntime(
        models={"selector-model": model},
        adapters={"selector-model": _SelectorAdapter()},
    )
    selector = AIRouterLLMSelector(
        router=AIRouter(),
        runtime=runtime,
        selector_agent=selector_agent,
        models=(model,),
    )
    work_unit = WorkUnit(
        id="wu-router-selector",
        objective="Choose Android implementation agent",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )
    evidence = (
        EvidenceRecord(
            id="e1",
            work_unit_id=work_unit.id,
            kind=EvidenceKind.FACT,
            source="test",
            statement="platform=android",
        ),
    )
    candidates = (
        AgentCandidate("android-developer", 0.9, ("platform match",), ("e1",)),
    )

    decision = selector.select(
        work_unit=work_unit,
        evidence=evidence,
        candidates=candidates,
    )

    assert decision.selected_agents == ("android-developer",)
    assert decision.confidence == 0.93

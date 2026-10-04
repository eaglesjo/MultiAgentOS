"""Tests for the model-backed Agent selector."""

from core.contracts.agent_selection import AgentCandidate
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelResponse
from core.contracts.work_unit import WorkUnit
from runtime.agent_selection import ModelBackedAgentSelector
from runtime.model.ai_runtime import AIRuntime


class _SelectorAdapter:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, model, request):
        return ModelResponse(text=self.text, model_id=model.id)


def _selector(response: str) -> AIRuntimeLLMSelector:
    runtime = AIRuntime(
        models={"selector-model": ModelSpec("selector-model", "test")},
        adapters={"selector-model": _SelectorAdapter(response)},
    )
    return AIRuntimeLLMSelector(runtime=runtime, model_id="selector-model")


def _inputs():
    work_unit = WorkUnit(
        id="wu-llm",
        objective="Choose the best Android implementation route",
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
        AgentCandidate("android-developer", 0.90, ("platform match",), ("e1",)),
        AgentCandidate("development-research-android", 0.85, ("research match",), ("e1",)),
    )
    return work_unit, evidence, candidates


def test_model_backed_selector_uses_existing_ai_runtime():
    selector = _selector(
        '{"selected_agents":["android-developer"],"confidence":0.91,'
        '"reasons":["Android Kotlin implementation is the strongest match"]}'
    )
    work_unit, evidence, candidates = _inputs()

    decision = selector.select(
        work_unit=work_unit,
        evidence=evidence,
        candidates=candidates,
    )

    assert decision.selected_agents == ("android-developer",)
    assert decision.confidence == 0.91
    assert decision.reasons


def test_model_backed_selector_rejects_unknown_agent():
    selector = _selector(
        '{"selected_agents":["unknown-agent"],"confidence":0.9,"reasons":[]}'
    )
    work_unit, evidence, candidates = _inputs()

    try:
        selector.select(
            work_unit=work_unit,
            evidence=evidence,
            candidates=candidates,
        )
    except ValueError as exc:
        assert "outside the candidate set" in str(exc)
    else:
        raise AssertionError("unknown Agent should be rejected")

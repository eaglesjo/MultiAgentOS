from types import SimpleNamespace

from core.contracts.agent import AgentContract, AgentTaxonomy
from core.contracts.agent_selection import AgentCandidate, AgentPlan, StageConfidence
from core.contracts.ai import ModelSpec
from core.contracts.work_unit import WorkUnit
from runtime.adaptive_agent_execution import (
    RuntimeExecutionEvidenceCollector,
    RuntimeStageExecutor,
)


def _agent(agent_id="android-developer"):
    return AgentContract(
        id=agent_id,
        role="Android developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development", platform="android"),
    )


def _plan(work_unit_id="wu-1", agent_id="android-developer"):
    return AgentPlan(
        work_unit_id=work_unit_id,
        selected_agents=(agent_id,),
        route=(agent_id,),
        candidates=(
            AgentCandidate(
                agent_id=agent_id,
                score=0.8,
                stage_indices=(0,),
            ),
        ),
        stage_confidences=(
            StageConfidence(0, agent_id, 0.8, 0.8, 1.0, 0.0),
        ),
        confidence=0.89,
    )


class _Delegation:
    def delegate(self, work_unit, agent, models, preferred_model_ids=None, strategy="pool"):
        return SimpleNamespace(
            assignment=SimpleNamespace(model_id=models[0].id)
        )


class _Executor:
    def execute(self, *, agent, model_id, work_unit):
        return {"agent": agent.id, "model": model_id}


class _EventStore:
    def load(self, work_unit_id):
        return (
            {
                "sequence": 4,
                "kind": "tool_result",
                "payload": {
                    "tool_id": "mcp.github.search",
                    "invocation_id": "inv-1",
                    "ok": True,
                },
            },
        )


class _LedgerStore:
    def load(self, work_unit_id):
        return (
            SimpleNamespace(
                sequence=4,
                invocation_id="inv-1",
                tool_id="mcp.github.search",
                state="completed",
            ),
        )


def test_runtime_stage_executor_uses_native_agent_executor_boundary():
    work_unit = WorkUnit(id="wu-1", objective="inspect Android project")
    executor = RuntimeStageExecutor(
        agents={"android-developer": _agent()},
        models=[ModelSpec(id="model-1", provider_id="test")],
        executors={"android-developer": _Executor()},
        delegation=_Delegation(),
    )

    outcomes = executor.execute(
        work_unit=work_unit,
        plan=_plan(),
        stage_indices=(0,),
    )

    assert len(outcomes) == 1
    assert outcomes[0].success is True
    assert outcomes[0].agent_id == "android-developer"
    assert outcomes[0].confidence == 0.85
    assert outcomes[0].reason == "execution completed using model model-1"


def test_runtime_evidence_collector_prefers_event_journal_over_duplicate_ledger():
    work_unit = WorkUnit(id="wu-1", objective="inspect Android project")
    collector = RuntimeExecutionEvidenceCollector(
        event_store=_EventStore(),
        tool_ledger_store=_LedgerStore(),
    )

    evidence = collector.collect(work_unit, agent_id="android-developer")

    assert len(evidence) == 1
    assert evidence[0].source == "runtime.tool_result"
    assert evidence[0].metadata["invocation_id"] == "inv-1"

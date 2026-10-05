from types import SimpleNamespace

from core.adaptive_agent_execution import AdaptiveAgentExecutionLoop, AdaptiveExecutionPolicy
from core.agent_selection_policy import SelectionFallback, SelectionDecision
from core.contracts.agent import AgentContract, AgentTaxonomy
from core.contracts.agent_selection import AgentCandidate, AgentPlan, StageConfidence
from core.contracts.ai import ModelSpec
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState
from core.state import RuntimeEventStore
from core.tool_ledger import ToolInvocationStore
from runtime.adaptive_agent_execution import RuntimeExecutionEvidenceCollector, RuntimeStageExecutor


def _agent(agent_id, platform="android"):
    return AgentContract(
        id=agent_id,
        role="Android developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development", platform=platform),
    )


def _plan(work_unit_id="wu-e2e", selected="android-developer"):
    return AgentPlan(
        work_unit_id=work_unit_id,
        selected_agents=(selected,),
        route=(selected,),
        candidates=(
            AgentCandidate("android-developer", 0.52, stage_indices=(0,)),
            AgentCandidate("android-debugger", 0.51, stage_indices=(0,)),
        ),
        stage_confidences=(
            StageConfidence(0, selected, 0.52, 0.52, 0.01, 0.0),
        ),
        confidence=0.52,
    )


class _Delegation:
    def delegate(self, work_unit, agent, models, preferred_model_ids=None, strategy="pool"):
        return SimpleNamespace(assignment=SimpleNamespace(model_id=models[0].id))


class _Fallback:
    def select_stage(self, *, work_unit, evidence, candidates, stage_index):
        return SelectionDecision(
            selected_agents=("android-debugger",),
            confidence=0.91,
            reasons=("execution evidence indicates debugger is the better specialist",),
        )


class _RuntimeExecutor:
    def __init__(self, event_store, ledger_store):
        self.event_store = event_store
        self.ledger_store = ledger_store
        self.calls = []

    def execute(self, *, agent, model_id, work_unit):
        self.calls.append(agent.id)
        if agent.id == "android-developer":
            self.event_store.append(
                RuntimeEvent(
                    kind=RuntimeEventKind.TOOL_RESULT,
                    work_unit_id=work_unit.id,
                    payload={
                        "tool_id": "mcp.github.search",
                        "invocation_id": "inv-failed",
                        "ok": False,
                    },
                )
            )
            self.ledger_store.append(
                ToolInvocationRecord(
                    invocation_id="inv-failed",
                    work_unit_id=work_unit.id,
                    tool_id="mcp.github.search",
                    arguments={},
                    state=ToolInvocationState.FAILED,
                    replay_policy=ReplayPolicy(ReplayDisposition.SAFE),
                    sequence=1,
                )
            )
            raise RuntimeError("search failed")
        return {"ok": True}


def test_runtime_adapter_drives_failed_stage_into_specialist_reselection(tmp_path):
    work_unit = WorkUnit(
        id="wu-e2e",
        objective="debug Android build",
        status=WorkStatus.EXECUTING,
        target="android",
    )
    event_store = RuntimeEventStore(tmp_path / "events")
    ledger_store = ToolInvocationStore(tmp_path / "tool-ledger")
    fake = _RuntimeExecutor(event_store, ledger_store)
    stage_executor = RuntimeStageExecutor(
        agents={
            "android-developer": _agent("android-developer"),
            "android-debugger": _agent("android-debugger"),
        },
        models=[ModelSpec(id="model-1", provider_id="test")],
        executors={
            "android-developer": fake,
            "android-debugger": fake,
        },
        delegation=_Delegation(),
        evidence_collector=RuntimeExecutionEvidenceCollector(
            event_store=event_store,
            tool_ledger_store=ledger_store,
        ),
    )

    class _Selector:
        def select(self, work_unit, *, evidence):
            assert any(item.source == "runtime.tool_result" for item in evidence)
            return SimpleNamespace(plan=_plan(selected="android-developer"))

    loop = AdaptiveAgentExecutionLoop(
        selector=_Selector(),
        registry={
            "android-developer": _agent("android-developer"),
            "android-debugger": _agent("android-debugger"),
        },
        executor=stage_executor,
        selection_fallback=SelectionFallback(
            _Fallback(),
        ),
        policy=AdaptiveExecutionPolicy(max_attempts=2, retry_confidence_threshold=0.7),
    )

    rounds = loop.run(work_unit=work_unit, initial_plan=_plan())

    assert len(rounds) == 2
    assert fake.calls == ["android-developer", "android-debugger"]
    assert rounds[0].outcomes[0].success is False
    assert rounds[0].outcomes[0].evidence[0].source == "runtime.tool_result"
    assert rounds[1].plan.route == ("android-debugger",)
    assert rounds[1].outcomes[0].success is True
    assert work_unit.status is WorkStatus.EXECUTING

from core.contracts.agent import AgentContract, AgentTaxonomy
from core.contracts.ai import ModelSpec
from core.contracts.health import HealthStatus, ModelHealth
from core.contracts.agent_selection import AgentCandidate, AgentPlan, StageConfidence
from core.contracts.work_unit import WorkUnit
from runtime.adaptive_agent_execution import RuntimeStageExecutor


class _Executor:
    def __init__(self):
        self.calls = []

    def execute(self, *, agent, model_id, work_unit):
        self.calls.append((agent.id, model_id))
        return {"ok": True}


def _plan(agent_id):
    return AgentPlan(
        work_unit_id="wu-model-resolution",
        selected_agents=(agent_id,),
        route=(agent_id,),
        candidates=(AgentCandidate(agent_id, 0.9, stage_indices=(0,)),),
        stage_confidences=(StageConfidence(0, agent_id, 0.9, 0.9, 0.0, 0.0),),
        confidence=0.9,
    )


def test_runtime_stage_executor_enforces_agent_model_allowlist():
    agent = AgentContract(
        id="android-developer",
        role="Android developer",
        kind="specialist",
        model_ids=("allowed-model",),
        taxonomy=AgentTaxonomy(domain="development", platform="android"),
    )
    executor = _Executor()
    stage_executor = RuntimeStageExecutor(
        agents={agent.id: agent},
        models=[
            ModelSpec("forbidden-model", "test", frozenset()),
            ModelSpec("allowed-model", "test", frozenset()),
        ],
        executors={agent.id: executor},
    )

    outcomes = stage_executor.execute(
        work_unit=WorkUnit(id="wu-model-resolution", objective="build Android app"),
        plan=_plan(agent.id),
        stage_indices=(0,),
    )

    assert outcomes[0].success is True
    assert executor.calls == [(agent.id, "allowed-model")]


def test_runtime_stage_executor_records_model_routing_explanation():
    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development"),
    )
    executor = _Executor()
    work_unit = WorkUnit(id="wu-routing-audit", objective="implement feature")
    stage_executor = RuntimeStageExecutor(
        agents={agent.id: agent},
        models=[
            ModelSpec("generic", "test", frozenset({"code"})),
            ModelSpec("tools", "test", frozenset({"code", "tools"})),
        ],
        executors={agent.id: executor},
    )

    stage_executor.execute(
        work_unit=work_unit,
        plan=_plan(agent.id),
        stage_indices=(0,),
    )

    resolution = work_unit.metadata["agent_model_resolutions"][0]
    assert resolution["agent_id"] == agent.id
    assert resolution["model_id"] == "tools"
    assert len(resolution["candidates"]) == 2
    assert any(item["selected"] for item in resolution["candidates"])


def test_runtime_stage_executor_respects_model_health():
    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development"),
    )
    executor = _Executor()
    work_unit = WorkUnit(id="wu-health", objective="implement feature")
    stage_executor = RuntimeStageExecutor(
        agents={agent.id: agent},
        models=[
            ModelSpec("unhealthy", "test", frozenset()),
            ModelSpec("healthy", "test", frozenset()),
        ],
        executors={agent.id: executor},
        health_snapshots={
            "unhealthy": ModelHealth(
                model_id="unhealthy",
                provider_id="test",
                status=HealthStatus.AUTH_FAILED,
            )
        },
    )

    stage_executor.execute(
        work_unit=work_unit,
        plan=_plan(agent.id),
        stage_indices=(0,),
    )

    assert executor.calls == [(agent.id, "healthy")]

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
        capabilities=frozenset({"tools"}),
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


def test_runtime_stage_executor_records_model_success(tmp_path):
    from runtime.health import ModelHealthRegistry, ModelHealthStore

    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development"),
    )
    executor = _Executor()
    health_store = ModelHealthStore(tmp_path / "health")
    stage_executor = RuntimeStageExecutor(
        agents={agent.id: agent},
        models=[ModelSpec("model-a", "test", frozenset())],
        executors={agent.id: executor},
        health_registry=ModelHealthRegistry(health_store),
    )

    stage_executor.execute(
        work_unit=WorkUnit(id="wu-feedback-success", objective="implement"),
        plan=_plan(agent.id),
        stage_indices=(0,),
    )

    health = health_store.load("model-a")
    assert health.successes == 1
    assert health.consecutive_failures == 0


def test_runtime_stage_executor_records_model_failure(tmp_path):
    from runtime.health import ModelHealthRegistry, ModelHealthStore

    class _FailingExecutor(_Executor):
        def execute(self, *, agent, model_id, work_unit):
            raise RuntimeError("rate_limit exceeded")

    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development"),
    )
    health_store = ModelHealthStore(tmp_path / "health")
    stage_executor = RuntimeStageExecutor(
        agents={agent.id: agent},
        models=[ModelSpec("model-a", "test", frozenset())],
        executors={agent.id: _FailingExecutor()},
        health_registry=ModelHealthRegistry(health_store),
    )

    outcomes = stage_executor.execute(
        work_unit=WorkUnit(id="wu-feedback-failure", objective="implement"),
        plan=_plan(agent.id),
        stage_indices=(0,),
    )

    assert outcomes[0].success is False
    health = health_store.load("model-a")
    assert health.consecutive_failures == 1



def test_runtime_stage_executor_records_authorized_execution_decision():
    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development"),
    )
    executor = _Executor()
    work_unit = WorkUnit(id="wu-execution-decision", objective="implement feature")
    stage_executor = RuntimeStageExecutor(
        agents={agent.id: agent},
        models=[ModelSpec("model-a", "test", frozenset())],
        executors={agent.id: executor},
    )

    stage_executor.execute(
        work_unit=work_unit,
        plan=_plan(agent.id),
        stage_indices=(0,),
    )

    decision = work_unit.metadata["execution_decisions"][0]
    assert decision["agent_id"] == agent.id
    assert decision["model_id"] == "model-a"
    assert decision["authorized"] is True
    assert decision["governance_passed"] is True
    assert decision["decision_id"]
    assert decision["decision_id"] == work_unit.metadata["execution_decisions"][0]["decision_id"]


def test_runtime_stage_executor_blocks_execution_outside_governed_candidate_pool():
    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development"),
    )
    executor = _Executor()
    work_unit = WorkUnit(id="wu-governance-deny", objective="implement feature")
    plan = AgentPlan(
        work_unit_id=work_unit.id,
        selected_agents=(agent.id,),
        route=(agent.id,),
        candidates=(AgentCandidate(agent.id, 0.9, stage_indices=()),),
        stage_confidences=(StageConfidence(0, agent.id, 0.9, 0.9, 0.0, 0.0),),
        confidence=0.9,
    )
    stage_executor = RuntimeStageExecutor(
        agents={agent.id: agent},
        models=[ModelSpec("model-a", "test", frozenset())],
        executors={agent.id: executor},
    )

    outcomes = stage_executor.execute(
        work_unit=work_unit,
        plan=plan,
        stage_indices=(0,),
    )

    assert outcomes[0].success is False
    assert "outside the governed candidate pool" in outcomes[0].reason
    assert executor.calls == []
    decision = work_unit.metadata["execution_decisions"][0]
    assert decision["authorized"] is False
    assert decision["governance_passed"] is False


def test_execution_decision_is_reproducibly_identified():
    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        taxonomy=AgentTaxonomy(domain="development"),
    )
    work_unit = WorkUnit(id="wu-decision-id", objective="implement feature")
    plan = _plan(agent.id)
    from core.agent_model_resolver import AgentModelResolver

    resolution = AgentModelResolver().resolve(
        agent,
        [ModelSpec("model-a", "test", frozenset())],
    )
    from core.contracts.execution_decision import ExecutionDecision

    first = ExecutionDecision.authorize(
        work_unit=work_unit,
        plan=plan,
        stage_index=0,
        routing=resolution.explanation,
        attempt=1,
        governance_passed=True,
    )
    second = ExecutionDecision.authorize(
        work_unit=work_unit,
        plan=plan,
        stage_index=0,
        routing=resolution.explanation,
        attempt=1,
        governance_passed=True,
    )
    assert first.decision_id == second.decision_id

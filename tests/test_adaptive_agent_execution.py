"""Tests for the bounded adaptive Agent execution loop."""

from core.adaptive_agent_execution import (
    AdaptiveAgentExecutionLoop,
    AdaptiveExecutionPolicy,
    StageExecutionOutcome,
)
from core.contracts.agent_selection import AgentCandidate, AgentPlan, StageConfidence
from core.contracts.work_unit import WorkUnit
from agents.registry import build_registry


class _NoopFallback:
    def select(self, *, work_unit, deterministic, registry):
        return deterministic


class _Selector:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def select(self, work_unit, *, evidence=None):
        self.calls.append(tuple(evidence or ()))
        return type("Selection", (), {"plan": self.plan})()


class _Executor:
    def __init__(self):
        self.stage_calls = []

    def execute(self, *, work_unit, plan, stage_indices):
        self.stage_calls.append(tuple(stage_indices))
        return tuple(
            StageExecutionOutcome(
                stage_index=index,
                agent_id=plan.route[index],
                success=index != 1,
                confidence=0.20 if index == 1 else 0.95,
                reason="forced retry" if index == 1 else "ok",
            )
            for index in stage_indices
        )


def _plan():
    route = ("file-picker", "android-developer", "reviewer")
    candidates = tuple(
        AgentCandidate(agent_id=agent_id, score=0.8, stage_indices=(index,))
        for index, agent_id in enumerate(route)
    )
    stages = tuple(
        StageConfidence(
            stage_index=index,
            selected_agent_id=agent_id,
            selected_score=0.8,
            best_score=0.8,
            margin=1.0,
            evidence_coverage=0.0,
        )
        for index, agent_id in enumerate(route)
    )
    plan = AgentPlan(
        work_unit_id="wu-adaptive-loop",
        selected_agents=route,
        route=route,
        candidates=candidates,
        confidence=0.8,
        stage_confidences=stages,
    )
    plan.validate()
    return plan


def test_adaptive_loop_reexecutes_only_failed_specialist_stage():
    plan = _plan()
    executor = _Executor()
    loop = AdaptiveAgentExecutionLoop(
        selector=_Selector(plan),
        registry=build_registry(),
        executor=executor,
        selection_fallback=_NoopFallback(),
        policy=AdaptiveExecutionPolicy(max_attempts=2, retry_confidence_threshold=0.70),
    )

    rounds = loop.run(
        work_unit=WorkUnit(
            id="wu-adaptive-loop",
            objective="test adaptive execution",
            work_type="development",
            target="android",
        ),
        initial_plan=plan,
    )

    assert len(rounds) == 2
    assert executor.stage_calls == [(0, 1, 2), (1,)]
    assert rounds[0].outcomes[1].success is False


def test_adaptive_loop_is_bounded_by_max_attempts():
    plan = _plan()
    executor = _Executor()
    loop = AdaptiveAgentExecutionLoop(
        selector=_Selector(plan),
        registry=build_registry(),
        executor=executor,
        selection_fallback=_NoopFallback(),
        policy=AdaptiveExecutionPolicy(max_attempts=1),
    )

    rounds = loop.run(
        work_unit=WorkUnit(
            id="wu-adaptive-bound",
            objective="test bounded execution",
            work_type="development",
            target="android",
        ),
        initial_plan=plan,
    )

    assert len(rounds) == 1
    assert executor.stage_calls == [(0, 1, 2)]

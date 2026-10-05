"""Tests for evidence-driven automatic Agent selection."""

from core.agent_selector import DeterministicAgentSelector
from core.contracts.work_unit import WorkUnit


def test_android_work_selects_governed_android_route():
    work_unit = WorkUnit(
        id="wu-android",
        objective="Implement Android settings",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )

    selection = DeterministicAgentSelector().select(work_unit)

    assert selection.plan.selection_mode == "deterministic"
    assert "android-developer" in selection.plan.selected_agents
    assert selection.plan.selected_agents[0] == "file-picker"
    assert selection.plan.selected_agents[-1] == "reviewer"
    assert work_unit.assigned_agents == list(selection.plan.route)
    assert selection.plan.evidence


def test_explicit_agent_route_bypasses_automatic_selection_but_remains_validated():
    work_unit = WorkUnit(
        id="wu-explicit",
        objective="Run explicit route",
        work_type="development",
        target="android",
    )

    selection = DeterministicAgentSelector().select(
        work_unit,
        explicit_agents=("planner", "android-developer", "reviewer"),
    )

    assert selection.plan.selection_mode == "explicit"
    assert selection.plan.selected_agents == (
        "planner",
        "android-developer",
        "reviewer",
    )
    assert work_unit.assigned_agents == [
        "planner",
        "android-developer",
        "reviewer",
    ]


def test_generic_development_uses_bounded_route_without_platform_evidence():
    work_unit = WorkUnit(
        id="wu-generic",
        objective="Make a small code change",
        work_type="development",
    )

    selection = DeterministicAgentSelector().select(work_unit)

    assert selection.plan.selected_agents == (
        "file-picker",
        "planner",
        "editor",
        "executor",
        "reviewer",
    )


def test_repository_evidence_is_attached_and_changes_candidate_confidence():
    from core.contracts.repository import RepositoryEvidence

    work_unit = WorkUnit(
        id="wu-repo-evidence",
        objective="Inspect an Android repository change",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )
    repository_evidence = RepositoryEvidence(
        checkpoint_id="cp-test",
        git_status=" M app/src/main/java/MainActivity.kt",
        git_diff="+++ b/app/src/main/java/MainActivity.kt\n",
        validation={"platform": "android", "technology": "kotlin"},
    )

    selection = DeterministicAgentSelector().select(
        work_unit,
        repository_evidence=repository_evidence,
    )

    assert any(item.source == "repository.validation.platform" for item in selection.plan.evidence)
    assert any(item.kind.value == "verified" for item in selection.plan.evidence)
    assert selection.plan.confidence > 0.5
    assert selection.plan.candidates
    assert all(0.0 <= item.score <= 1.0 for item in selection.plan.candidates)
    assert any("android-developer" == item.agent_id for item in selection.plan.candidates)
    assert any(item.stage_indices for item in selection.plan.candidates)


class _LowConfidenceSelector:
    def select(self, *, work_unit, evidence, candidates):
        from core.agent_selection_policy import SelectionDecision
        from runtime.governance import specialist_route
        return SelectionDecision(
            selected_agents=specialist_route(work_unit),
            confidence=0.88,
            reasons=("fallback selector confirmed governed route",),
        )


def test_low_confidence_deterministic_selection_uses_policy_safe_fallback():
    from core.agent_selection_policy import AgentSelectionPolicy
    from core.agent_selector import EvidenceEngine

    work_unit = WorkUnit(
        id="wu-fallback",
        objective="Make an Android change",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )
    selector = DeterministicAgentSelector(
        evidence_engine=EvidenceEngine(),
        selection_strategy=_LowConfidenceSelector(),
        selection_policy=AgentSelectionPolicy(confidence_threshold=1.0),
    )

    selection = selector.select(work_unit)

    assert selection.plan.selection_mode == "hybrid"
    assert selection.plan.confidence == 0.88
    assert selection.plan.selected_agents == selection.plan.route
    assert selection.plan.policy_decisions


def test_selection_exposes_stage_aware_confidence_breakdown():
    from core.contracts.repository import RepositoryEvidence

    work_unit = WorkUnit(
        id="wu-stage-confidence",
        objective="Implement Android settings",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )
    repository_evidence = RepositoryEvidence(
        checkpoint_id="cp-stage-confidence",
        git_status="clean",
        git_diff="",
        validation={"platform": "android", "technology": "kotlin"},
    )

    selection = DeterministicAgentSelector().select(
        work_unit,
        repository_evidence=repository_evidence,
    )

    stages = selection.plan.stage_confidences
    assert len(stages) == len(selection.plan.route)
    assert tuple(item.stage_index for item in stages) == tuple(range(len(stages)))
    assert all(0.0 <= item.margin <= 1.0 for item in stages)
    assert all(0.0 <= item.evidence_coverage <= 1.0 for item in stages)
    assert any(item.evidence_coverage > 0.0 for item in stages)
    assert work_unit.metadata["agent_plan"]["stage_confidences"]


def test_partial_fallback_reselects_only_ambiguous_specialist_stage():
    from agents.registry import build_registry
    from core.agent_selection_policy import AgentSelectionPolicy, SelectionDecision, SelectionFallback
    from core.contracts.agent_selection import AgentCandidate, AgentPlan, StageConfidence
    from runtime.governance import specialist_route

    work_unit = WorkUnit(
        id="wu-partial",
        objective="Implement Android settings",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )
    route = specialist_route(work_unit)
    candidates = [
        AgentCandidate(agent_id=agent_id, score=0.90, stage_indices=(index,))
        for index, agent_id in enumerate(route)
    ]
    candidates.append(
        AgentCandidate(
            agent_id="react-native-developer",
            score=0.40,
            stage_indices=(4,),
        )
    )
    stages = [
        StageConfidence(
            stage_index=index,
            selected_agent_id=agent_id,
            selected_score=0.40 if index == 4 else 0.90,
            best_score=0.90,
            margin=0.10 if index == 4 else 1.0,
            evidence_coverage=0.0,
        )
        for index, agent_id in enumerate(route)
    ]
    plan = AgentPlan(
        work_unit_id=work_unit.id,
        selected_agents=route,
        route=route,
        candidates=tuple(candidates),
        confidence=0.80,
        stage_confidences=tuple(stages),
        evidence=(),
    )

    class StageStrategy:
        def __init__(self):
            self.stages = []

        def select_stage(self, *, work_unit, evidence, candidates, stage_index):
            self.stages.append(stage_index)
            return SelectionDecision(
                selected_agents=("react-native-developer",),
                confidence=0.91,
                reasons=("specialist ambiguity resolved",),
            )

    strategy = StageStrategy()
    result = SelectionFallback(
        strategy,
        policy=AgentSelectionPolicy(confidence_threshold=0.75),
    ).select(
        work_unit=work_unit,
        deterministic=plan,
        registry=build_registry(),
    )

    assert strategy.stages == [4]
    assert result.selected_agents[4] == "react-native-developer"
    assert result.selected_agents[:4] == route[:4]
    assert result.selected_agents[5:] == route[5:]
    assert result.candidates == plan.candidates
    assert result.stage_confidences[4].selection_source == "model"
    assert result.stage_confidences[4].model_confidence == 0.91
    assert all(
        stage.selection_source == "deterministic"
        for stage in result.stage_confidences[:4]
    )


def test_sparse_android_stage_expands_profile_candidates_and_keeps_top_k():
    from core.agent_selection_policy import CandidatePoolExpansionPolicy

    work_unit = WorkUnit(
        id="wu-adaptive-pool",
        objective="Implement Android build settings",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )
    selection = DeterministicAgentSelector(
        candidate_pool_policy=CandidatePoolExpansionPolicy(min_candidates=2, top_k=3),
    ).select(work_unit)

    stage_index = selection.plan.route.index("android-developer")
    stage_candidates = [
        candidate
        for candidate in selection.plan.candidates
        if stage_index in candidate.stage_indices
    ]

    assert len(stage_candidates) == 3
    assert "android-developer" in {candidate.agent_id for candidate in stage_candidates}
    assert "kotlin-developer" in {candidate.agent_id for candidate in stage_candidates}
    assert all(candidate.stage_indices for candidate in selection.plan.candidates)


def test_candidate_pool_does_not_expand_governance_only_routes():
    from core.agent_selection_policy import CandidatePoolExpansionPolicy
    from core.registry import AgentRegistry

    registry = AgentRegistry()
    from agents.catalog import build_agent_catalog

    for agent in build_agent_catalog():
        registry.register(agent)

    selector = DeterministicAgentSelector(
        registry=registry,
        candidate_pool_policy=CandidatePoolExpansionPolicy(min_candidates=2, top_k=3),
    )
    work_unit = WorkUnit(
        id="wu-no-governance-expansion",
        objective="Run a simple task",
        work_type="simple",
    )

    selection = selector.select(work_unit)

    assert all(
        selection.plan.route[index] in {
            candidate.agent_id
            for candidate in selection.plan.candidates
            if index in candidate.stage_indices
        }
        for index in range(len(selection.plan.route))
    )
    assert "android-architect" not in {candidate.agent_id for candidate in selection.plan.candidates}


def test_legacy_strategy_cannot_change_non_ambiguous_stage():
    from core.agent_selection_policy import AgentSelectionPolicy, SelectionDecision, SelectionFallback
    from core.contracts.agent_selection import AgentCandidate, AgentPlan, StageConfidence
    from runtime.governance import specialist_route
    from agents.registry import build_registry

    work_unit = WorkUnit(
        id="wu-legacy-guard",
        objective="Implement Android settings",
        work_type="development",
        target="android",
        metadata={"technology": "kotlin"},
    )
    route = specialist_route(work_unit)
    candidates = tuple(
        AgentCandidate(agent_id=agent_id, score=0.90, stage_indices=(index,))
        for index, agent_id in enumerate(route)
    ) + (AgentCandidate(agent_id="react-native-developer", score=0.40, stage_indices=(4,)),)
    stages = tuple(
        StageConfidence(
            stage_index=index,
            selected_agent_id=agent_id,
            selected_score=0.40 if index == 4 else 0.90,
            best_score=0.90,
            margin=0.10 if index == 4 else 1.0,
            evidence_coverage=0.0,
        )
        for index, agent_id in enumerate(route)
    )
    plan = AgentPlan(
        work_unit_id=work_unit.id,
        selected_agents=route,
        route=route,
        candidates=candidates,
        stage_confidences=stages,
        confidence=0.80,
    )

    class UnsafeLegacyStrategy:
        def select(self, *, work_unit, evidence, candidates):
            return SelectionDecision(
                selected_agents=(route[0], "kotlin-developer", *route[2:]),
                confidence=0.95,
            )

    try:
        SelectionFallback(
            UnsafeLegacyStrategy(),
            policy=AgentSelectionPolicy(confidence_threshold=0.75),
        ).select(work_unit=work_unit, deterministic=plan, registry=build_registry())
    except ValueError as exc:
        assert "only change ambiguous specialist stages" in str(exc)
    else:
        raise AssertionError("unsafe legacy strategy was accepted")



def test_selector_uses_agent_capability_requirements_to_bound_specialist_candidates():
    work_unit = WorkUnit(
        id="wu-capability-gate",
        objective="Implement React Native screen",
        work_type="development",
        target="react-native",
        metadata={
            "technology": "react-native",
            "agent_requirements": {
                "react-native-developer": {
                    "capabilities": ["code", "react-native"],
                    "tools": ["filesystem.write"],
                }
            },
        },
    )

    selection = DeterministicAgentSelector().select(work_unit)
    stage_index = selection.plan.route.index("react-native-developer")
    candidates = {
        item.agent_id
        for item in selection.plan.candidates
        if stage_index in item.stage_indices
    }

    assert "react-native-developer" in candidates
    assert "android-developer" not in candidates
    assert "ios-developer" not in candidates


def test_selector_fails_clearly_when_stage_capability_requirements_have_no_match():
    work_unit = WorkUnit(
        id="wu-capability-missing",
        objective="Implement unsupported specialist work",
        work_type="development",
        target="android",
        metadata={
            "technology": "kotlin",
            "agent_requirements": {
                "android-developer": {
                    "capabilities": ["code", "quantum-computing"],
                }
            },
        },
    )

    try:
        DeterministicAgentSelector().select(work_unit)
    except LookupError as exc:
        assert "android-developer" in str(exc)
        assert "capability requirements" in str(exc)
    else:
        raise AssertionError("expected capability-gated selection to fail")

from core.contracts.agent import AgentContract\nfrom core.contracts.agent_selection import AgentCandidate, AgentPlan, StageConfidence\nfrom core.contracts.ai import ModelSpec\nfrom core.contracts.execution_decision import ExecutionDecision\nfrom core.contracts.mcp import MCPTool, MCPToolProfile, ToolSideEffect\nfrom core.contracts.work_unit import WorkUnit\n\n\ndef _decision() -> tuple[ExecutionDecision, AgentContract]:
    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        permissions=frozenset({"repo.read"}),
    )
    work_unit = WorkUnit(id="wu-tool-auth", objective="inspect repository")
    candidate = AgentCandidate(
        agent_id=agent.id,
        score=1.0,
        stage_indices=(0,),
    )
    confidence = StageConfidence(
        stage_index=0,
        selected_agent_id=agent.id,
        selected_score=1.0,
        best_score=1.0,
        margin=1.0,
        evidence_coverage=0.0,
    )
    plan = AgentPlan(
        work_unit_id=work_unit.id,
        selected_agents=(agent.id,),
        route=(agent.id,),
        candidates=(candidate,),
        confidence=1.0,
        stage_confidences=(confidence,),
    )
    from core.routing import AIRouter
    resolution = AIRouter().explain(
        agent,
        [ModelSpec("model-a", "test", frozenset())],
    )
    decision = ExecutionDecision.authorize(
        work_unit=work_unit,
        plan=plan,
        stage_index=0,
        routing=resolution,
        attempt=1,
        governance_passed=True,
    )
    return decision, agent



def test_tool_authorization_binds_exact_execution_decision():
    from core.contracts.tool_authorization import ToolAuthorizationPolicy

    decision, agent = _decision()
    tool = MCPTool(
        name="read_repo",
        server_id="repo",
        permissions=frozenset({"repo.read"}),
    )

    authorization = ToolAuthorizationPolicy.authorize(
        decision=decision,
        agent=agent,
        tool=tool,
    )

    assert authorization.authorized is True
    assert authorization.decision_id == decision.decision_id
    assert authorization.tool_id == "repo:read_repo"
    assert authorization.model_id == decision.model_id


def test_tool_authorization_rejects_agent_mismatch():
    from core.contracts.tool_authorization import ToolAuthorizationPolicy

    decision, _ = _decision()
    other = AgentContract(
        id="other",
        role="Other",
        kind="specialist",
        permissions=frozenset({"repo.read"}),
    )
    tool = MCPTool(
        name="read_repo",
        server_id="repo",
        permissions=frozenset({"repo.read"}),
    )

    authorization = ToolAuthorizationPolicy.authorize(
        decision=decision,
        agent=other,
        tool=tool,
    )

    assert authorization.authorized is False
    assert "does not match execution decision" in authorization.findings[0]


def test_tool_authorization_enforces_existing_mcp_profile():
    from core.contracts.tool_authorization import ToolAuthorizationPolicy

    decision, agent = _decision()
    tool = MCPTool(
        name="write_repo",
        server_id="repo",
        permissions=frozenset({"repo.write"}),
        side_effect=ToolSideEffect.WRITE,
    )
    profile = MCPToolProfile(
        id="read-only",
        allowed_tools=frozenset({"repo:read_repo"}),
    )

    authorization = ToolAuthorizationPolicy.authorize(
        decision=decision,
        agent=agent,
        tool=tool,
        profile=profile,
    )

    assert authorization.authorized is False
    assert len(authorization.findings) >= 2

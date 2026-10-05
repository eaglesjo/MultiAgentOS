from core.contracts.agent import AgentContract
from core.contracts.agent_selection import AgentPlan
from core.contracts.ai import ModelSpec
from core.contracts.execution_decision import ExecutionDecision
from core.contracts.mcp import MCPTool, MCPToolProfile, ToolSideEffect
from core.contracts.work_unit import WorkUnit
from core.agent_model_resolver import AgentModelResolver


def _decision() -> tuple[ExecutionDecision, AgentContract]:
    agent = AgentContract(
        id="developer",
        role="Developer",
        kind="specialist",
        permissions=frozenset({"repo.read"}),
    )
    work_unit = WorkUnit(id="wu-tool-auth", objective="inspect repository")
    from core.agent_selector import AgentSelector
    plan = AgentSelector({agent.id: agent}).select(work_unit)
    resolution = AgentModelResolver().resolve(
        agent,
        [ModelSpec("model-a", "test", frozenset())],
    )
    decision = ExecutionDecision.authorize(
        work_unit=work_unit,
        plan=plan,
        stage_index=0,
        routing=resolution.explanation,
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

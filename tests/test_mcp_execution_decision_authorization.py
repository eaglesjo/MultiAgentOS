from types import SimpleNamespace

from core.contracts.agent import AgentContract
from core.contracts.execution_decision import ExecutionDecision
from core.contracts.mcp import MCPTool, MCPToolCall, MCPToolProfile, MCPToolResult
from core.contracts.work_unit import WorkUnit
from core.routing import RoutingCandidate, RoutingExplanation, RoutingStrategy
from runtime.mcp.policy import MCPAuthorizationError, MCPToolAuthorizer
from runtime.mcp.proxy import MCPToolProxy


def _decision(work_unit: WorkUnit, agent_id: str = "agent-a", model_id: str = "model-a") -> ExecutionDecision:
    routing = RoutingExplanation(
        agent_id=agent_id,
        strategy=RoutingStrategy.POOL,
        selected_model_id=model_id,
        candidates=(
            RoutingCandidate(
                model_id=model_id,
                provider_id="provider-a",
                selected=True,
                compatible=True,
                health_available=True,
                quota_available=True,
                capability_score=1.0,
                quota_score=1.0,
                missing_capabilities=frozenset(),
                rejection_reasons=(),
            ),
        ),
    )
    return ExecutionDecision(
        work_unit_id=work_unit.id,
        stage_index=0,
        agent_id=agent_id,
        model_id=model_id,
        attempt=1,
        selection_source="deterministic",
        selection_confidence=1.0,
        routing=routing,
        governance_passed=True,
        authorized=True,
    )


def _tool() -> MCPTool:
    return MCPTool(
        name="read_data",
        server_id="server-a",
        permissions=frozenset({"data.read"}),
    )


class _FakeClient:
    def __init__(self, tool: MCPTool):
        self.tool = tool
        self.session = None
        self.calls = 0

    def list_tools(self):
        return (self.tool,)

    def call_tool(self, request):
        self.calls += 1
        return MCPToolResult(
            request.server_id,
            request.tool_name,
            content=({"type": "text", "text": "ok"},),
        )


def test_authorized_execution_decision_reaches_mcp_and_is_audited():
    client = _FakeClient(_tool())
    agent = AgentContract(
        id="agent-a",
        role="specialist",
        tools=frozenset({"server-a:read_data"}),
        permissions=frozenset({"data.read"}),
    )
    decision = _decision(WorkUnit(id="work-1", objective="test"))

    result = MCPToolProxy({"server-a": client}).call(
        MCPToolCall("server-a", "read_data"),
        agent=agent,
        decision=decision,
    )

    assert client.calls == 1
    authorization = result.metadata["tool_authorization"]
    assert authorization["decision_id"] == decision.decision_id
    assert authorization["agent_id"] == "agent-a"
    assert authorization["model_id"] == "model-a"
    assert authorization["tool_id"] == "server-a:read_data"
    assert authorization["authorized"] is True


def test_unauthorized_execution_decision_never_reaches_mcp():
    client = _FakeClient(_tool())
    agent = AgentContract(
        id="agent-a",
        role="specialist",
        tools=frozenset({"server-a:read_data"}),
        permissions=frozenset({"data.read"}),
    )
    decision = _decision(WorkUnit(id="work-2", objective="test"))
    denied = ExecutionDecision(
        **{
            **decision.__dict__,
            "authorized": False,
            "governance_passed": False,
            "governance_findings": ("governance denied",),
        }
    )

    try:
        MCPToolProxy({"server-a": client}).call(
            MCPToolCall("server-a", "read_data"),
            agent=agent,
            decision=denied,
        )
    except MCPAuthorizationError as exc:
        assert "not authorized" in str(exc)
    else:
        raise AssertionError("unauthorized MCP invocation was not rejected")
    assert client.calls == 0


def test_agent_mismatch_never_reaches_mcp():
    client = _FakeClient(_tool())
    agent = AgentContract(
        id="agent-b",
        role="specialist",
        tools=frozenset({"server-a:read_data"}),
        permissions=frozenset({"data.read"}),
    )
    decision = _decision(WorkUnit(id="work-3", objective="test"), agent_id="agent-a")

    try:
        MCPToolProxy({"server-a": client}).call(
            MCPToolCall("server-a", "read_data"),
            agent=agent,
            decision=decision,
        )
    except MCPAuthorizationError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Agent-mismatched MCP invocation was not rejected")
    assert client.calls == 0


def test_missing_tool_permission_never_reaches_mcp():
    client = _FakeClient(_tool())
    agent = AgentContract(
        id="agent-a",
        role="specialist",
        tools=frozenset({"server-a:read_data"}),
        permissions=frozenset(),
    )
    decision = _decision(WorkUnit(id="work-4", objective="test"))

    try:
        MCPToolProxy({"server-a": client}).call(
            MCPToolCall("server-a", "read_data"),
            agent=agent,
            decision=decision,
        )
    except MCPAuthorizationError as exc:
        assert "missing tool permissions" in str(exc)
    else:
        raise AssertionError("permission-denied MCP invocation was not rejected")
    assert client.calls == 0


def test_profile_denial_never_reaches_mcp():
    client = _FakeClient(_tool())
    agent = AgentContract(
        id="agent-a",
        role="specialist",
        tools=frozenset({"server-a:read_data"}),
        permissions=frozenset({"data.read"}),
    )
    profile = MCPToolProfile(
        id="readonly",
        denied_tools=frozenset({"server-a:read_data"}),
    )
    decision = _decision(WorkUnit(id="work-5", objective="test"))
    proxy = MCPToolProxy(
        {"server-a": client},
        MCPToolAuthorizer((profile,)),
    )

    try:
        proxy.call(
            MCPToolCall("server-a", "read_data"),
            agent=agent,
            profile_id="readonly",
            decision=decision,
        )
    except MCPAuthorizationError as exc:
        assert "profile denied" in str(exc)
    else:
        raise AssertionError("profile-denied MCP invocation was not rejected")
    assert client.calls == 0



def test_session_bound_mcp_client_rejects_missing_or_mismatched_session():
    for request_session_id in (None, "session-other"):
        client = _FakeClient(_tool())
        client.session = SimpleNamespace(id="session-bound")
        try:
            MCPToolProxy({"server-a": client}).call(
                MCPToolCall(
                    "server-a",
                    "read_data",
                    session_id=request_session_id,
                )
            )
        except KeyError as exc:
            assert "MCP session mismatch" in str(exc)
        else:
            raise AssertionError(
                f"session mismatch was accepted: {request_session_id!r}"
            )
        assert client.calls == 0


def test_session_bound_mcp_client_accepts_exact_session():
    client = _FakeClient(_tool())
    client.session = SimpleNamespace(id="session-bound")

    result = MCPToolProxy({"server-a": client}).call(
        MCPToolCall(
            "server-a",
            "read_data",
            session_id="session-bound",
        )
    )

    assert client.calls == 1
    assert result.is_error is False

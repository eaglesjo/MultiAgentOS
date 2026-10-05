"""End-to-end audit trace for Agent x Model x MCP tool execution."""

import tempfile
from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.agent_execution_runtime import ToolSideEffect, ToolSpec
from core.contracts.ai import ModelSpec
from core.contracts.execution_decision import ExecutionDecision
from core.contracts.mcp import MCPTool, MCPToolCall, MCPToolResult
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.tool_ledger import ToolInvocationState
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.routing import RoutingCandidate, RoutingExplanation, RoutingStrategy
from core.state import RuntimeEventStore, WorkStateStore
from core.tool_ledger import ToolInvocationStore
from runtime.mcp.proxy import MCPToolProxy
from runtime.observability import ExecutionObservability
from runtime.tool_calling import ToolCallingRuntime, ToolRuntime


class FakeMCPClient:
    def __init__(self, tool: MCPTool) -> None:
        self.tool = tool
        self.session = None
        self.calls = 0

    def list_tools(self) -> tuple[MCPTool, ...]:
        return (self.tool,)

    def call_tool(self, request: MCPToolCall) -> MCPToolResult:
        self.calls += 1
        return MCPToolResult(
            request.server_id,
            request.tool_name,
            content=({"type": "text", "text": "mcp-ok"},),
        )


class OneToolModel:
    def generate_with_tools(self, model, request, tools):
        if request.metadata.get("tool_results"):
            return ModelResponse(text="done", model_id=model.id)
        return ModelResponse(
            text="",
            model_id=model.id,
            metadata={
                "tool_calls": [
                    {
                        "id": "read-1",
                        "name": "server-a:read_data",
                        "arguments": {"key": "value"},
                    }
                ]
            },
        )


def _decision(work_unit: WorkUnit, *, authorized: bool = True) -> ExecutionDecision:
    routing = RoutingExplanation(
        agent_id="agent-a",
        strategy=RoutingStrategy.POOL,
        selected_model_id="model-a",
        candidates=(
            RoutingCandidate(
                model_id="model-a",
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
        agent_id="agent-a",
        model_id="model-a",
        attempt=1,
        selection_source="deterministic",
        selection_confidence=1.0,
        routing=routing,
        governance_passed=authorized,
        governance_findings=() if authorized else ("governance denied",),
        authorized=authorized,
    )


def _agent() -> AgentContract:
    return AgentContract(
        id="agent-a",
        role="specialist",
        tools=frozenset({"server-a:read_data"}),
        permissions=frozenset({"data.read"}),
    )


def _tool() -> MCPTool:
    return MCPTool(
        name="read_data",
        server_id="server-a",
        permissions=frozenset({"data.read"}),
    )


def _runtime(root: Path, decision: ExecutionDecision, proxy: MCPToolProxy):
    work = WorkUnit(id=decision.work_unit_id, objective="audit MCP execution")
    work.transition(WorkStatus.EXECUTING)
    WorkStateStore(root / ".multiagentos" / "work").save(work)

    ledger = ToolInvocationStore(root / ".multiagentos" / "tool-ledger")
    events = RuntimeEventStore(root / ".multiagentos" / "events")
    tools = ToolRuntime()

    def call_mcp(request):
        result = proxy.call(
            MCPToolCall("server-a", "read_data", arguments=request.arguments),
            agent=_agent(),
            decision=decision,
        )
        authorization = result.metadata["tool_authorization"]
        assert authorization["decision_id"] == decision.decision_id
        return result.content

    tools.register(
        ToolSpec(
            "server-a:read_data",
            "read data through MCP",
            ToolSideEffect.READ,
            permissions=frozenset({"data.read"}),
        ),
        call_mcp,
    )

    runtime = ToolCallingRuntime(
        models={"model-a": ModelSpec("model-a", "provider-a", frozenset({"data"}))},
        adapters={"model-a": OneToolModel()},
        tools=tools,
        ledger_store=ledger,
        agent_id="agent-a",
        event_sink=events.append,
    )
    return runtime, ledger, events


def test_execution_decision_flows_through_mcp_ledger_events_and_observability():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        work = WorkUnit(id="work-e2e-1", objective="audit MCP execution")
        decision = _decision(work)
        client = FakeMCPClient(_tool())
        proxy = MCPToolProxy({"server-a": client})
        runtime, ledger, events = _runtime(root, decision, proxy)

        result = runtime.execute(
            ModelRequest(
                prompt="read data",
                metadata={"execution_decision": decision.to_metadata()},
            ),
            model_id="model-a",
            work_unit_id=work.id,
            granted_permissions=frozenset({"data.read"}),
        )

        assert result.response.text == "done"
        assert client.calls == 1

        record = ledger.load(work.id)[0]
        assert record.state is ToolInvocationState.COMPLETED
        assert record.decision_id == decision.decision_id
        assert record.agent_id == decision.agent_id
        assert record.model_id == decision.model_id

        durable_events = events.load(work.id)
        tool_call = next(item for item in durable_events if item["kind"] == "tool_call")
        tool_result = next(item for item in durable_events if item["kind"] == "tool_result")
        for event in (tool_call, tool_result):
            assert event["payload"]["decision_id"] == decision.decision_id
            assert event["payload"]["agent_id"] == decision.agent_id
            assert event["payload"]["model_id"] == decision.model_id

        summary = ExecutionObservability(root).summarize(work.id)
        assert summary.tool_count == 1
        assert summary.tool_decision_timeline == (
            {
                "invocation_id": record.invocation_id,
                "tool_id": "server-a:read_data",
                "decision_id": decision.decision_id,
                "agent_id": "agent-a",
                "model_id": "model-a",
                "state": "completed",
            },
        )


def test_denied_execution_decision_blocks_mcp_before_underlying_call_and_is_auditable():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        work = WorkUnit(id="work-e2e-denied", objective="deny MCP execution")
        decision = _decision(work, authorized=False)
        client = FakeMCPClient(_tool())
        proxy = MCPToolProxy({"server-a": client})
        runtime, ledger, events = _runtime(root, decision, proxy)

        result = runtime.execute(
            ModelRequest(
                prompt="read data",
                metadata={"execution_decision": decision.to_metadata()},
            ),
            model_id="model-a",
            work_unit_id=work.id,
            granted_permissions=frozenset({"data.read"}),
        )

        assert result.response.text == "done"
        assert result.tool_results[0].ok is False
        assert client.calls == 0
        assert "not authorized" in result.tool_results[0].error

        record = ledger.load(work.id)[0]
        assert record.state is ToolInvocationState.FAILED
        assert record.decision_id == decision.decision_id
        assert record.agent_id == decision.agent_id
        assert record.model_id == decision.model_id

        tool_result = next(item for item in events.load(work.id) if item["kind"] == "tool_result")
        assert tool_result["payload"]["decision_id"] == decision.decision_id
        assert tool_result["payload"]["ok"] is False

        summary = ExecutionObservability(root).summarize(work.id)
        assert summary.tool_decision_timeline[0]["decision_id"] == decision.decision_id
        assert summary.tool_decision_timeline[0]["state"] == "failed"

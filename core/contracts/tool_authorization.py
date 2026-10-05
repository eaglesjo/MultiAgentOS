"""Tool authorization bound to an execution decision."""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.execution_decision import ExecutionDecision
from core.contracts.mcp import MCPTool, MCPToolProfile


@dataclass(frozen=True)
class ToolAuthorization:
    """Auditable authorization for one MCP tool invocation."""

    decision_id: str
    agent_id: str
    model_id: str
    server_id: str
    tool_name: str
    authorized: bool
    findings: tuple[str, ...] = ()

    @property
    def tool_id(self) -> str:
        return f"{self.server_id}:{self.tool_name}"

    def validate(self) -> None:
        if not self.decision_id.strip():
            raise ValueError("tool authorization decision_id must not be empty")
        if not self.agent_id.strip() or not self.model_id.strip():
            raise ValueError("tool authorization requires Agent and Model")
        if not self.server_id.strip() or not self.tool_name.strip():
            raise ValueError("tool authorization requires server and tool")
        if self.authorized and self.findings:
            raise ValueError("authorized tool invocation cannot contain rejection findings")

    def to_metadata(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "model_id": self.model_id,
            "server_id": self.server_id,
            "tool_name": self.tool_name,
            "tool_id": self.tool_id,
            "authorized": self.authorized,
            "findings": list(self.findings),
        }


class ToolAuthorizationPolicy:
    """Binds MCP tool access to the exact authorized Agent × Model decision."""

    @staticmethod
    def authorize(
        *,
        decision: ExecutionDecision,
        agent: AgentContract,
        tool: MCPTool,
        profile: MCPToolProfile | None = None,
    ) -> ToolAuthorization:
        findings: list[str] = []
        if not decision.authorized:
            findings.append("execution decision is not authorized")
        if decision.agent_id != agent.id:
            findings.append("tool Agent does not match execution decision")
        if tool.permissions - agent.permissions:
            findings.append(
                "Agent is missing tool permissions: "
                + ", ".join(sorted(tool.permissions - agent.permissions))
            )
        if profile is not None and not profile.allows(tool, agent.permissions):
            findings.append("MCP tool profile denied the tool invocation")

        result = ToolAuthorization(
            decision_id=decision.decision_id,
            agent_id=agent.id,
            model_id=decision.model_id,
            server_id=tool.server_id,
            tool_name=tool.name,
            authorized=not findings,
            findings=tuple(findings),
        )
        result.validate()
        return result

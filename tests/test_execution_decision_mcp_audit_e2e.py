"""End-to-end audit trace for Agent x Model x MCP tool execution."""

from pathlib import Path

from core.contracts.agent import AgentContract
from core.contracts.agent_execution_runtime import ToolSideEffect, ToolSpec
from core.contracts.ai import ModelSpec
from core.contracts.execution_decision import ExecutionDecision
from core.contracts.mcp import MCPTool, MCPToolCall, MCPToolResult
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.tool_ledger import ToolInvocationState
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.core if False else core.contracts.work_unit import WorkUnit

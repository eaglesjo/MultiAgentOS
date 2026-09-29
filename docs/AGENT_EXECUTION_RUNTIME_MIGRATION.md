# Agent Execution Runtime API Migration

## Phase 1

The architectural name is now **Agent Execution Runtime**.

This phase adds canonical Python import paths without breaking existing consumers:

- `runtime.AgentExecutionRuntime`
- `runtime.agent_execution_runtime.AgentExecutionRuntime`
- `core.contracts.agent_execution_runtime`
- `runtime.mcp.agent_execution_runtime_server.AgentExecutionRuntimeMCPServer`

The historical VYRELON APIs remain available as compatibility surfaces, backed by the canonical implementation:

- `runtime.VYRELONRuntime`
- `runtime.vyrelon.VYRELONRuntime`
- `core.contracts.vyrelon_runtime`
- `runtime.mcp.server.VYRELONMCPServer`

## Migration rule

New code must use the Agent Execution Runtime names.

Existing integrations should not be forced to migrate in the same release solely because the architectural name changed.

## Phase 2

A later migration may remove the legacy implementation module facade and update CLI/configuration terminology after all repository consumers and external integration points have been audited.

No compatibility alias should be removed until that audit is complete.
